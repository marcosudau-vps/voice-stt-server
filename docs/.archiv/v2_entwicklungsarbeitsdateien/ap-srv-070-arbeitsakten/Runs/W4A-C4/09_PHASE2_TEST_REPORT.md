# AP-SRV-070 / W4A-C4 — Phase 2: Testbericht

## 1. Ausgeführte Testbefehle und Ergebnisse

### 1.1 Targeted Test Gate

```bash
python -m pytest -q tests/unit/test_fastapi_server_multi_user.py -k "retention_gap or retention" --basetemp=C:\Users\user\AppData\Local\Temp\pytest-c4-test
```
**Ergebnis:** `2 passed, 52 deselected in 1.58s` (Exit Code 0)
- `FastAPIMultiUserWebSocketTests.test_admin_replay_reports_retention_gap`: **PASS** (erfolgreich am 2026-09-01)
- `FastAPIMultiUserWebSocketTests.test_inside_retention_timestamp_fixture_is_future_proof`: **PASS** (geprüft für 2026-09-01 und 2036-09-01)

```bash
python -m pytest -q tests/unit/test_kroko_artifact_store.py --basetemp=C:\Users\user\AppData\Local\Temp\pytest-c4-test
```
**Ergebnis:** `83 passed in 14.85s` (Exit Code 0)
- `RootFindingKCrashAtomicSwapTests.test_concurrent_lookup_during_store_swap_never_returns_miss`: **PASS** (Finding N Concurrency-Beweis)
- `RootFindingKCrashAtomicSwapTests.test_healthy_slot_never_takes_the_recovery_lock`: **PASS** (Lock-Free Hit Proof, `_slot_lock.assert_not_called()`)
- Alle 81 weiteren Artifact-Store-Tests: **PASS**

```bash
python -m pytest -q tests/unit/test_kroko_fingerprint.py --basetemp=C:\Users\user\AppData\Local\Temp\pytest-c4-test
```
**Ergebnis:** `67 passed, 86 subtests passed in 0.36s` (Exit Code 0)
- `RootFindingLMWindowsToolchainAuthorityTests`:
  - `test_xwin_declaration_contains_complete_c3_reconstructed_authority`: **PASS** (10.1 Declaration)
  - `test_changing_any_manifest_or_sdk_crt_input_invalidates_fingerprint`: **PASS** (10.2 Invalidation, 7 Subtests)
  - `test_generated_dockerfile_downloads_and_verifies_manifests_and_invokes_pinned_xwin`: **PASS** (10.3 Generated Dockerfile)
  - `test_missing_xwin_anchor_raises_kroko_install_error`: **PASS** (10.5 Negative Proof Anchor)
  - `test_manifest_sha_mismatch_would_fail_verification`: **PASS** (10.5 Negative Proof Hash)
- `BuildEffectiveLogicGuardTests`:
  - `test_patch_set_matches_its_declared_revision`: **PASS** (`EXPECTED_PATCH_SOURCE_DIGEST` matches `PATCH_SET_REVISION = 3`)
  - `test_builder_surface_matches_its_declared_revision`: **PASS**
  - `test_both_declared_revisions_are_fingerprint_inputs`: **PASS**
- `RootFindingJWindowsToolchainAuthorityTests`:
  - `test_describe_and_fingerprint_stay_offline_for_windows`: **PASS** (10.4 Offline Gate)

### 1.2 Gesamte Kroko-W4A-Testgruppe

```bash
python -m pytest -q \
  tests/unit/test_kroko_fingerprint.py \
  tests/unit/test_kroko_artifact_store.py \
  tests/unit/test_kroko_onnx_engine.py \
  tests/unit/test_kroko_model_authority.py \
  tests/unit/test_install_kroko_cpu.py \
  --basetemp=C:\Users\user\AppData\Local\Temp\pytest-c4-test
```
**Ergebnis:** `208 passed, 1 skipped, 118 subtests passed in 15.56s` (Exit Code 0)

### 1.3 `git diff --check`

```bash
git diff --check
```
**Ergebnis:** Exit Code 0 (Keine Whitespace-Fehler, keine Konfliktmarker).

## 2. Neue Tests

1. `tests/unit/test_fastapi_server_multi_user.py`:
   - `test_inside_retention_timestamp_fixture_is_future_proof`:
     Beweist für Referenzdaten `2026-09-01` und `2036-09-01`, dass der erzeugte Timestamp echt innerhalb des 30-Tage-Fensters (`> now - 30 days`) und echt vor `now` (`< now`) liegt.
2. `tests/unit/test_kroko_artifact_store.py`:
   - `test_concurrent_lookup_during_store_swap_never_returns_miss`:
     Beweist über Threading-Events und `os.replace`-Hook deterministisch, dass ein während eines Force-Swaps gestarteter `lookup(recover=True)` am Slot-Lock wartet und nach dem Swap das neue Artefakt (keinen MISS) liefert.
   - `test_healthy_slot_never_takes_the_recovery_lock`:
     Erweitert um `slot_lock.assert_not_called()`, um die Lock-Freiheit des gesunden Pfades direkt zu belegen.
3. `tests/unit/test_kroko_fingerprint.py`:
   - `RootFindingLMWindowsToolchainAuthorityTests.test_xwin_declaration_contains_complete_c3_reconstructed_authority`:
     Prüft alle Manifest-URLs, Dateinamen, Bytezahlen, SHA-256-Hashes, SDK-Version (`10.0.26100`) und CRT-Version (`14.44.17.14`).
   - `RootFindingLMWindowsToolchainAuthorityTests.test_changing_any_manifest_or_sdk_crt_input_invalidates_fingerprint`:
     Mutiert jede einzelne der 7 neuen Authority-Eingaben isoliert und beweist die Ungleichheit von Toolchain-Authority und Fingerprint-Dokument.
   - `RootFindingLMWindowsToolchainAuthorityTests.test_generated_dockerfile_downloads_and_verifies_manifests_and_invokes_pinned_xwin`:
     Beweist die generierten Download-, Bytezahl-, Hash- und `xwin`-Aufrufzeilen im Dockerfile.
   - `RootFindingLMWindowsToolchainAuthorityTests.test_missing_xwin_anchor_raises_kroko_install_error`:
     Beweist, dass ein fehlender Upstream-xwin-Block hart zu `KrokoInstallError` führt (kein stiller Fallback).
   - `RootFindingLMWindowsToolchainAuthorityTests.test_manifest_sha_mismatch_would_fail_verification`:
     Beweist, dass eine Abweichung im Channel-Manifest-SHA im Dockerfile zur Zurückweisung via `sha256sum -c` führt.

## 3. Guard-Negativproof

- **Negativtest (Guard RED):**
  Vor der Aktualisierung von `EXPECTED_PATCH_SOURCE_DIGEST` in `test_kroko_fingerprint.py` schlug `test_patch_set_matches_its_declared_revision` mit `AssertionError` fehl:
  `'70d8bacbe95c358e532db9ce1b6127d2aa575ff7724b90464a5aec71b7387c80' != '17cbc1dd927d74fc10477579a9475920d0ebfa7df8ddb777d92344aa07e183b5'`.
  Damit wurde bewiesen, dass jede Änderung an `_pinned_windows_dockerfile_edits` ohne deliberate Revision und Digest-Aktualisierung den Test rot färbt.
- **Positivtest (Guard GREEN):**
  Nach dem Pinnen von `PATCH_SET_REVISION = 3` und dem Eintrag des neuen Digests ist der Guard grün (`test_patch_set_matches_its_declared_revision` PASSED).

## 4. Skips und Begründung

- In der Testgruppe wurde exakt **1 Test** übersprungen:
  - `tests/unit/test_install_kroko_cpu.py:test_real_linux_build_is_reproducible_byte_for_byte_when_rerun`:
    `skipped: Docker not available or Linux builder not runnable on this host`.
    Dieser Skip ist unter Windows standardmäßig aktiv und erwartungskonform (bereits in W4A-C1 bis C3 identisch dokumentiert).
- Alle übrigen 208 Tests der W4A-Gruppe liefen erfolgreich durch.
