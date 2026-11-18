# W5-R04 — 06 Test Matrix

Final-tree verification and test execution record for run W5-R04.

---

## 1. Tested-Tree Identity

| Item | Value |
| --- | --- |
| Final Commit SHA | `40a6eee93102b8355067973e94368b55ed2bf049` |
| Superseded Commit SHAs | `5a87ad837a9f078c59a37bd7a1e1134b59117a97` (rejected by 1st external Root Review: B1–B4, E1)<br>`202bedadd4a2448e7ab11fb11b2567053b46a2e1` (rejected by 2nd external Root Review: B5, B6) |
| Final Tree SHA | `7aa37473f44dcf39587c33dc3cde1fe0caed7ed0` |
| Direct Parent SHA | `934e3be7c78aa9358f9b42b9fa4dc282bed54d6c` (exact start commit) |
| Corrected Final Diff SHA256 | `F16F5BBB296DCB32B6030A06B6FB528F2F428C17B812D1B6783286CCE8DEC3D8` |
| Changed Files Count | 70 files changed (52 modified/renamed/deleted, 18 added) |
| Diffstat | 70 files changed, 9508 insertions(+), 3526 deletions(-) |
| Workspace State | Literally clean (`git status --porcelain=v1` empty) |
| Remote Branch State | `origin/feat/einheitliche-triggerarchitektur-distributed` unchanged at `934e3be7c78aa9358f9b42b9fa4dc282bed54d6c` |
| Temporary Review Branch | `review/ap-srv-070-w5-r04-root` at `40a6eee93102b8355067973e94368b55ed2bf049` (authorized dirty review push) |

---

## 2. Targeted Test Suites (G61 – G64)

### 2.1 W5R4-G61: Release Tooling Targeted Tests

- **Command:**
  ```powershell
  python -m pytest -q --basetemp=P:\tmp\pt_rel_all (Get-ChildItem tests/unit/test_release_*.py, tests/unit/test_build_*.py)
  ```
- **Execution Time:** 15.07s
- **Result:** **350 passed, 225 subtests passed, 0 failures, 0 errors** (PASS)
- **Scope Covered:** Release engine state transitions, adapter barriers, fail-closed enforcement, SemVer alias resolution, candidate manifest schema v2 validation (with multi-platform REQUIRED_PLATFORMS), preflight checks (enforcing QUALIFIED and candidate version matching), pipeline wiring, credential redaction at boundaries, remote registry checks with current PyPI `urls` shape (B5), precheck-pypi read-only conflict check, WindowsCandidateBuildTests.

### 2.2 W5R4-G62: Build and Kroko Targeted Tests

- **Command:**
  ```powershell
  python -m unittest tests/unit/test_build_distribution.py tests/unit/test_build_production.py tests/unit/test_kroko_fingerprint.py tests/unit/test_production_docker_contract.py tests/unit/test_kroko_artifact_store.py tests/unit/test_install_kroko_cpu.py
  ```
- **Execution Time:** 18.730s
- **Result:** **191 passed, 0 failures, 0 errors** (PASS)
- **Scope Covered:** Distribution packaging (`tools/build_distribution.py`), wheel rewriting/retagging, Dockerfile contract, Kroko build fingerprinting, store reuse/isolation, Windows CPU build script validation.

### 2.3 W5R4-G63: Workflow / YAML / Permission / Trigger Guard Tests

- **Command:**
  ```powershell
  python -m unittest tests/unit/test_release_workflows.py
  ```
- **Execution Time:** 0.96s
- **Result:** **41 passed (158 subtests), 0 failures, 0 errors** (PASS)
- **Scope Covered:** YAML schema validity, read-only permissions across `ci.yml`, workflow dispatch isolation, protected `release` environment bindings, OIDC `id-token: write` isolation to PyPI job only, commit-SHA pinned GitHub Actions, `actions: read` for all cross-run artifact downloads (B1), `contents: read` for checkout jobs, multi-platform candidate workflow structure (B2), candidate manifest version validation against workflow input `version` before tag creation (B6).

### 2.4 W5R4-G64: Documentation and Link Guard Tests

- **Command:**
  ```powershell
  python -m unittest tests/unit/test_docs_surface.py
  ```
- **Execution Time:** 0.113s
- **Result:** **30 passed, 0 failures, 0 errors** (PASS)
- **Scope Covered:** Public documentation surface honesty, deletion of `docs/engines/` directory, presence and relocation of `faster-whisper.md` and `kroko-onnx.md` to `docs/`, no broken relative markdown links across all maintained documents, README distribution/import/CLI assertions.
- **Evidence Log:** `Evidence/07_Documentation/docs_surface.log`

---

## 3. Full Regression Suites (G65, G66)

### 3.1 W5R4-G65: Windows Full Regression (Final Tree)

- **Environment:** Windows 11, CPython 3.12.8 x64, pytest 8.3.4
- **Working Directory:** `P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-070-w5-r04`
- **Basetemp:** `P:\tmp\pt_w5r4_final`
- **Command:**
  ```powershell
  python -m pytest -q --basetemp=P:\tmp\pt_w5r4_final tests/unit
  ```
- **Execution Time:** 677.19s (11m 17s)
- **Result:** **1930 passed, 14 skipped, 1244 subtests passed, 0 failures** (PASS)
- **Evidence Log:** `Evidence/08_WindowsRegression/unit_full_final_tree.log`

### 3.2 W5R4-G66: Ubuntu 24.04 Full Regression (Final Tree)

- **Environment:** Ubuntu 24.04 LTS (WSL2), Linux 6.6.x x86_64, native ext4 filesystem
- **Python Binary:** `/home/marco/w5r02c1-ubuntu-test/bin/python` (CPython 3.12.3, pytest 9.1.1, fastapi 0.141.1)
- **Source Copy:** `/home/marco/w5r04-native-src` (refreshed via `rsync -av --delete` from current worktree)
- **Command:**
  ```bash
  cd /home/marco/w5r04-native-src && /home/marco/w5r02c1-ubuntu-test/bin/python -m pytest -q tests/unit
  ```
- **Execution Time:** 417.37s (6m 57s)
- **Result:** **1930 passed, 14 skipped, 4 warnings, 1244 subtests passed, 0 failures** (PASS)
- **Evidence Log:** `Evidence/09_UbuntuRegression/unit_full_final_tree.log`

---

## 4. Diff, Scope and Security Verification (G67 – G69)

### 4.1 W5R4-G67: `git diff --check`

- **Command:**
  ```powershell
  git diff --check 934e3be7c78aa9358f9b42b9fa4dc282bed54d6c..40a6eee93102b8355067973e94368b55ed2bf049
  ```
- **Result:** **PASS** (0 whitespace errors, conflict markers, or carriage-return issues)
- **Evidence Log:** `Evidence/10_Security/diff_check.txt`

### 4.2 W5R4-G68: Secret, Large-Binary, and Scope Review

- **Binary/Size Check:** All 70 modified/added files inspected; 0 files exceed 500 KB; 0 compiled wheels, native binaries, `.env` files, or model archives committed.
- **Secret Scan:** Diff scanned for PATs, API keys, private keys, AWS/PyPI tokens. Only synthetic test strings in mocks and link/secret regex guards exist.
- **Scope Compliance:** Changes strictly confined to release infrastructure, packaging tooling, GitHub workflows, tests, and documentation.
- **Result:** **PASS**
- **Evidence Log:** `Evidence/10_Security/scope_review.txt`

### 4.3 W5R4-G69: Exact Full Diff Archive

- **Pre-commit Patch:** `Evidence/11_Diff/corrected_final_diff.patch`
- **Diffstat Record:** `Evidence/11_Diff/staged_final_diffstat.txt`
- **Diff Hash:** `F16F5BBB296DCB32B6030A06B6FB528F2F428C17B812D1B6783286CCE8DEC3D8` (SHA256)
- **Result:** **PASS**
