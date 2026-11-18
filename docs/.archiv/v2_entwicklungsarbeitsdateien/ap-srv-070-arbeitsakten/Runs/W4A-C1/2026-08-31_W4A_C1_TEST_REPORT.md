# AP-SRV-070 — W4A-C1 — Test Report

**Datum:** 2026-08-31

---

## 1. Neue/geänderte Tests je Finding

| Datei | Vorher | Nachher | Neu |
|---|---|---|---|
| `tests/unit/test_kroko_fingerprint.py` | 25 | 37 | +12 (Findings A, B) |
| `tests/unit/test_kroko_artifact_store.py` | 30 | 48 | +18 (Findings C, D, Hardening, plus 2 gehärtete Bestandstests) |

**Summe neu/verschärft für C1: 30 Tests.**

## 2. RED-first-Nachweis je Finding

### Finding A (Quell-Overrides)
`RootFindingASourceOverrideTests` (5 Tests). Vor der Korrektur hätte
`test_default_and_different_revision_never_share_a_fingerprint` und
`test_default_and_different_repo_never_share_a_fingerprint` fehlgeschlagen,
weil `fingerprint_for()` beide Overrides ignorierte und für alle Eingaben
denselben Fingerprint lieferte.

### Finding B (Linux-Toolchain + Ambient-Overrides)
`RootFindingBLinuxToolchainFingerprintTests` (7 Tests) +
`RootFindingBLinuxBuildEnvTests` (4 Tests). Vor der Korrektur hätte
`test_ambient_compiler_overrides_never_reach_the_build_environment`
fehlgeschlagen (volle `os.environ`-Kopie), ebenso
`test_cmake_args_override_ambient_value_instead_of_appending` (Append- statt
Override-Semantik) und `test_linux_fingerprint_uses_a_probed_toolchain_not_the_generic_placeholder`
(Linux-Identity war der generische Platzhalter).

### Finding C (Secret Boundary)
Der **bestehende** Test `test_pro_build_environment_carries_no_key` prüfte nur
Werte in String-Argumenten, nicht die Abwesenheit der Variablennamen selbst —
genau die vom Prompt benannte Lücke. Verschärft, plus neu:
`test_windows_build_environment_carries_no_key` (Windows-Pfad war vorher für
dieses Szenario komplett ungetestet) und
`test_runtime_key_lookup_outside_the_builder_is_unchanged`.

### Finding D (Wheel-Plattform-Verifikation)
`RootFindingDWheelPlatformVerificationTests` (7 Tests). Vor der Korrektur
hätte `test_windows_wheel_is_rejected_under_linux_inputs` **fehlgeschlagen**
(Miss wäre ein `found is not None` gewesen, weil die alte Prüfung nur den
Python/ABI-Präfix verglich) — das ist exakt das im Prompt beschriebene
Szenario.

### Root Hardening (Concurrency)
`RootHardeningConcurrentSlotAccessTests` (3 Tests). Negativ verifiziert: der
Lock wurde testweise durch `contextlib.nullcontext()` ersetzt;
`test_concurrent_stores_of_the_same_slot_do_not_corrupt_it` schlug daraufhin
**8 von 8 Wiederholungen** fehl (Exception oder abweichender `wheel_sha256`
zwischen den beiden Racern). Nach Rücknahme: durchgehend grün (5/5
Wiederholungen ohne Lock-Änderung geprüft).

## 3. Guard-Erweiterung (`BuildEffectiveLogicGuardTests`)

Die bewachte Builder-Fläche wuchs von 9 auf 12 Funktionen:
`fingerprint_for`, `sanitize_build_subprocess_env`, `windows_build_env` kamen
hinzu, weil ein künftiger Regressionsfehler in genau diesen drei Funktionen
(z. B. „vergisst" `repo=`/`revision=` erneut zu übergeben, oder lässt die
Sanitizer-Funktion wieder eine Env-Var durchrutschen) den Fingerprint **nicht
automatisch** ändern würde — das ist genau die Fehlerklasse, die Findings A
und C beschreiben, und die der Hash-Vergleich „Fingerprint ändert sich bei
Input-Änderung" strukturell nicht abdecken kann.

`BUILDER_REVISION` wurde 1 → 2 angehoben; der Guard-Digest wurde neu berechnet
und **negativ verifiziert**: eine simulierte Änderung in `fingerprint_for`
(zusätzlicher Dict-Key) ließ `test_builder_surface_matches_its_declared_revision`
zuverlässig fehlschlagen; nach Rücknahme wieder grün (4/4 Tests der Guard-Klasse).

## 4. Während der Korrektur gefundener Zusatzfehler (siehe Root Correction Report §5)

Die erste „adopt existing"-Implementierung für Root Hardening hätte
`--rebuild-kroko` unwirksam gemacht. Aufgedeckt durch den bereits bestehenden
Test `test_successful_store_replaces_the_previous_artifact` (jetzt
`test_forced_store_replaces_the_previous_artifact`), der sofort fehlschlug,
sobald `adopt_existing` eingeführt wurde. Behoben durch den
`adopt_existing`-Parameter (Default `True`, `--rebuild-kroko` übergibt
`False`). Zusätzlich neu abgesichert durch
`test_force_rebuild_actually_replaces_the_stored_artifact`, der die
tatsächlich gespeicherten Wheel-Bytes prüft statt nur den
Builder-Aufrufzähler.

## 5. Regression

| Suite | Ergebnis |
|---|---|
| Alle Kroko-Suiten (`test_kroko_fingerprint.py`, `test_kroko_artifact_store.py`, `test_kroko_model_authority.py`, `test_kroko_onnx_engine.py`, `test_install_kroko_cpu.py`) | `143 passed, 1 skipped, 45 subtests passed` |
| Vollständige Regression gegen den finalen C1-Stand | **`1382 passed, 14 skipped, 901 subtests passed`** in 600 s — 0 Fehlschläge. Netto ggü. W4A-Baseline (`1352 passed`): exakt +30, entspricht den 30 neuen/verschärften Tests. |

W4A-Baseline (vor C1): `1352 passed, 14 skipped, 901 subtests passed`.

## 6. Secret-Scan über Diff/Evidence

Gescannt: alle geänderten Dateien (`git diff`) und der komplette
`Runs/W4A-C1/`-Evidence-Ordner, auf die vier Kroko-Key-Sentinel-Namen sowie auf
Literalwerte, die in Tests als Sentinel-Secrets verwendet wurden
(`"kroko-secret-key-should-never-be-stored-4a7f"`). Ergebnis: keine
tatsächlichen Secret-**Werte** gefunden; die Sentinel-Variablen**namen**
selbst tauchen erwartungsgemäß nur im Testcode und in den Docstrings/Kommentaren
auf, die den Schutz beschreiben — nie in einem gespeicherten Artefakt, einer
Fingerprint-Ausgabe oder einem Log. Siehe `evidence_artifacts/2026-08-31_W4A_C1_secret_scan.txt`.

## 7. Hygiene

- `git diff --check`: Exit 0.
- Geänderte Dateien ausschließlich: `VoiceSTT/install_kroko.py`,
  `VoiceSTT/kroko/artifacts.py`, `VoiceSTT/kroko/buildinputs.py`,
  `VoiceSTT/kroko/fingerprint.py`, `tests/unit/test_kroko_artifact_store.py`,
  `tests/unit/test_kroko_fingerprint.py`. Keine Architekturänderung, kein
  W4B-Scope, keine Wake-/Server-Änderung.
