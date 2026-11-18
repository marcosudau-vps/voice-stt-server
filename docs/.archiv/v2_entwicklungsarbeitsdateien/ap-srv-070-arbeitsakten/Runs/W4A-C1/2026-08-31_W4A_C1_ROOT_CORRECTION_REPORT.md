# AP-SRV-070 — W4A-C1 — Root Correction Report

**Datum:** 2026-08-31
**Auftrag:** Behebe ausschließlich die vier Root-Findings (A–D) plus die Root-Hardening-Anforderung aus `AP-SRV-070_W4A_C1_ROOT_CORRECTION.md`. Keine neue Architektur, kein allgemeines Refactoring.

---

## 0. Vorprüfung gegen den aktuellen Code

Jeder Root-Fund wurde vor der Korrektur am tatsächlichen W4A-Code nachvollzogen:

| Finding | Nachvollzogen an | Befund |
|---|---|---|
| A | `install_kroko.fingerprint_for()` | rief `compute_fingerprint(variant=args.variant)` — `args.repo`/`args.revision` flossen nie ein, obwohl `prepare_checkout()` sie real für Clone/Checkout verwendet |
| B | `VoiceSTT/kroko/fingerprint.py::toolchain_identity("linux")` + `install_kroko.linux_build_env()` | Linux-Identity kollabiert zu `{"kind": "host-native"}`; `linux_build_env()` kopierte `os.environ` vollständig, hängte an ein vorhandenes `SHERPA_ONNX_CMAKE_ARGS` an statt zu überschreiben, und `setdefault` bei `SHERPA_ONNX_MAKE_ARGS` |
| C | `install_kroko.linux_build_env()` + `install_windows()`/`build_windows_wheel()` | Linux kopierte den vollen Host-Environment (inkl. Keys); Windows startete `cmd.exe` ganz ohne `env=`, erbte also die volle Prozessumgebung |
| D | `VoiceSTT/kroko/artifacts.py::verify_artifact()` | Wheel-Tag-Prüfung nur `tag.startswith(f"{pythonTag}-{abiTag}")`; die Plattformkomponente des Tags wurde nie gegen `target.platform`/`architecture` geprüft |
| Hardening | `KrokoArtifactStore.store()` | Staging/Verify/Replace ohne Interprozess-Lock; zwei Racer könnten beide `final.exists() == False` sehen und beide `os.replace(staging, final)` versuchen |

Alle fünf Befunde bestätigt. Keiner erwies sich als bereits behoben oder als Fehlinterpretation.

---

## 1. Root Finding A — effektive Source-Overrides fließen jetzt in den Fingerprint

**Gewählter Vertrag: Variante 1 — Overrides bleiben unterstützt.**

Begründung: Die CLI-Hilfetexte von `--revision` behaupteten bereits vor der Korrektur „Overriding it changes the build fingerprint" — das war die dokumentierte Absicht, nur die Implementierung hielt sie nicht ein. Variante 1 ist damit die Korrektur, die den bestehenden Vertrag erfüllt, statt ihn rückwirkend zu ändern.

### Umsetzung

- `VoiceSTT/kroko/fingerprint.py::build_fingerprint_document()` akzeptiert jetzt `repo`/`revision` (Default: die gepinnten Werte aus `buildinputs.py`).
- `install_kroko.fingerprint_for(args)` übergibt `repo=args.repo, revision=args.revision` — exakt dieselben Werte, die `prepare_checkout()` für den echten Checkout verwendet.
- `main()`s Log-Zeile liest jetzt `computed["inputs"]["upstream"]` statt der statischen Pin-Konstante, zeigt also immer die tatsächlich wirksame Quelle.

### RED-/Regressionsnachweis (`RootFindingASourceOverrideTests`, 5 Tests)

- `test_default_and_different_revision_never_share_a_fingerprint`
- `test_default_and_different_repo_never_share_a_fingerprint`
- `test_default_invocation_resolves_to_the_static_pin` (Default bleibt unverändert)
- `test_describe_artifact_and_fingerprint_for_agree_on_the_effective_source`
- `test_prepare_checkout_uses_the_same_revision_the_fingerprint_hashes` (treibt den echten `prepare_checkout()`-Pfad mit gepatchtem `run`/`ensure_pinned_revision`)

**Nebenwirkung, geprüft:** Der Standardfall (kein Override) liefert exakt denselben Fingerprint wie zuvor an dieser Stelle — nur `BUILDER_REVISION` (siehe §2/§3) ändert den Wert, nicht die Repo/Revision-Übergabe selbst.

---

## 2. Root Finding B — Linux-Toolchain-Identität ist jetzt deklariert

**Gewählter Vertrag: Kombination beider im Prompt erlaubten Optionen** — geschlossen dort, wo Normalisierung ausreicht; deklariert, wo eine echte Host-Eigenschaft (Compiler/CMake) betroffen ist.

### a) Ambient-Overrides entfernt/normalisiert (statt in den Fingerprint aufgenommen)

`linux_build_env()`:
- `SHERPA_ONNX_CMAKE_ARGS`/`SHERPA_ONNX_MAKE_ARGS` werden jetzt **gesetzt**, nicht mehr angehängt bzw. nur bei Fehlen belegt.
- Ein neuer, deklarierter Streichungssatz `LINUX_BUILD_ENV_STRIP_NAMES` entfernt `CC`, `CXX`, `CFLAGS`, `CXXFLAGS`, `CPPFLAGS`, `LDFLAGS`, `CMAKE_ARGS`, `CMAKE_GENERATOR`, `CMAKE_TOOLCHAIN_FILE`, `CMAKE_PREFIX_PATH`, `CMAKE_C_COMPILER`, `CMAKE_CXX_COMPILER`, `LD_LIBRARY_PATH`, `LIBRARY_PATH`, `CPATH`, `C_INCLUDE_PATH`, `CPLUS_INCLUDE_PATH` aus der Build-Kindumgebung.

Diese Werte werden entfernt statt gehasht, weil sie sonst den Fingerprint aufblähen würden, ohne die eigentliche Ursache (ein Build, der stillschweigend von der Shell-Umgebung des Bedieners abhängt) zu beseitigen — genau das war der Fehler.

### b) Echte Compiler-/CMake-Identität für den realen Linux-Pfad

Neue Funktion `install_kroko.detect_linux_toolchain_identity()`: ermittelt `cmake --version` und `cc`/`gcc`/`clang --version` über `shutil.which` + `subprocess.run` und liefert `{"kind": "host-native", "cmakePath", "cmakeVersion", "compilerPath", "compilerVersion"}`. `fingerprint_for(args)` ruft das **nur auf Linux** auf und übergibt das Ergebnis als `toolchain=` — der Windows-Pfad bleibt unverändert host-unabhängig (Docker-Crossbuild-Identität), da dort tatsächlich der gepinnte Upstream plus Patch-Set das Ergebnis bestimmt, nicht der Host.

`compute_fingerprint()`/`build_fingerprint_document()` selbst bleiben unverändert rein (kein Datei-/Subprozesszugriff) — die Probe passiert ausschließlich im Installer, der bewusst reale Systemzustände abfragen darf.

### RED-/Regressionsnachweis (`RootFindingBLinuxToolchainFingerprintTests`, 7 Tests + `RootFindingBLinuxBuildEnvTests`, 4 Tests)

- `test_linux_fingerprint_uses_a_probed_toolchain_not_the_generic_placeholder`
- `test_different_cmake_version_changes_the_linux_fingerprint`
- `test_different_compiler_version_changes_the_linux_fingerprint`
- `test_windows_fingerprint_never_probes_the_host_toolchain` (Gegenprobe: Windows bleibt unverändert)
- `test_ordinary_voicestt_change_still_does_not_move_a_linux_fingerprint` (Gegenbeweis: VERSION-Override bewegt den jetzt probeten Linux-Fingerprint weiterhin nicht)
- `test_detect_linux_toolchain_identity_probes_real_tools` / `..._tolerates_a_missing_tool`
- `test_ambient_compiler_overrides_never_reach_the_build_environment`
- `test_cmake_args_override_ambient_value_instead_of_appending`
- `test_make_args_override_ambient_value_instead_of_defaulting`
- `test_declared_flags_are_still_applied_with_a_clean_environment`

`BUILDER_REVISION` wurde 1 → 2 angehoben (siehe §5) und deckt genau diese Änderung ab, weil `linux_build_env()` und `fingerprint_for()` beide Teil der bewachten Builder-Fläche sind.

---

## 3. Root Finding C — Kroko-Lizenzkeys erreichen die Build-Umgebung nicht mehr

### Umsetzung

Neue, gemeinsame Sanitizer-Funktion `install_kroko.sanitize_build_subprocess_env(base_env)` entfernt `KROKO_API_KEY`, `KROKO_ONNX_KEY`, `VOICESTT_KROKO_ONNX_KEY`, `KROKO_KEY` (deklariert in `KROKO_LICENSE_KEY_ENV_NAMES`) aus einer Kopie der übergebenen Umgebung.

- `linux_build_env()` ruft sie jetzt zuerst auf, **bevor** die Ambient-Strip-Liste und die deklarierten Flags gesetzt werden.
- Neue Funktion `install_kroko.windows_build_env()` wendet denselben Sanitizer an; `install_windows()` und `build_windows_wheel()` übergeben jetzt beide explizit `env=windows_build_env()` an `run(["cmd.exe", ...])` statt (wie zuvor) `env=None` (= volle Prozessumgebung erben).

`install_windows()` ist toter Code (kein Aufrufer mehr seit `build_wheel()`/`build_windows_wheel()` eingeführt wurden), wurde aber aus Sorgfalt ebenfalls korrigiert, um keinen latenten unsicheren Pfad liegen zu lassen, falls er reaktiviert wird.

Pro bleibt ausschließlich über `buildinputs.PRO_BUILD_ENV_NAME`/`PRO_BUILD_ENV_VALUE` (`KROKO_LICENSE=ON`) gesteuert — unverändert ein Capability-Switch, kein Secret.

### RED-/Regressionsnachweis

Der **bestehende** Test `test_pro_build_environment_carries_no_key` prüfte bisher nur, dass der Secret-**Wert** nicht in den CMAKE-/MAKE-Argument-**Strings** auftaucht — genau die vom Prompt benannte Schwäche. Er wurde verschärft: er prüft jetzt zusätzlich, dass die vier **Variablennamen selbst** aus dem `build_env`-Dict verschwunden sind.

Neu:
- `test_windows_build_environment_carries_no_key` (Windows-Pfad, vorher komplett ungetestet für dieses Szenario)
- `test_runtime_key_lookup_outside_the_builder_is_unchanged` — belegt, dass `kroko_onnx_engine.py` unverändert dieselben vier Variablen zur Laufzeit liest (Datei nicht angefasst)
- `test_free_build_environment_does_not_enable_pro` (unverändert, weiterhin grün)

`kroko_onnx_engine.py` wurde für diese Korrektur **nicht** angefasst — die Laufzeit-Key-Auflösung ist exakt wie vor W4A-C1.

---

## 4. Root Finding D — Wheel-Plattform-Tag wird jetzt gegen den Ziel-Fingerprint geprüft

### Umsetzung

Neue Funktion `artifacts.wheel_platform_tag_matches_target(platform_tag, target_platform, architecture)`: prüft die Plattform-Familie (`win*` für windows, `linux*`/`manylinux*`/`musllinux*` für linux, `macosx*` für darwin) **und**, soweit im Tag kodierbar, die Architektur (`amd64`/`x86_64`, `arm64`/`aarch64`).

`verify_artifact()` verlangt jetzt für jeden Wheel-Tag sowohl den Python/ABI-Präfix-Treffer **als auch** einen positiven Plattform-Match über diese Funktion, bevor der Tag als kompatibel gilt. Eine reine Metadata-Selbstauskunft (`targetPlatform` im gespeicherten Dokument) reicht nicht mehr — geprüft wird der tatsächliche Tag-String des Wheels.

### RED-/Regressionsnachweis (`RootFindingDWheelPlatformVerificationTests`, 7 Tests)

- `test_windows_wheel_is_rejected_under_linux_inputs` → REJECT
- `test_linux_wheel_is_rejected_under_windows_inputs` → REJECT
- `test_arm64_wheel_is_rejected_under_amd64_inputs` → REJECT
- `test_amd64_wheel_is_rejected_under_arm64_inputs` → REJECT
- `test_matching_windows_wheel_is_accepted` → PASS
- `test_matching_manylinux_wheel_is_accepted` → PASS
- `test_platform_tag_matcher_directly` — Direkttest der Matcher-Funktion

**Realer Nachweis am tatsächlich qualifizierten Wheel:** Der reale `kroko_onnx-1.12.9-1free-cp312-cp312-win_amd64.whl` wurde nach der Korrektur erneut gegen ein `windows`/`amd64`-Ziel gespeichert und per `lookup()` ohne Beanstandung gefunden (`problems == []`) — die neue Prüfung akzeptiert also weiterhin korrekt den echten, passenden Fall (siehe Artifact-Report).

---

## 5. Root Hardening — gleichzeitiger Zugriff auf denselben Artifact-Slot

**Gewählter Weg: kleine per-Slot-Lock-Lösung** (vom Prompt ausdrücklich zugelassen).

### Umsetzung

- `KrokoArtifactStore._slot_lock(variant, fingerprint)`: Kontextmanager, exklusiv über `os.open(path, O_CREAT | O_EXCL | O_RDWR)` — ein atomarer OS-Syscall auf POSIX **und** Windows, kein Python-GIL-Lock. Wartet mit Poll-Intervall bis zu 30 Minuten (`DEFAULT_LOCK_TIMEOUT_SECONDS`), danach `KrokoArtifactError`.
- `store()` hält den Lock nur um die kurze Entscheidungs-/Replace-Phase, nicht um das (potenziell größere) Staging/Verify — Staging ist bereits durch eindeutige `uuid4`-Verzeichnisnamen kollisionsfrei.
- **Neuer Parameter `adopt_existing` (Default `True`):** Findet `store()` innerhalb des Locks bereits ein verifiziertes Artefakt für denselben Slot, wird dieses **übernommen statt überschrieben** — beide Kandidaten sind für denselben Fingerprint gleichwertig, ein Ersetzen brächte nichts außer unnötigem I/O. `--rebuild-kroko` ruft `store()` explizit mit `adopt_existing=False` auf, damit ein erzwungener Rebuild **immer** wirklich ersetzt (siehe „Während der Korrektur gefundener Zusatzfehler" unten).

### Warum kein größeres Job-/Scheduler-System

Der Lock schützt exakt die Stelle, die laut Finding tatsächlich unsicher war (die finale `os.replace`-Entscheidung). Er koordiniert **nicht** die vorgelagerte, potenziell 30-minütige Kompilierung zweier Racer — ein doppelter, redundanter nativer Build bleibt möglich, ist aber ein Performance-, kein Korrektheitsproblem: beide Racer landen dank des Locks garantiert auf demselben, einmal verifizierten Endzustand. Eine verteilte Build-Koordination über Prozessgrenzen hinweg wäre genau das vom Prompt ausgeschlossene „allgemeine Job-/Scheduler-System".

### RED-/Regressionsnachweis (`RootHardeningConcurrentSlotAccessTests`, 3 Tests)

- `test_concurrent_stores_of_the_same_slot_do_not_corrupt_it` — zwei echte `threading.Thread`s, synchronisiert über eine `Barrier`, rufen `store()` mit **unterschiedlichem** Wheel-Inhalt für denselben Slot auf. Erwartung: keine Exception, beide Aufrufe liefern denselben `wheel_sha256`, der Slot enthält genau eine `.whl`-Datei, keine Lock-/Staging-Leichen.
- `test_a_second_store_call_reuses_an_already_stored_artifact`
- `test_slot_lock_is_mutually_exclusive` — Direktnachweis des Lock-Primitives selbst (Reihenfolge `holder-enter, holder-exit, waiter-enter` erzwungen über `threading.Event`).

**Threads statt echter Prozesse — bewusst und begründet:** Der Lock ist ein OS-Level-Primitiv (`os.open` mit `O_EXCL`), keine Python-GIL-Sperre; Datei-I/O gibt den GIL frei, sodass zwei Python-Threads am Dateisystem tatsächlich race-fähig sind. Das Primitiv selbst verhält sich für zwei Threads im selben Prozess identisch zu zwei getrennten OS-Prozessen. Diese Begründung steht auch als Docstring im Test.

**Negativ verifiziert, nicht nur grün gesehen:** Der Lock-Aufruf in `store()` wurde testweise durch `contextlib.nullcontext()` ersetzt und der Concurrency-Test **8-mal** wiederholt — **alle 8 Läufe schlugen fehl** (Korruption/Exception). Nach Rücknahme der Änderung: wieder zuverlässig grün. Damit ist belegt, dass der Test die Race tatsächlich erkennt und nicht zufällig immer besteht.

### Während der Korrektur gefundener und behobener Zusatzfehler

Die erste Implementierung von „adopt existing" hätte **`--rebuild-kroko` unwirksam gemacht**: Ein erzwungener Rebuild hätte sein frisch gebautes Wheel verworfen und stillschweigend das alte behalten, sobald `store()` beim Abschluss ein bereits vorhandenes Artefakt vorfand. Das hätte den originalen W4A-Vertrag „Force: REBUILD -> VERIFY -> ATOMICALLY REPLACE" gebrochen. Aufgedeckt durch den bereits bestehenden Test `test_successful_store_replaces_the_previous_artifact` (jetzt `test_forced_store_replaces_the_previous_artifact`, mit `adopt_existing=False`), der sofort fehlschlug. Behoben durch den `adopt_existing`-Parameter; `install_kroko.main()` übergibt `adopt_existing=not args.rebuild_kroko`. Zusätzlich abgesichert durch den neuen Test `test_force_rebuild_actually_replaces_the_stored_artifact`, der die tatsächlich gespeicherten Bytes prüft, nicht nur den Builder-Aufrufzähler.

---

## 6. Verwendeter realer Artefakt-Kontext (klare Trennung)

| Aussage | Status |
|---|---|
| Bereits existierendes reales Kroko-Wheel (`kroko_onnx-1.12.9-1free-cp312-cp312-win_amd64.whl`, SHA-256 `ac26db5d…`) wurde unter dem **neuen**, durch C1 veränderten Fingerprint erneut vollständig qualifiziert | **JA** — real: Store, Verify (inkl. der neuen Finding-D-Plattformprüfung), Reuse-Lookup, echte Installation in eine wegwerfbare venv, `import kroko_onnx`, Variantenverifikation inkl. Negativprobe. Siehe Artifact-Report. |
| Neuer nativer Kroko-Build in W4A-C1 ausgeführt | **NEIN**, mit einer Ausnahme: ein **unbeabsichtigter** Build-Versuch (siehe §7) |
| Instrumentierte Builder-Tests (`BuilderReuseFlowTests`, gestubbter `build_wheel`) | Ausdrücklich **kein** realer 30-Minuten-Build — Aufrufzähler und jetzt zusätzlich die tatsächlich gespeicherten Bytes, nie eine echte Kompilierung |

---

## 7. Vorfall während der Verifikation: unbeabsichtigter Build-Versuch (vollständig dokumentiert)

Bei der manuellen Re-Qualifizierung des echten Wheels unter dem neuen Fingerprint verwendete ein eigenes Verifikationsskript einen POSIX-artigen Pfad (`/c/Users/...`) als Python-`Path`-Literal aus einer Bash-Umgebung heraus. `pathlib.Path` interpretiert einen solchen Pfad unter Windows als **laufwerksrelativ**, nicht als absolut, und `.resolve()` hängte ihn an das aktuelle Arbeitslaufwerk (`P:`) an — der Artifact-Store landete dadurch an einem falschen Ort, und der reale `stt-install-kroko`-Lauf sah einen Cache-Miss.

Da `--rebuild-kroko` **nicht** gesetzt war, fiel der Lauf regulär auf den Build-Pfad zurück: `ensure_windows_host()` meldete Docker als lauffähig (siehe §8 — Docker hat sich seit dem ursprünglichen W4A-Lauf erholt), und `build_windows.bat --variant free` startete real. Der Docker-Build scheiterte einige Schritte später an einem externen, unabhängigen Problem (ein `curl`-Download von `slproweb.com` innerhalb des Docker-Builds schlug fehl) — kein Zusammenhang mit den C1-Änderungen.

**Nebenwirkung:** `build_windows.bat` leert offenbar sein Ausgabeverzeichnis (`release_artifacts\windows`), bevor es den eigentlichen Build startet. Das vorher dort liegende, real qualifizierte Wheel war danach nicht mehr vorhanden.

**Kein Datenverlust:** Eine bytegenaue Kopie desselben Wheels (SHA-256 `ac26db5d…`, verifiziert) existierte bereits in einem Session-Scratch-Artifact-Store aus einem vorherigen Schritt desselben Laufs. Diese Kopie wurde zur Wiederherstellung von `release_artifacts\windows` verwendet (Hash nach Wiederherstellung erneut verifiziert) und anschließend für die korrekte, PowerShell-native Re-Qualifizierung verwendet.

**Root Cause war ein Fehler in der eigenen Verifikationstooling (bash→Python-Pfad-Mischung), kein Fehler im W4A/W4A-C1-Produktcode.** Der reale `install_kroko.main()`-Reuse-Pfad funktioniert bei korrekt aufgelöstem Store-Pfad wie vorgesehen (siehe §6 und Artifact-Report: sauberer Reuse-Treffer ohne jeden Build-Versuch bei identischem, aber korrekt aufgelöstem Store-Pfad).

**Lehre für künftige Läufe:** `VOICESTT_KROKO_ARTIFACT_STORE`/`--artifact-store` und jeder an `install_kroko`/`artifacts.py` übergebene Pfad müssen aus PowerShell (nativer Windows-Pfad) oder aus einem bereits von `pathlib` aufgelösten Wert stammen — niemals als roher POSIX-Pfad-String aus einer Bash-Umgebung in Python-Quelltext eingebettet werden.

---

## 8. Docker-Umgebungsstatus (nur informativ, ehrlich aktualisiert)

W3 und der ursprüngliche W4A-Lauf dokumentierten einen hängenden Docker-Container-Runtime (`docker run` lief selbst mit bereits lokal vorhandenen Images in den Timeout). Dieser Status wurde für W4A-C1 **erneut geprüft, nicht ungeprüft übernommen**:

```
docker run --rm alpine:latest echo "container-runtime-check-c1"
→ "container-runtime-check-c1", Exit 0
```

**Docker ist in dieser Umgebung inzwischen wieder funktionsfähig** (Container-Ausführung, Image-Build, `docker version`). Das erklärt auch, wie der in §7 beschriebene unbeabsichtigte Build-Versuch überhaupt bis in einen echten Docker-Build-Schritt vordringen konnte. Der tatsächliche Windows-Kroko-Build scheiterte dennoch an einem externen, von W4A-C1 unabhängigen Problem (siehe §7) — ein echter, vollständiger Kroko-Windows-Build wurde in diesem Lauf bewusst nicht verfolgt, da er außerhalb des C1-Scopes liegt und nicht notwendig war (das reale Artefakt war bereits vorhanden und wurde erfolgreich re-qualifiziert).
