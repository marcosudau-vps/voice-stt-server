# AP-SRV-070 / W4AB — Linux Test Portability Fix Report

## 1. Ausgangsbefund: 10 Linux-Failures auf Hermes
Nach der erfolgreichen realen Ubuntu-Kroko-Qualification (alle Produkt- und Runtime-Gates grün) schlugen in `tests/unit/test_kroko_artifact_store.py` 10 Unittests fehl:
1. `StoreAndReuseTests::test_storing_a_wheel_produces_a_verified_artifact`
2. `BuilderReuseFlowTests::test_free_and_pro_rebuilds_never_modify_the_other_variant`
3. `BuilderReuseContinuationTests::test_failed_force_rebuild_keeps_the_existing_artifact`
4. `BuilderReuseContinuationTests::test_force_rebuild_actually_replaces_the_stored_artifact`
5. `RootFindingISourceAuthorityTests::test_reuse_hit_needs_no_checkout_at_all_regression`
6. `RootFindingKCrashAtomicSwapTests::test_a_run_after_the_crash_reuses_instead_of_rebuilding`
7. `RootFindingISourceAuthorityTests::test_a_checkout_without_a_readable_origin_is_never_trusted`
8. `RootFindingISourceAuthorityTests::test_fingerprint_describe_and_checkout_agree_on_the_same_authority`
9. `RootFindingISourceAuthorityTests::test_matching_authority_still_reuses_the_existing_checkout`
10. `RootFindingISourceAuthorityTests::test_reused_checkout_from_another_repo_is_reclaimed_for_the_requested_one`

## 2. Tatsächliche Root Causes und Zuordnung
Es handelte sich um reine Test-Harness- und Portabilitätsprobleme, nicht um Produktcode-Fehler:

- **Ursache A (Hardcodierte Windows-Erwartung):**
  In `StoreAndReuseTests.test_storing_a_wheel_produces_a_verified_artifact` wurde die Erwartung für `wheelTags` hart auf `["cp312-cp312-win_amd64"]` geprüft, obwohl `make_wheel` bereits plattformgerechte Tags (`linux_x86_64`) erzeugte.
- **Ursache B (Fingerprint-Mismatch zwischen Builderpfad und Test-Lookup):**
  `install_kroko.main` berechnet unter Linux die effektive OpenSSL-/Toolchain-Authority ein (`install_kroko.fingerprint_for(args)`). Die Tests riefen für Lookups und Vorbefüllung jedoch isoliert `fingerprint.compute_fingerprint(variant=...)` auf (ohne Toolchain). Dadurch kam es auf Linux zu einem Cache-Miss, der Folgefehler bei `store.lookup(...)` auslöste.
- **Folgefehler (MagicMock Assertion Failures):**
  In `test_reuse_hit_needs_no_checkout_at_all_regression` und `test_a_run_after_the_crash_reuses_instead_of_rebuilding` führte der Cache-Miss dazu, dass `install_kroko.main` den Builder-Pfad betrat und gemockte Methoden unerwartet aufgerufen wurden (`checkout.assert_not_called()`, `builder.assert_not_called()`).
- **Ursache C (Abhängigkeit von globalem Git Default Branch):**
  In `RootFindingISourceAuthorityTests._make_upstream` und `RootFindingFPristineCheckoutTests._make_local_upstream` erzeugte `git init` auf Ubuntu standardmäßig den Branch `master`. Die Tests und `install_kroko` forderten jedoch explizit `branch="main"`, weshalb Checkouts fehlschlugen.

## 3. Durchgeführte Test-Harness-Änderungen
Ausschließlich in `tests/unit/test_kroko_artifact_store.py`:
1. **Ursache A:** `record.metadata["wheelTags"]` wird gegen den dynamisch aus dem Wheel-Dateinamen geparsten Tag (`"{python}-{abi}-{platform}".format(**parsed_wheel)`) geprüft.
2. **Ursache B & Kaskade:**
   - Helper `fingerprint_for(extra_args=())` in `BuilderReuseFlowTests` und `BuilderReuseContinuationTests` eingeführt, der `install_kroko.fingerprint_for(parse_args(...))` verwendet.
   - In `test_free_and_pro_rebuilds_never_modify_the_other_variant`, `test_force_rebuild_actually_replaces_the_stored_artifact` und `test_failed_force_rebuild_keeps_the_existing_artifact` auf `self.fingerprint_for()` umgestellt.
   - In `test_reuse_hit_needs_no_checkout_at_all_regression` und `RootFindingKCrashAtomicSwapTests.setUp` / `test_a_foreign_backup_is_never_activated` die Fingerprint-Generierung auf `install_kroko.fingerprint_for(args)` umgestellt.
3. **Ursache C:** In `_make_upstream` und `_make_local_upstream` wird der Branch über `git init -b main` (bzw. Fallback `git branch -M main`) deterministisch auf `main` gesetzt.

## 4. Bestätigung Produktcode-Integrität
```text
PRODUCT_CODE_CHANGED: NO
```
Keine Datei außerhalb von `tests/unit/test_kroko_artifact_store.py` wurde verändert.

## 5. Lokale Windows-Testergebnisse
- `python -m pytest -q tests/unit/test_kroko_artifact_store.py`:
  **91 passed** in 17.85s (0 failed, 0 errors)
- `python -m pytest -q tests/unit/test_install_kroko_cpu.py tests/unit/test_kroko_artifact_store.py tests/unit/test_kroko_fingerprint.py`:
  **169 passed, 86 subtests passed** in 19.44s (0 failed, 0 errors)
