# AP-SRV-070 — W4A-C2 — Test Report

**Datum:** 2026-08-31

---

## 1. Neue/geänderte Tests je Finding

| Datei | Vorher (C1-Endstand) | Nachher | Neu |
|---|---|---|---|
| `tests/unit/test_kroko_fingerprint.py` | 37 | 44 | +7 (Finding G) |
| `tests/unit/test_kroko_artifact_store.py` | 48 | 67 | +19 (Findings E, F, H) |

**Summe neu für C2: 26 Tests.**

## 2. RED-first-Nachweis je Finding

### Finding E (Capability-Isolation)
`RootFindingELinuxCapabilityIsolationTests` (6 Tests). Vor der Korrektur hätte
`test_ambient_license_on_does_not_survive_a_free_build` fehlgeschlagen: ein
geerbtes `KROKO_LICENSE=ON` überlebte in `linux_build_env("free")`
unverändert, weil nur der `pro`-Zweig den Wert explizit setzte.

### Finding F (Pristine Checkout)
`RootFindingFPristineCheckoutTests` (7 Tests, echte temporäre Git-Repos). Vor
der Korrektur hätte `test_prepare_checkout_restores_a_tracked_file_modified_by_a_previous_patch_run`
fehlgeschlagen: `prepare_checkout()` prüfte nur die Commit-Identität
(`ensure_pinned_revision`), ließ eine bereits gepatchte tracked Datei aber
unverändert im Checkout stehen.

### Finding G (Linux-Toolchain-Vollständigkeit)
`RootFindingGCxxToolchainTests` (5 Tests) + `RootFindingGPreInstalledOnnxRuntimeTests`
(2 Tests). Vor der Korrektur hätte `test_identity_declares_a_separate_cxx_compiler_field`
fehlgeschlagen (kein `cxxCompilerPath`/`cxxCompilerVersion` in der
Toolchain-Identity), und `test_declared_linux_cmake_flags_disable_the_pre_installed_onnxruntime_default`
hätte fehlgeschlagen, weil der deklarierte Flag-String das Upstream-Default
(`ON`) nicht überschrieb.

### Finding H (Crash-Recoverable Lock)
`RootFindingHCrashRecoverableLockTests` (6 Tests). Vor der Korrektur hätte
`test_orphaned_lock_is_reacquirable_without_manual_cleanup` fehlgeschlagen:
das alte `O_CREAT|O_EXCL`-Locking erkennt nur `FileExistsError` und wartet
den vollen Timeout aus, weil die Dateiexistenz selbst als Sperre galt. Der
stärkste Nachweis, `test_orphaned_lock_after_a_real_killed_subprocess`,
verwendet einen echten, separat gestarteten und hart abgebrochenen
OS-Prozess statt einer Simulation im selben Prozess.

## 3. Guard-Erweiterung (`BuildEffectiveLogicGuardTests`)

Die bewachte Builder-Fläche wuchs von 12 auf 13 Funktionen: `materialize_pristine_checkout`
kam hinzu, weil eine künftige Regression in dieser Funktion (z. B. das
versehentliche Entfernen von `git clean -fdx`) den Fingerprint nicht
automatisch ändern würde, obwohl sie build-wirksam ist.

`BUILDER_REVISION` wurde 2 → 3 angehoben; der Guard-Digest wurde nach dem
finalen Codezustand neu berechnet (`5d4baea1924953743a3c8c9ee083383905f0fc4372f1d47e872f5d44703ada93`)
und **negativ verifiziert**: eine künstliche Drift in `materialize_pristine_checkout`
ließ `test_builder_surface_matches_its_declared_revision` mit der erwarteten
Digest-Mismatch-Meldung fehlschlagen; nach Rücknahme wieder grün (4/4 Tests
der Guard-Klasse).

## 4. Bestehende C1-Tests, die durch die neue Lock-Semantik angepasst werden mussten

Die crash-sichere Lock-Lösung (Finding H) lässt die Lock-Datei absichtlich
dauerhaft bestehen (siehe Root Correction Report §4 — Vermeidung der
Unlink-Race). Drei C1-Assertions, die einen leeren Lock-Ordner erwarteten,
wurden auf die jetzt korrekte Erwartung „genau eine persistente Marker-Datei"
angepasst:

- `test_forced_store_replaces_the_previous_artifact`
- `RootHardeningConcurrentSlotAccessTests::test_concurrent_stores_of_the_same_slot_do_not_corrupt_it`

Zusätzlich verschärft (nicht nur angepasst): `test_free_build_environment_does_not_enable_pro`
prüft jetzt explizit `KROKO_LICENSE == "OFF"` statt nur dessen Abwesenheit
(Finding E macht diese stärkere Aussage erst wahr).

Alle übrigen C1-Tests (inklusive Findings A–D und der ursprünglichen
Hardening-Tests) blieben unverändert grün.

## 5. Während der Verifikation gefundener und behobener Testfehler

Siehe Root Correction Report §7 für die vollständige Herleitung.
`test_orphaned_lock_after_a_real_killed_subprocess` blockierte durch eine
eager ausgewertete `assertEqual`-`msg`-Auswertung (`process.stderr.read()`)
faktisch für die volle `time.sleep(30)`-Dauer des Kindprozesses, **bevor**
der Kill überhaupt ausgeführt wurde — der Test bestand zwar, bewies aber
nicht die beanspruchte prompte Wiedererlangung. Behoben durch Verschieben der
Stderr-Lese­operation hinter eine bedingte `self.fail(...)`-Prüfung.

| Messung | Vorher | Nachher |
|---|---|---|
| `test_orphaned_lock_after_a_real_killed_subprocess` (isoliert) | 30.32 s | 0.28 s |
| `RootHardeningConcurrentSlotAccessTests` + `RootFindingHCrashRecoverableLockTests` (8 Tests) | 31.02 s (3× identisch reproduziert) | 1.03 s |

Kein Produktcode-Fehler; ausschließlich Testinfrastruktur betroffen.

## 6. Regression

| Suite | Ergebnis |
|---|---|
| Alle Kroko-Suiten (`test_kroko_fingerprint.py`, `test_kroko_artifact_store.py`, `test_kroko_model_authority.py`, `test_kroko_onnx_engine.py`, `test_install_kroko_cpu.py`), sauberer Lauf ohne gleichzeitige Host-Last | `169 passed, 1 skipped, 45 subtests passed` |
| Vollständige Regression gegen den finalen C2-Stand | **`1408 passed, 14 skipped, 901 subtests passed`** in 580.87 s (0:09:40) — 0 Fehlschläge. Netto ggü. C1-Endstand (`1382 passed`): exakt +26, entspricht den 26 neuen Tests. |

**Beobachtete, aufgeklärte Flakiness (kein Regressionsbefund):** Ein isolierter
Lauf von `test_kroko_artifact_store.py` allein — parallel zum noch laufenden
Hintergrundprozess der vollständigen Projekt-Regression auf derselben
Maschine — ließ `test_concurrent_stores_of_the_same_slot_do_not_corrupt_it`
einmalig fehlschlagen (dieser Test verwendet einen echten
`threading.Barrier(2)` mit `timeout=10` auf zwei echten OS-Thread-Racern,
siehe Root Correction Report §4/§7 der C1-Vorlage). Fünf sofort anschließende
Wiederholungen desselben Suite-Laufs, sowie ein finaler Lauf nach Abschluss
der Hintergrund-Regression, bestanden alle 5/5 bzw. sauber. Erklärung: reale
Ressourcenkonkurrenz durch die selbst gestartete, parallel laufende
1408-Test-Vollregression auf demselben Host — kein Logikfehler im
Lock-/Store-Mechanismus. Dokumentiert aus Transparenzgründen, konsistent mit
der Praxis dieses Workstreams.

C1-Baseline (vor C2): `1382 passed, 14 skipped, 901 subtests passed`.

## 7. Secret-Scan über Diff/Evidence

Gescannt: `git diff` über alle fünf geänderten Dateien, gefiltert auf
`KROKO_API_KEY`, `KROKO_LICENSE_KEY`, `license[_-]?key`, `secret`, `password`,
`token`, `api[_-]?key` (Groß-/Kleinschreibung ignoriert). Alle Treffer sind
entweder (a) Referenzen auf Umgebungsvariablen-**Namen** (z. B.
`KROKO_LICENSE_KEY_ENV_NAMES`), (b) Dokumentationsprosa, die die
Secret-/Capability-Unterscheidung erklärt, oder (c) ein offensichtlicher
Test-Fixture-Platzhalterwert (`"still-a-secret"`) in einem bereits aus C1
bestehenden Testmuster. Keine echten Secret-Werte im Diff. Siehe
`evidence_artifacts/2026-08-31_W4A_C2_secret_scan.txt`.

## 8. Hygiene

- `git diff --check`: Exit 0.
- Geänderte Dateien ausschließlich: `VoiceSTT/install_kroko.py`,
  `VoiceSTT/kroko/artifacts.py`, `VoiceSTT/kroko/buildinputs.py`,
  `tests/unit/test_kroko_artifact_store.py`, `tests/unit/test_kroko_fingerprint.py`.
  Keine Architekturänderung, kein W4B-Scope, keine Wake-/Server-Änderung.
- `VoiceSTT/kroko/fingerprint.py` unverändert (alle C2-Änderungen laufen über
  `buildinputs.py`-Konstanten und `install_kroko.py`-Logik, die
  `fingerprint.py` automatisch aufgreift).
