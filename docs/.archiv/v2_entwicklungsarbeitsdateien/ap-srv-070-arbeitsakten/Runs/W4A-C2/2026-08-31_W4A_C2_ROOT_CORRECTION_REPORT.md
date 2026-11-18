# AP-SRV-070 — W4A-C2 — Root Correction Report

**Datum:** 2026-08-31
**Auftrag:** Behebe ausschließlich die vier Root-Findings (E–H) aus `AP-SRV-070_W4A_C2_ROOT_CORRECTION.md`, auf dem aktuellen W4A-C1-Stand. Kein neues Architekturthema, kein allgemeines Refactoring, kein neuer absichtlicher nativer Kroko-Build, W4B nicht begonnen.

---

## 0. Vorprüfung gegen den aktuellen Code

Jeder Root-Fund wurde vor der Korrektur am tatsächlichen C1-Endstand nachvollzogen:

| Finding | Nachvollzogen an | Befund |
|---|---|---|
| E | `install_kroko.linux_build_env()` | setzte `KROKO_LICENSE` nur für `variant == "pro"`; bei `free` blieb ein geerbter Ambient-Wert unangetastet |
| F | `install_kroko.prepare_checkout()` | prüfte nur `ensure_pinned_revision()` (Commit-Identität), materialisierte aber keinen pristine Working-Tree-Zustand vor dem Patchen |
| G.1 | `install_kroko.detect_linux_toolchain_identity()` | probte nur `cmake`/`cc`/`gcc`/`clang`; kein separates C++-Compiler-Feld, obwohl Kroko ein C++-Projekt baut |
| G.2 | `buildinputs.LINUX_CMAKE_FLAGS` | deaktivierte `SHERPA_ONNX_USE_PRE_INSTALLED_ONNXRUNTIME_IF_AVAILABLE` nicht; Upstream-Default ist `ON` |
| H | `KrokoArtifactStore._slot_lock()` | reines `os.open(O_CREAT\|O_EXCL)` mit Löschen im `finally`; ein hart beendeter Prozess hinterlässt eine nie mehr automatisch erwerbbare Lock-Datei |

Alle vier Befunde bestätigt. Keiner erwies sich als bereits behoben oder als Fehlinterpretation.

---

## 1. Root Finding E — `KROKO_LICENSE` wird nie mehr ambient geerbt

### Umsetzung

- `buildinputs.PRO_BUILD_ENV_OFF_VALUE = "OFF"` und `buildinputs.KROKO_CAPABILITY_SWITCH_ENV_NAMES = (PRO_BUILD_ENV_NAME,)` neu deklariert.
- `install_kroko.sanitize_build_subprocess_env()` entfernt jetzt zusätzlich zu den vier Runtime-Lizenzkeys auch `KROKO_LICENSE` aus der übergebenen Umgebung — dieselbe Funktion wird von `linux_build_env()` **und** `windows_build_env()` verwendet, also gilt der Ambient-Strip für beide Plattformen.
- `linux_build_env()` setzt `KROKO_LICENSE` danach **immer** explizit: `ON` für `pro`, `OFF` für `free` — nie mehr ungesetzt.
- Windows bleibt bei der bestehenden `--variant`/`BUILD_VARIANT`-Steuerung des gepinnten Builders als Authority; da `windows_build_env()` denselben Sanitizer verwendet, kann `KROKO_LICENSE` dort nicht mehr ambient durchsickern, auch wenn die Windows-Buildlogik es ohnehin nicht liest (siehe §6).

### RED-/Regressionsnachweis (`RootFindingELinuxCapabilityIsolationTests`, 6 Tests)

- `test_ambient_license_on_does_not_survive_a_free_build`
- `test_ambient_license_off_does_not_prevent_a_pro_build`
- `test_ambient_garbage_value_does_not_survive_a_free_build`
- `test_windows_build_env_does_not_inherit_the_ambient_capability_switch`
- `test_sanitizer_strips_the_capability_switch_directly`
- `test_runtime_key_variables_remain_stripped_regression`

Zusätzlich verschärft: der bestehende `test_free_build_environment_does_not_enable_pro` prüft jetzt nicht mehr nur `assertNotIn(KROKO_LICENSE, build_env)`, sondern `assertEqual(build_env[KROKO_LICENSE], "OFF")` — die stärkere, jetzt korrekte Aussage.

---

## 2. Root Finding F — Builder-Checkout wird vor jedem echten Build pristine gemacht

### Umsetzung

Neue Funktion `install_kroko.materialize_pristine_checkout(repo_dir, revision, *, work_dir)`:

```python
run(["git", "reset", "--hard", revision], cwd=repo_dir)
run(["git", "clean", "-fdx"], cwd=repo_dir)
```

- Sicherheitsschranke identisch zum bestehenden Muster von `remove_tree_inside()`: verweigert die Ausführung, wenn `repo_dir` nicht eindeutig unterhalb des externen Kroko-Builder-Workroots (`work_dir`) liegt — betrifft also nie den VoiceSTT-Projektworktree.
- In `prepare_checkout()` direkt nach `ensure_pinned_revision()` verdrahtet, also **vor** jeder VoiceSTT-Patch-Anwendung, für **beide** Plattformen (Windows und Linux teilen sich denselben `prepare_checkout()`-Aufruf).
- Der normale Reuse-Pfad (Cache-Hit) ruft `prepare_checkout()` überhaupt nicht auf — bewiesen durch den neuen Test `test_reuse_hit_never_calls_prepare_checkout`.

### RED-/Regressionsnachweis (`RootFindingFPristineCheckoutTests`, 7 Tests, echte Git-Repos)

Diese Klasse verwendet **echte, temporäre Git-Repositories** (per `subprocess.run(["git", ...])`), keine gestubbten Aufrufe, um die tatsächliche Git-Mechanik zu beweisen:

- `test_prepare_checkout_restores_a_tracked_file_modified_by_a_previous_patch_run` — eine bereits gepatchte tracked Datei wird auf den pristine Commit-Inhalt zurückgesetzt, bevor Patches erneut angewendet werden
- `test_prepare_checkout_removes_a_stale_cmake_cache_and_build_artifacts` — untracked Build-/CMake-Reste überleben den Checkout nicht
- `test_free_cannot_inherit_a_pro_builds_cached_cmake_state` — direkter Nachweis der im Finding beschriebenen Gefahr
- `test_effective_repo_and_revision_still_feed_the_fingerprint` — Regression zu C1 Finding A: bewegliche Source-Overrides bleiben Fingerprint-Inputs
- `test_abbreviated_revision_cannot_bypass_the_exact_commit_postcheck`
- `test_materialize_pristine_checkout_refuses_a_path_outside_the_work_root`
- `test_materialize_pristine_checkout_refuses_the_work_root_itself`

**Harte Grenze eingehalten:** `materialize_pristine_checkout()` operiert ausschließlich auf dem validierten externen Kroko-Builder-Checkout; kein `git reset --hard`/`git clean` auf dem VoiceSTT-Projektworktree.

---

## 3. Root Finding G — vollständigerer Linux-Toolchain-Fingerprint

### 3.1 C++-Compiler-Identität

`detect_linux_toolchain_identity()` liefert jetzt zusätzlich `cxxCompilerPath`/`cxxCompilerVersion` (`c++`/`g++`/`clang++` über `shutil.which`), getrennt von `compilerPath`/`compilerVersion` (C). `CXX` bleibt Teil von `LINUX_BUILD_ENV_STRIP_NAMES` (bereits seit C1) und erreicht die Build-Kindumgebung weiterhin nicht.

**RED-/Regressionsnachweis (`RootFindingGCxxToolchainTests`, 5 Tests):**
- `test_identity_declares_a_separate_cxx_compiler_field`
- `test_c_and_cxx_compilers_are_not_collapsed_into_one_identity`
- `test_different_cxx_compiler_version_changes_the_linux_fingerprint`
- `test_ambient_cxx_override_does_not_survive_into_the_build_environment`
- `test_ordinary_voicestt_change_still_does_not_move_a_linux_fingerprint_with_cxx` (Gegenbeweis)

### 3.2 Pre-installed ONNX Runtime deterministisch deaktiviert

`buildinputs.LINUX_CMAKE_FLAGS` erhält den zusätzlichen Flag `-DSHERPA_ONNX_USE_PRE_INSTALLED_ONNXRUNTIME_IF_AVAILABLE=OFF`. Da CMake-Flags bereits ein Fingerprint-Input sind (C1), invalidiert diese Änderung den Linux-Fingerprint automatisch — kein separater Mechanismus nötig.

**RED-/Regressionsnachweis (`RootFindingGPreInstalledOnnxRuntimeTests`, 2 Tests):**
- `test_declared_linux_cmake_flags_disable_the_pre_installed_onnxruntime_default`
- `test_changing_the_declared_flags_changes_the_linux_fingerprint`

---

## 4. Root Finding H — Slot-Lock ist jetzt crash-recoverable

### Umsetzung

**Ersetzt** das C1-Locking (`os.open(O_CREAT|O_EXCL)` + Löschen im `finally`) durch **echtes OS-Advisory-Locking auf einem dauerhaft offenen Handle**:

- POSIX: `fcntl.flock(fd, LOCK_EX | LOCK_NB)` / `LOCK_UN`
- Windows: `msvcrt.locking(fd, LK_NBLCK, 1)` / `LK_UNLCK`

`_slot_lock()` öffnet die Lock-Datei mit `open(path, "a+b")`, versucht den OS-Lock mit Poll-Intervall bis `timeout`, hält ihn während des `yield`, gibt ihn im `finally` frei und schließt das Handle — **löscht die Datei aber nie**.

**Zentrale Design-Entscheidung, dokumentiert im Docstring:** Die Lock-Datei bleibt für immer als leere/inerte Markierung bestehen. Grund: Ein `unlink()` nach Freigabe würde die klassische "Unlink-Race" wiedereinführen — ein zweiter Prozess könnte zwischen "Lock freigegeben" und "Datei gelöscht" bereits eine neue Datei am selben Pfad sperren, während ein dritter Prozess noch die alte (inzwischen ungültige) Inode sperrt. Da der OS-Lock beim Prozessende (auch bei `kill`/Absturz) automatisch vom Betriebssystem freigegeben wird, ist die Dateiexistenz irrelevant für die Korrektheit — nur der Lock-Zustand zählt.

Damit ändert sich ein beobachtbares Nebenprodukt: Der Lock-Ordner enthält nach jeder erfolgreichen Operation genau eine persistente Marker-Datei pro jemals benutztem Slot, statt (wie unter C1) leer zu sein. Drei bestehende C1-Tests wurden entsprechend angepasst (siehe Testbericht §2).

### RED-/Regressionsnachweis (`RootFindingHCrashRecoverableLockTests`, 6 Tests)

- `test_orphaned_lock_is_reacquirable_without_manual_cleanup` — simulierter Absturz (Lock erwerben, Handle ohne Freigabe schließen): neuer Erwerb < 1 s statt Timeout-Wartezeit
- `test_orphaned_lock_after_a_real_killed_subprocess` — **echter separater Prozess**, real per `subprocess.Popen` gestartet, hält den Lock, wird per `process.kill()` hart beendet; neuer Erwerb < 5 s (siehe §7 zu einem während der Verifikation gefundenen Testfehler)
- `test_fresh_lock_still_excludes_a_second_acquirer` — Sicherheitsanforderung: ein lebender Lock darf nicht gestohlen werden
- `test_force_rebuild_still_really_replaces_regression` — C1-`adopt_existing=False`-Semantik bleibt unverändert
- `test_concurrent_store_still_avoids_corruption_regression` — zwei gleichzeitige Store-Aufrufer weiterhin ohne Korruption

---

## 5. Guard-/Revision-Vertrag

`BUILDER_REVISION` 2 → 3 angehoben (Dokumentation der Änderung direkt in `buildinputs.py`, siehe Docstring). Der bewachte Builder-Funktionsumfang (`BuildEffectiveLogicGuardTests.BUILDER_FUNCTION_NAMES`) wurde um `materialize_pristine_checkout` erweitert (13 Funktionen statt 12).

**Negativ verifiziert, nicht nur grün gesehen:** Der erwartete Digest wurde erst nach dem finalen Codezustand neu berechnet. Anschließend wurde eine künstliche Drift in eine der bewachten Funktionen injiziert (Kommentarzeile in `materialize_pristine_checkout` verändert, `BUILDER_REVISION` unverändert gelassen) → Guard-Test schlägt mit der erwarteten Digest-Mismatch-Meldung fehl. Nach Rücknahme der Drift: Guard wieder grün mit dem finalen Digest `5d4baea1924953743a3c8c9ee083383905f0fc4372f1d47e872f5d44703ada93`.

Kein Entfernen bewachter Funktionen, keine Guard-Abschwächung.

---

## 6. Windows-Buildpfad — warum Finding E/H ihn nicht real verändern

Zur Einordnung des Real-Artifact-Vertrags in §8: Sowohl Finding E (Capability-Isolation) als auch die Erweiterung von `sanitize_build_subprocess_env()` betreffen über die gemeinsame Sanitizer-Funktion technisch auch `windows_build_env()`. Das ändert das tatsächliche Verhalten eines Windows-Builds jedoch nachweislich nicht:

- `windows_build_env()`s eigener, bereits in C1 geschriebener Docstring stellt fest, dass der Windows-Build „entirely by the pinned upstream revision and VoiceSTT's patch set" gesteuert wird — es gibt dort schon vor C2 keine build-wirksamen Ambient-Variablen außer der Secret-Grenze.
- Der gepinnte Windows-Builder liest `KROKO_LICENSE` nicht; er wird über `--variant`/`BUILD_VARIANT` gesteuert (siehe Prompt §2, explizit bestätigt).
- Finding F (`materialize_pristine_checkout`) verändert das *Verhalten zukünftiger* Checkouts (pristine statt potenziell verschmutzt), ändert aber keine deklarierten Fingerprint-Werte und keine bereits abgeschlossene, historische Build-Provenienz.

Damit strippt C2 für Windows lediglich eine Variable, die der Windows-Builder ohnehin nie konsumiert hat — eine Determinismus-Härtung ohne Verhaltensänderung.

---

## 7. Während der Verifikation gefundener und behobener Testfehler (kein Produktcode-Fehler)

Bei der Verifikation von Finding H fiel eine auffällige, exakt reproduzierbare Laufzeit von ca. 30–31 Sekunden für `test_orphaned_lock_after_a_real_killed_subprocess` bzw. für `RootHardeningConcurrentSlotAccessTests` + `RootFindingHCrashRecoverableLockTests` zusammen auf (drei Wiederholungen: „31.02s" auf die Hundertstelsekunde identisch) — verdächtig nah an der `time.sleep(30)` des Kindprozesses im Test, obwohl dieser sofort nach dem Bestätigen von `"LOCKED"` per `process.kill()` beendet werden sollte.

**Root Cause identifiziert:** `self.assertEqual(line.strip(), "LOCKED", process.stderr.read())` — das `msg`-Argument von `assertEqual` wird als gewöhnliches Funktionsargument **eager** ausgewertet, also bei **jedem** Lauf, nicht nur im Fehlerfall. `process.stderr.read()` blockiert bis EOF auf der Stderr-Pipe des Kindprozesses — das setzt voraus, dass der (noch lebende, gerade erst 30 Sekunden schlafende) Kindprozess beendet ist. Da `process.kill()` erst im nachfolgenden `finally`-Block läuft, wartete der Test faktisch den vollen 30-Sekunden-Schlaf des Kindes ab, **bevor** er überhaupt zum Kill kam — der Test bewies damit nicht die beanspruchte „prompte Wiedererlangung nach Prozessabbruch", sondern nur eine (zufällig ähnlich schnelle) Wiedererlangung nach normalem Prozessende.

Direkt am Python-Interpreter reproduziert und bestätigt: ein isolierter `process.stderr.read()`-Aufruf auf einen noch laufenden, `time.sleep(30)`-haltenden Kindprozess blockierte exakt 30.0 Sekunden.

**Behebung:** Die Stderr-Lese­operation wurde hinter eine bedingte `if line.strip() != "LOCKED": self.fail(...)`-Prüfung verschoben, sodass sie nur im tatsächlichen Fehlerfall ausgewertet wird. Ergebnis: Testlaufzeit 30.25 s → 0.28 s, Test bleibt grün — jetzt aus dem richtigen Grund (echter, prompter Kill-Nachweis).

Dies ist ein Fehler in eigener Testinfrastruktur, kein Fund in E–H und kein neuer Root-Finding; er wird hier ausschließlich aus Transparenzgründen dokumentiert, konsistent mit der bisherigen Praxis dieses Workstreams, keine unerklärte Testlaufzeit unkommentiert zu lassen.

---

## 8. Real-Artifact-Vertrag — EVIDENCE_BLOCKED für diesen Teil

Der `BUILDER_REVISION`-Bump (2 → 3) ändert erwartungsgemäß auch den Windows-Free/Pro-Fingerprint auf diesem Host:

| | Vor C2 (`BUILDER_REVISION=2`, aus C1-Log) | Nach C2 (`BUILDER_REVISION=3`) |
|---|---|---|
| free (windows/amd64/cp312) | `9055547da3ba4d66` | `a11549d157f478b6` |
| pro (windows/amd64/cp312) | `2469fd1a25e86b97` | `0599c1a1bdc8e1c2` |

Die Analyse in §6 legt nahe, dass die reale Provenienz des bereits qualifizierten Wheels (`kroko_onnx-1.12.9-1free-cp312-cp312-win_amd64.whl`, SHA-256 `ac26db5d8c063649028924d4b55b14019b2370e8c457841ea278a8e48dd50041`) durch C2 nicht verändert wird und eine Re-Qualifizierung unter dem neuen Fingerprint zulässig wäre.

**Diese Re-Qualifizierung konnte in diesem Lauf jedoch nicht durchgeführt werden:** Die Wheel-Datei selbst ist auf dieser Maschine nicht mehr auffindbar. Der in C1 verwendete Session-Scratch-Artifact-Store, aus dem die Datei zuletzt wiederhergestellt wurde, existiert nicht mehr (vermutlich durch eine zwischenzeitliche Bereinigung des Temp-Verzeichnisses). Eine gezielte Suche über das gesamte `P:`-Laufwerk nach Dateiname **und** exakter Bytegröße (12 549 957 Bytes) fand keine Übereinstimmung; zwei Dateien mit demselben Namen in fremden, nicht mit diesem Projekt verbundenen lokalen Verzeichnissen (`Legacy-STT-kroko-debug`, `RealtimeVoiceProjekte/Legacy-STT`) wurden geprüft und anhand abweichender Dateigröße und SHA-256 eindeutig als **nicht identisch** ausgeschlossen (siehe `evidence_artifacts/2026-08-31_W4A_C2_requalification_log.md`).

Gemäß Prompt §7 wird dieser Teil deshalb explizit **`EVIDENCE_BLOCKED`** gemeldet, statt die fehlende Datei umzudeuten oder durch ein fremdes Wheel zu ersetzen. Es wurde **kein** neuer nativer Kroko-Build ausgelöst, um das Artefakt zu ersetzen — das wäre ein absichtlicher, für diese Korrektur nicht zwingend erforderlicher Native-Build und damit außerhalb des C2-Scopes.

Instrumentierte Builder-Tests (`BuilderReuseFlowTests`, gestubbter `build_wheel`) bleiben davon unberührt und ausdrücklich **kein** realer Build-Nachweis.

---

## 9. Scope-Hygiene

- Keine Änderungen an `VoiceSTT/kroko/models.py`, `VoiceSTT/assets/kroko/models.json`, `VoiceSTT/transcription_engines/kroko_onnx_engine.py` (W4B-Themen, außerhalb des Scopes).
- Keine Release-/Tag-/PyPI-Änderungen, keine Wakeword-Änderungen.
- Genau 5 Dateien geändert: `VoiceSTT/install_kroko.py`, `VoiceSTT/kroko/artifacts.py`, `VoiceSTT/kroko/buildinputs.py`, `tests/unit/test_kroko_artifact_store.py`, `tests/unit/test_kroko_fingerprint.py` (`git status --porcelain` bestätigt, keine Fremdartefakte).
- Alle bestehenden C1-Negativtests unverändert grün erhalten, bis auf die in §4 und im Testbericht §2 dokumentierten, begründeten Anpassungen an drei Assertions, deren beobachtetes Verhalten sich durch die crash-sichere Lock-Semantik korrekt geändert hat.
