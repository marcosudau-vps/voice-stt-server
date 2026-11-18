# AP-SRV-070 / W4A-C3 — Test Report

**Datum:** 2026-09-01
**Stand:** finaler C3-Code
**Interpreter:** CPython 3.12.10 x64, Windows 11 Pro 26200

---

## 0. Umgebungsvorbedingung (ehrlich benannt, nicht weggewinkt)

Ein erster Regressionslauf ohne `--basetemp` erzeugte **48 Setup-Errors**. Diese
sind **nicht** durch C3 verursacht und auch keine Testfehler: pytests
`tmp_path`-Fixture scannt sein Basisverzeichnis, und

```text
C:\Users\user\AppData\Local\Temp\pytest-of-marco
```

ist auf diesem Host nicht mehr lesbar:

```text
PermissionError: [WinError 5] Zugriff verweigert:
    'C:\Users\user\AppData\Local\Temp\pytest-of-marco'
```

`icacls` auf dasselbe Verzeichnis scheitert ebenfalls mit „Zugriff verweigert".
Das Verzeichnis stammt vom 2026-05-04 und ist eine vorbestehende Altlast der
Arbeitsumgebung. Frühere AP-SRV-070-Läufe sind demselben Problem bereits
begegnet und haben es genauso umgangen (im Temp liegen `pytest-w1b`,
`w1b-pytest-full`, `w1b-c1-pytest-full`).

Alle Läufe unten verwenden daher ein eigenes Basisverzeichnis
(`--basetemp=...\w4a-c3-pytest-final`). Damit verschwinden alle 48 Errors
vollständig — sie waren ausschließlich Fixture-Setup, nie Testlogik.

---

## 1. Gezielte RED-/Regression-Tests für Findings I–K

Alle neuen Tests laufen gegen echte Primitive, nicht gegen Mocks der zu
beweisenden Eigenschaft: Finding I gegen zwei echte, wegwerfbare lokale
git-Repositories, Finding K gegen echte `os.replace`-Zustände auf dem echten
Dateisystem und echte OS-Locks unter konkurrierenden Threads, Finding J gegen
die real erzeugte Dockerfile-/Container-Skript-Ausgabe.

### Finding I — Source-Authority (`RootFindingISourceAuthorityTests`, 6 Tests)

| Prompt-RED-Proof | Test | Ergebnis |
| --- | --- | --- |
| 1–4 Repo A, dann `--repo B` + nur in B existierender Full-SHA; Checkout **und** reale Fetch-Authority danach B | `test_reused_checkout_from_another_repo_is_reclaimed_for_the_requested_one` | PASS |
| 5 Fingerprint / describe / realer Checkout: eine Authority | `test_fingerprint_describe_and_checkout_agree_on_the_same_authority` | PASS |
| 6 Reuse-Hit braucht gar keinen Checkout | `test_reuse_hit_needs_no_checkout_at_all_regression` | PASS |
| Guard macht keinen Neuklon bei passender Authority | `test_matching_authority_still_reuses_the_existing_checkout` | PASS |
| Unidentifizierbarer Checkout wird nie vertraut | `test_a_checkout_without_a_readable_origin_is_never_trusted` | PASS |
| Nur kosmetische Schreibweisen gefaltet | `test_authority_comparison_folds_only_cosmetic_spellings` | PASS |

### Finding J — Windows-Toolchain-Authority (`RootFindingJWindowsToolchainAuthorityTests`, 9 Tests)

| Prompt-RED-Proof | Test | Ergebnis |
| --- | --- | --- |
| 1 konkrete immutable Authority statt `definedBy: upstream-revision+patch-set` | `test_windows_fingerprint_names_a_concrete_immutable_authority` | PASS |
| 2 Änderung der Authority ändert den Fingerprint | `test_changing_any_pinned_input_changes_the_windows_fingerprint` (11 Subtests, je ein Vertreter pro Input-Klasse) | PASS |
| 3 keine availability-basierte OpenSSL-Auswahl | `test_generated_windows_build_has_no_availability_based_openssl_choice` | PASS |
| 4 OpenSSL gegen deklarierten SHA-256 geprüft, vor Verwendung | `test_generated_windows_build_verifies_openssl_against_a_declared_hash` | PASS |
| 5 mutable Base-Image-/Packaging-Inputs geschlossen (inkl. openfst) | `test_generated_windows_build_closes_the_mutable_image_inputs` | PASS |
| 6 `fingerprint_for()`/`describe_artifact()` bleiben offline | `test_describe_and_fingerprint_stay_offline_for_windows` | PASS |
| 7 normale VoiceSTT-/Versionsänderungen bewegen den Fingerprint nicht | `test_ordinary_voicestt_changes_still_leave_the_windows_fingerprint_alone` | PASS |
| Deklaration ist einzige Quelle des generierten Builds | `test_declared_pins_are_the_only_source_of_the_generated_build` | PASS |
| Nicht anwendbarer Pin scheitert laut | `test_a_missing_upstream_anchor_fails_loudly` | PASS |

Zu RED-Proof 6: der Test patcht `install_kroko.run`, `subprocess.run`,
`subprocess.check_output` und `prepare_checkout` und beweist, dass **keiner**
davon während einer Windows-Fingerprint-Berechnung aufgerufen wird — die
Offline-Eigenschaft ist damit belegt, nicht behauptet.

### Finding K — crash-atomarer Swap (`RootFindingKCrashAtomicSwapTests`, 9 Tests)

| Prompt-RED-Proof | Test | Ergebnis |
| --- | --- | --- |
| 1+2 Abbruch zwischen den Moves; nächster Lookup stellt das Last-Known-Good ohne Native-Rebuild bereit | `test_known_good_artifact_survives_a_kill_between_the_two_moves` | PASS |
| 2 (End-to-End) Lauf nach dem Crash startet keinen Build | `test_a_run_after_the_crash_reuses_instead_of_rebuilding` | PASS |
| 3 Abbruch nach dem zweiten Move: neues final bleibt aktiv, Backup wird bereinigt | `test_crash_after_the_second_move_keeps_the_new_artifact_and_cleans_up` | PASS |
| 4 korruptes Backup wird nie aktiviert | `test_a_corrupt_backup_is_never_activated` | PASS |
| 4 fremdes Backup wird nie aktiviert | `test_a_foreign_backup_is_never_activated` | PASS |
| 5 zwei gleichzeitige Recovery-Aufrufer, genau ein gültiger Slot | `test_two_concurrent_recoverers_converge_on_one_valid_slot` | PASS |
| 6 `--rebuild-kroko` unverändert | `test_force_rebuild_semantics_are_unchanged_regression` | PASS |
| `store()` sieht nach dem Crash den realen Slot-Zustand | `test_store_recovers_before_deciding_what_to_adopt` | PASS |
| gesunder Slot nimmt den Recovery-Lock nicht | `test_healthy_slot_never_takes_the_recovery_lock` | PASS |

Die Crash-Simulation führt exakt dieselben `os.replace`-Operationen aus, die
`store()` ausführt, und hält dazwischen an — also genau der On-Disk-Zustand, den
ein harter Kill hinterlässt. Der OS-Lock ist dabei frei, wie nach einem
Prozessende.

---

## 2. Alle C1-/C2-Kroko-Tests weiterhin grün

```text
python -m pytest -q \
  tests/unit/test_kroko_fingerprint.py \
  tests/unit/test_kroko_artifact_store.py \
  tests/unit/test_kroko_onnx_engine.py \
  tests/unit/test_kroko_model_authority.py \
  tests/unit/test_install_kroko_cpu.py

193 passed, 1 skipped, 74 subtests passed
```

Darin unverändert grün und für C3 besonders relevant:
`RootHardeningConcurrentSlotAccessTests` (concurrent store, Lock-Exklusivität),
`RootFindingHCrashRecoverableLockTests` (crash-recoverable Lock, force rebuild),
`RootFindingFPristineCheckoutTests` (pristine checkout),
`RootFindingELinuxCapabilityIsolationTests` und `SecretLeakageTests`
(Free/Pro-Grenze und Secret-Boundary aus C1/C2).

---

## 3. Guard-Negativtests

Beide geguardeten Surfaces wurden **erweitert, nicht abgeschwächt**:

* Patch-Surface `+ _pinned_windows_dockerfile_edits`,
  `+ _pinned_windows_openssl_block`, `+ _packaging_tool_assertion`
* Builder-Surface `+ checkout_origin_url`, `+ normalize_repo_authority`,
  `+ checkout_matches_repo_authority`

Negative Verifikation durch simulierte buildwirksame Drift
(`evidence_artifacts/2026-09-01_W4A_C3_guard_negative_verification.txt`):

```text
GUARD: patch surface (_pinned_windows_openssl_block: a different OpenSSL package)
  simulated build-effective drift -> exit=1: 1 failed
  restored                        -> exit=0: 1 passed
GUARD: builder surface (checkout_matches_repo_authority: authority check weakened)
  simulated build-effective drift -> exit=1: 1 failed
  restored                        -> exit=0: 1 passed
```

`VoiceSTT/install_kroko.py` wurde vor und nach dem Verfahren gehasht und ist
byte-identisch (`9b2d7099ca0139c1dedbb1b26061fc49772cf185473a110eee903cfd99573189`).

Deklarierte Revisionen und Digests final:

| Konstante | Wert |
| --- | --- |
| `PATCH_SET_REVISION` | `2` |
| `BUILDER_REVISION` | `4` |
| `EXPECTED_PATCH_SOURCE_DIGEST` | `17cbc1dd927d74fc10477579a9475920d0ebfa7df8ddb777d92344aa07e183b5` |
| `EXPECTED_BUILDER_SOURCE_DIGEST` | `4df7ea655259e01e9e1443212d427c9f82c9b98738a0ce0853402923e502b705` |

Dass die neuen Windows-Toolchain-Konstanten echte Fingerprint-Inputs sind, ist
per Subtest pro Input-Klasse bewiesen (Abschnitt 1, Finding J, RED-Proof 2).

---

## 4. `git diff --check`

Sauber (keine Whitespace-Fehler, keine Konfliktmarker).

---

## 5. Kompletter Projekt-Regressionstest gegen den finalen C3-Stand

```text
python -m pytest -q --basetemp=...\w4a-c3-pytest-final

1 failed, 1431 passed, 14 skipped, 934 subtests passed in 562.12 s (0:09:22)
```

Netto gegenüber dem C2-Endstand (`1408 passed, 901 subtests`): **+23 Tests und
+33 Subtests**, das entspricht exakt den in Abschnitt 1 aufgeführten neuen
Tests (6 + 9 + 9 = 24 Testmethoden, davon eine — der Reuse-Hit-Regressionstest —
in einer bestehenden Klasse gezählt) plus deren Subtests.

### Der eine Fehlschlag: vorbestehend, C3-fremd, und heute fällig geworden

```text
FAILED tests/unit/test_fastapi_server_multi_user.py::
       FastAPIMultiUserWebSocketTests::test_admin_replay_reports_retention_gap
       AssertionError: 6 != 0   (hello["retentionCursor"], Zeile 1976)
```

**Schritt 1 — nicht durch C3 verursacht.** Der Parent-Commit
`c8db0f5687dc535e0fe9974fba0445b8fd10f2e1` wurde mit `git archive` in ein
separates Verzeichnis exportiert (ohne Mutation des Repositories und ohne einen
Worktree anzulegen) und derselbe Test dort isoliert ausgeführt:

```text
tests\unit\test_fastapi_server_multi_user.py:1976: AssertionError: 6 != 0
1 failed
```

Identische Zeile, identischer Wert — der Fehlschlag existiert also bereits im
W4A-C2-Endstand.

**Schritt 2 — warum C2 dann `0 Fehlschläge` melden konnte.** Der C2-Testreport
ist nicht falsch: der Test ist **kalenderabhängig**. Die Fixture legt ein
Ereignis mit dem *absoluten* Zeitstempel `2026-08-02T00:00:00.000Z` an und setzt
danach ein Retention-Fenster von 30 Tagen. `EventStore._prune_if_due()`
(`VoiceSTT_server/event_logging.py`) berechnet den Cutoff als
`datetime.now(timezone.utc) - timedelta(days=days)`, also relativ zur echten
Uhr. Das Ereignis liegt damit genau bis zum 2026-09-01 innerhalb des Fensters
und ab dem 2026-09-01 außerhalb; sobald es geprunt wird, entsteht für
`(transcription, session-b)` ein Retention-Watermark, und der erwartete
`retentionCursor == 0` wird zu `6`.

**Schritt 3 — empirisch verifiziert, nicht bloß hergeleitet.** Derselbe Test
wurde zweimal gegen denselben Code ausgeführt, wobei ausschließlich die vom
Event-Store gesehene Uhr eingefroren wurde:

```text
fixture session-b timestamp : 2026-08-02T00:00:00+00:00
declared retention window   : 30 days

clock 2026-08-31 (the day W4A-C2 ran)
  retention cutoff        : 2026-08-01T12:00:00+00:00
  fixture event inside?   : True
  test outcome            : PASS (0 failures, 0 errors)

clock 2026-09-01 (today)
  retention cutoff        : 2026-08-02T12:00:00+00:00
  fixture event inside?   : False
  test outcome            : FAIL (1 failures, 0 errors)
```

(Evidence: `evidence_artifacts/2026-09-01_W4A_C3_retention_test_time_dependency.txt`.)

Damit ist die Ursache eindeutig: eine latente Zeitbombe in der Test-Fixture, die
einen Tag nach dem C2-Lauf fällig wurde. Sie liegt in der FastAPI-/
Event-Logging-Testsuite, nicht im Produktcode, und hat mit Kroko Builder,
Fingerprint oder Artifact Store nichts zu tun.

**Warum sie hier nicht behoben wird.** Die Korrektur wäre klein (den
Fixture-Zeitstempel relativ zu `now` erzeugen statt absolut), fällt aber
eindeutig außerhalb des C3-Scopes: §7 des Prompts erlaubt ausschließlich Kroko
Builder / Fingerprint / Artifact Store, die zugehörige Buildinput-Authority,
deren direkte Tests und minimale Kroko-Builddoku, und schließt allgemeine
Server-Refactorings ausdrücklich aus. Der Punkt wird daher unverändert und
vollständig diagnostiziert als offener, C3-fremder Befund weitergereicht.

**Empfohlene Behebung (für ein eigenes Arbeitspaket):** in
`test_admin_replay_reports_retention_gap` den Zeitstempel des
`retention-transcription-session-b`-Ereignisses relativ zur aktuellen Zeit
erzeugen (z. B. `now - timedelta(days=1)`), damit die Aussage des Tests — „ein
Ereignis innerhalb des Retention-Fensters erzeugt kein Watermark" — nicht vom
Kalenderdatum des Laufs abhängt. Dieselbe Prüfung sollte für die übrigen
absoluten Zeitstempel dieser Suite erfolgen.

---

## 6. Secret-/Capability-Scan

`2026-09-01_W4A_C3_SECRET_SCAN.txt`. Ergebnis: keine Treffer im Diff, keine
Secret-Felder in den Fingerprint-Dokumenten (43 Leaf-Felder je Variante
einzeln geprüft), keine in den Artifact-Metadaten, keine in der Evidence.

---

## 7. Realer Native-Build, persistenter Store, echter Reuse, Installation

Siehe `2026-09-01_W4A_C3_REAL_ARTIFACT_QUALIFICATION.md`. Kurz:

| Gate | Ergebnis |
| --- | --- |
| frischer echter Free-Native-Build gegen finalen C3-Code | OK (genau **ein** nativer Build, keine Wiederholungsschleife) |
| kein Stub / kein synthetisches / kein fremdes Wheel | OK |
| persistenter, nicht temporärer Store | `C:\Users\user\AppData\Local\VoiceSTT\kroko-artifacts` |
| SHA-256 / Bytes | `cdaa28193366c21d21b6f59e73cd0733fd59ba3eba6a471d540ba11a34f48f38` / `12549999` |
| Fingerprint + vollständige Inputs | `b2483a5a5c488f59`, Authority `5c93d37146d3dd23` |
| echter REUSE ohne Native-Build | OK (0,34 s; Docker-Container und -Images unverändert) |
| Install / Import / `verify_installed_runtime("free")` | OK |
| Pro-Negativprobe lehnt ab | OK |
| disposable venv entfernt, Artifact behalten | OK |

---

## 8. Scope-/Hygiene-Nachweis

Geänderte Dateien: `VoiceSTT/install_kroko.py`, `VoiceSTT/kroko/artifacts.py`,
`VoiceSTT/kroko/buildinputs.py`, `VoiceSTT/kroko/fingerprint.py`,
`docs/engines/kroko-onnx.md`, `tests/unit/test_kroko_artifact_store.py`,
`tests/unit/test_kroko_fingerprint.py`.

Kein W4B, kein W4C, kein Client-Code, keine Wakeword-Architektur, keine
allgemeinen Server-Refactorings. Es wurde **kein** neues persistentes venv
angelegt; die Install-Probe lief in einer wegwerfbaren Umgebung außerhalb des
Worktrees, die danach entfernt wurde.
