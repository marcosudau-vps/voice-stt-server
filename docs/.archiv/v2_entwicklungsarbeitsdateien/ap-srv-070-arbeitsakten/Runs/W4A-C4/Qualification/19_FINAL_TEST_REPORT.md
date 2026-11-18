# AP-SRV-070 / W4A-C4 — Final Qualification: Test Report

## 1. Testübersicht und Ergebnisse

### 1.1 Focused Test Gate

| Testsuite / Command | Result | Duration |
|---|---|---:|
| `python -m pytest -q tests/unit/test_kroko_fingerprint.py` | **67 passed, 86 subtests passed** | 0.36s |
| `python -m pytest -q tests/unit/test_kroko_artifact_store.py` | **83 passed** | 14.85s |
| `python -m pytest -q tests/unit/test_fastapi_server_multi_user.py -k "retention_gap or retention"` | **2 passed, 52 deselected** | 1.58s |

### 1.2 Kroko-W4A Testgruppe

```powershell
python -m pytest -q `
  tests/unit/test_kroko_fingerprint.py `
  tests/unit/test_kroko_artifact_store.py `
  tests/unit/test_kroko_onnx_engine.py `
  tests/unit/test_kroko_model_authority.py `
  tests/unit/test_install_kroko_cpu.py
```
**Ergebnis:** `208 passed, 1 skipped, 118 subtests passed in 16.79s` (Exit Code 0)
- *Hinweis zum Skip:* `test_real_linux_build_is_reproducible_byte_for_byte_when_rerun` wird unter Windows standardmäßig übersprungen, wenn kein Linux-Docker-Builder auf dem Host aktiv ist.

### 1.3 Full Server Unit Regression

```powershell
python -m pytest -q tests/unit
```
**Ergebnis:** `1448 passed, 14 skipped, 974 subtests passed in 569.17s (0:09:29)` (Exit Code 0)
- **FAILED:** `0`
- `test_admin_replay_reports_retention_gap` ist vollständig grün (am 2026-09-01 ausgeführt).

### 1.4 Git Diff & Whitespace Check

```powershell
git diff --check
```
**Ergebnis:** Exit Code 0 (Keine Whitespace-Fehler, keine Konfliktmarker).

## 2. Zusammenfassung

```text
FOCUSED_TESTS: PASS
KROKO_W4A_TEST_GROUP: PASS
FULL_REGRESSION: PASS
FULL_REGRESSION_FAILURES: 0
GIT_DIFF_CHECK: PASS
```
