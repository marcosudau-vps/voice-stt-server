READY FOR ROOT REVIEW

# W5-R04 — 09 Final Report

Final closure report for AP-SRV-070 Phase W5 (Run W5-R04).

---

## 1. Run Identity & Repository Coordinates

| Item | Value |
| --- | --- |
| Final Status | **READY FOR ROOT REVIEW** |
| Run Identifier | AP-SRV-070 / W5-R04 (Gemini 3.8 Flash Final Root Correction B5 + B6) |
| Workspace | `P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-070-w5-r04` |
| Working Branch | `work/ap-srv-070-w5-r04` |
| Start / Binding Parent Commit SHA | `934e3be7c78aa9358f9b42b9fa4dc282bed54d6c` |
| Start Tree SHA | `2936f70ca44b7a902e1e5c7c5ca69eacc3154fdb` |
| Superseded Local Commit SHAs | `5a87ad837a9f078c59a37bd7a1e1134b59117a97` (rejected by 1st Root Review: B1–B4, E1)<br>`202bedadd4a2448e7ab11fb11b2567053b46a2e1` (rejected by 2nd Root Review: B5, B6) |
| Corrected Final Commit SHA | `40a6eee93102b8355067973e94368b55ed2bf049` |
| Corrected Final Tree SHA | `7aa37473f44dcf39587c33dc3cde1fe0caed7ed0` |
| Direct Parent SHA | `934e3be7c78aa9358f9b42b9fa4dc282bed54d6c` (verified via `git rev-parse HEAD^`) |
| Commit Subject | `AP-SRV-070 W5: finalize GitHub-native release infrastructure` |
| Product Version | `2.0.0` |
| Final Workspace Status | **Literally clean** (`git status --porcelain=v1` is empty) |
| Remote Branch State | `origin/feat/einheitliche-triggerarchitektur-distributed` unchanged at `934e3be7c78aa9358f9b42b9fa4dc282bed54d6c` |
| Temporary Review Branch | `review/ap-srv-070-w5-r04-root` at `40a6eee93102b8355067973e94368b55ed2bf049` (authorized dirty review push) |
| Changed Files Count | 70 files changed (52 modified/renamed/deleted, 18 added) |
| Diffstat | 70 files changed, 9508 insertions(+), 3526 deletions(-) |

---

## 2. Root Review Correction Summary (Review 1: B1–B4 + E1; Review 2: B5 + B6)

The external Root Review rejected the superseded local commit `5a87ad837a9f078c59a37bd7a1e1134b59117a97` (`FAIL`) and subsequently `202bedadd4a2448e7ab11fb11b2567053b46a2e1` (`FAIL`), accepting B1–B4 and E1, and identifying two narrow deterministic release defects: B5 and B6. These are resolved in the amended commit:

```text
External Root Review 1 on 5a87ad837a9f078c59a37bd7a1e1134b59117a97:
FAIL (B1, B2, B3, B4, E1)

External Root Review 2 on 202bedadd4a2448e7ab11fb11b2567053b46a2e1:
FAIL

Accepted from prior correction:
B1 - publish workflow permissions
B2 - Linux + Windows public-wheel candidate matrix
B3 - QUALIFIED publication barrier
E1 - staging evidence consistency

Remaining findings corrected:
B5 - current PyPI release JSON API shape
B6 - workflow input version validation
```

### 2.1 B1 — Publish Workflow Permissions
- **Finding:** Jobs in `.github/workflows/release-publish.yml` lacked permissions needed for cross-run artifact downloads (`actions: read`) and repository checkouts (`contents: read`).
- **Resolution:** Explicit least-privilege permissions assigned per job:
  - Any job calling `actions/download-artifact` with `run-id`: `actions: read`.
  - Any job calling `actions/checkout`: `contents: read` (or `contents: write` where tagging/releasing).
  - PyPI Trusted Publishing job: strictly isolated `id-token: write` + `contents: read` + `actions: read`.
  - GHCR write jobs: `packages: write`.
  - General CI: strictly read-only.
- **Verification:** Tested in `tests/unit/test_release_workflows.py` (39 passed).

### 2.2 B2 — Multi-Platform Candidate Build Matrix (Linux x86_64 + Windows AMD64)
- **Finding:** The candidate build was Linux-only, leaving Windows AMD64 distribution wheels missing and breaking the product contract for Windows users.
- **Resolution:**
  - Candidate workflow (`.github/workflows/release-candidate.yml`) partitioned into 3 jobs:
    - `candidate-linux` on `ubuntu-24.04`: builds Free and Pro Linux distribution wheels and OCI images.
    - `candidate-windows` on `windows-latest`: builds Free and Pro Windows AMD64 distribution wheels.
    - `candidate` on `ubuntu-24.04`: downloads all 4 wheels, verifies identities, binds them into candidate manifest v2, and marks readiness.
  - Manifest schema v2 (`release_tooling/rc_manifest.py`) enforces `REQUIRED_PLATFORMS = ("linux_x86_64", "win_amd64")`:
    - `voice-stt-server`: Linux wheel (`cp312-cp312-linux_x86_64`) + Windows wheel (`cp312-cp312-win_amd64`).
    - `voice-stt-server-pro`: Linux wheel (`cp312-cp312-linux_x86_64`) + Windows wheel (`cp312-cp312-win_amd64`).
  - `tools/release_candidate.py` updated with `build_windows_candidate` and `--platform {linux,windows,all}`.
- **Verification:** Verified by `tests/unit/test_release_candidate.py` (including `WindowsCandidateBuildTests`) and `test_release_rc_manifest.py`.

### 2.3 B3 — Qualification Publication Barrier
- **Finding:** Syntactically valid manifests with `releaseReadiness == "NOT_QUALIFIED"` could enter the real publication engine.
- **Resolution:**
  - Release engine (`release_tooling/engine.py`): In `ExecutionMode.REAL`, enforces `manifest["releaseReadiness"] == "QUALIFIED"` and verifies `manifest["evidenceRef"]`. Any non-qualified manifest raises `QualificationError` fail-closed before state execution starts.
  - Preflight (`release_tooling/preflight.py`): Added `_check_qualification` and `--require-qualified` CLI flag.
  - CLI (`release_tooling/cli.py`): `publish` command validates qualification and passes `require_qualified=True`. Added `manifest qualify` command to transition candidates upon qualification pass.
- **Verification:** Tested in `test_release_engine.py`, `test_release_preflight.py`, and `test_release_cli.py`.

### 2.4 B4 — PyPI Remote Conflict Precheck
- **Finding:** PyPI public write was attempted via Trusted Publishing prior to remote state verification, meaning conflicting same-version state was only detected post-write.
- **Resolution:**
  - Implemented `inspect_pypi_release` and `precheck_pypi` in `release_tooling/remote_checks.py`.
  - Added `release-tooling precheck-pypi` CLI command.
  - Evaluates both distributions (`voice-stt-server` and `voice-stt-server-pro`) across all 4 wheels before writer invocation:
    - `ABSENT`: safe to publish.
    - `MATCH`: safe to resume (omits re-upload).
    - `CONFLICT`: aborts fail-closed with exit 1 before any public write.
    - `UNKNOWN`: aborts fail-closed with exit 2 before any public write.
  - Supports `--stage-dir` to stage only absent wheels for `pypa/gh-action-pypi-publish`.
- **Verification:** Tested in `test_release_remote_checks.py`, `test_release_cli.py`, and `test_release### 2.5 E1 — Staging Evidence Correction
- **Finding:** G17 in `07_GATE_INDEX.md` stated candidate images were pushed to private staging GHCR, while the final report stated zero staging pushes occurred.
- **Resolution:**
  - Clarified in `07_GATE_INDEX.md` (G17 & G48), `08_DEVIATIONS.md`, and this report:
  - Local W5-R04 implementation proves staging architecture and persistence structurally without mutative network calls.
  - Exactly zero staging registry writes occurred during local implementation.
  - Real private staging GHCR persistence occurs during the post-Root-PASS GitHub Actions candidate run.

### 2.6 B5 — PyPI Read-Only Precheck & Verification via Current Release JSON API Shape
- **Finding:** `inspect_pypi_release()` requested `https://pypi.org/pypi/<project>/<version>/json` but attempted to read releases from `payload.get("releases", {}).get(version, [])`. The official current PyPI release-specific endpoint omits the top-level `releases` mapping; its files for that release are delivered in top-level `"urls": [...]`. Consequently, an existing release appeared as absent files, inhibiting precheck conflict detection and post-write verification.
- **Resolution:**
  - `release_tooling/remote_checks.py`: Rewrote `inspect_pypi_release` to parse the top-level `urls` list.
  - For each object, reads `filename` and `digests.sha256`.
  - Fails closed with `VerificationUnavailableError` if `urls` is missing or not a list; empty `urls: []` indicates a known state without files yet (`ABSENT`); HTTP 404 remains genuine `ABSENT`.
  - Both precheck and post-write adapter verification use the identical corrected parser.
- **Verification:** Tested in `tests/unit/test_release_remote_checks.py` (23 tests: match, hash conflict, extra file conflict, partial staging, malformed/missing urls fail-closed, empty urls, 404) and `tests/unit/test_release_adapters.py`.

### 2.7 B6 — Workflow Input Version Validation against Candidate Manifest
- **Finding:** `.github/workflows/release-publish.yml` defined `concurrency.group: release-publish-${{ inputs.version }}` but never validated that `inputs.version` matched `rc-manifest.productVersion`. A typo in the dispatch input could decouple serialization from the published version.
- **Resolution:**
  - In `release-publish.yml` (`tag` job), before Git tag creation and before `release.py publish`, added a preflight validation step:
    ```bash
    python release.py preflight \
      --manifest "$CANDIDATE_DIR/rc-manifest.json" \
      --version "${{ inputs.version }}" \
      --require-qualified
    ```
  - Added `--version` to CLI `publish` parser; `_cmd_publish` fails closed with error exit if `args.version` differs from candidate `productVersion`.
  - Passed `--version "${{ inputs.version }}"` to all `release.py publish` invocations across all jobs.
  - In `release_tooling/preflight.py`, implemented `_check_manifest_version` (`rc_manifest_version_matches`) verifying exact version equality.
- **Verification:** Tested in `test_release_preflight.py`, `test_release_cli.py`, and `test_release_workflows.py`.

---

## 3. Architecture & Release Infrastructure Summary

### 3.1 Canonical State Machine & Operation Graph

The release process is governed by a single canonical state machine (`release_tooling/state.py`) and execution engine (`release_tooling/engine.py`). Both dry-run and live execution evaluate the exact same graph.

The state progression strictly enforces qualification before publication:
```text
PREPARED → TAGGED → PYPI_PUBLISHED → DOCKERHUB_PUBLISHED → GHCR_PUBLISHED → EXTERNAL_VERIFIED → ALIASES_PUBLISHED → GITHUB_RELEASED → FINAL_VERIFIED → COMPLETE
```
- **Tag Barrier:** Git tag creation (`TAGGED`) occurs only after deterministic qualification completes, and strictly precedes any irreversible public registry write.
- **Docker Hub to GHCR Promotion:** Docker Hub is published first (`DOCKERHUB_PUBLISHED`); GHCR (`GHCR_PUBLISHED`) promotes the exact Docker Hub manifest by digest (`docker buildx imagetools create`), guaranteeing byte and digest parity without a second image build.
- **Movable Aliases Barrier:** Major (`2`), minor (`2.0`), and `latest` aliases (`release_tooling/aliases.py`) are created only after exact immutable SemVer artifacts are verified in both registries (`EXTERNAL_VERIFIED`). Each alias digest is remotely verified post-creation (`W5R4-G39`). For `0.x` versions, the broad `0` alias is omitted (`W5R4-G37`).
- **GitHub Release Last:** GitHub Release (`GITHUB_RELEASED`) is created as the final public success marker, after alias promotion and registry verification.

### 3.2 GitHub-Native Build & Qualification Authority

Release candidates are assembled and qualified exclusively in GitHub Actions on fresh, clean runners:
- **Clean Checkout Invariant:** The candidate build path (`.github/workflows/release-candidate.yml`, `tools/release_candidate.py`) runs from a clean git checkout of the exact commit. There is zero dependency on local developer workstations, pre-existing local wheels, or pre-populated Kroko artifact stores.
- **Candidate Persistence:** In the GitHub Actions candidate workflow, qualified candidate wheels and production image manifests are staged into private GHCR staging packages (`staging-voice-stt-server` and `staging-voice-stt-server-pro`) pinned by immutable digest tags. (Zero local staging registry writes were performed during local implementation).
- **Resume Capability:** Publishing workflows locate and reuse the exact candidate artifacts by commit SHA and run ID without recompilation.

### 3.3 Packaging Identity & Complete Wheel Matrix

In accordance with the binding product and packaging authority:
- **Two Alternative PyPI Distributions:**
  - `voice-stt-server`: complete VoiceSTT server with embedded native Kroko Free runtime.
  - `voice-stt-server-pro`: complete VoiceSTT server with embedded native Kroko Pro runtime.
- **Complete Platform Wheel Matrix (4 wheels total):**
  1. `voice_stt_server-2.0.0-cp312-cp312-linux_x86_64.whl` (Free Linux)
  2. `voice_stt_server-2.0.0-cp312-cp312-win_amd64.whl` (Free Windows)
  3. `voice_stt_server_pro-2.0.0-cp312-cp312-linux_x86_64.whl` (Pro Linux)
  4. `voice_stt_server_pro-2.0.0-cp312-cp312-win_amd64.whl` (Pro Windows)
- **Shared Canonical Surface:** Both distributions provide the identical canonical Python import `voice_stt_server` and identical CLI `voice-stt-server` (with legacy compatibility preserved). They are mutually exclusive alternative packages.
- **No-sdist Rationale:** Wheels for supported targets are published without an sdist so end-user `pip install` never triggers a ~30 min native C++ build.
- **Runtime Key Separation:** Kroko Pro builds and production images require no runtime license key at build time (`W5R4-G50`).

### 3.4 Workflow Boundaries & Least Privilege

- **`.github/workflows/ci.yml`:** Runs on pushes and pull requests; top-level `permissions: contents: read`; strictly read-only; zero publishing jobs; receives no release secrets.
- **`.github/workflows/release-candidate.yml`:** Triggered only via `workflow_dispatch`; builds and qualifies candidate artifacts; writes only to private staging GHCR.
- **`.github/workflows/release-publish.yml`:** Triggered only via `workflow_dispatch`; bound to the protected GitHub environment `release` requiring explicit operator approval.
- **OIDC / Trusted Publishing:** `id-token: write` is isolated strictly to the PyPI publishing job; no long-lived PyPI API tokens are configured.
- **Action Pinning:** All third-party GitHub Actions are pinned to immutable 40-character commit SHAs resolved via the GitHub API (`W5R4-G43`).

---

## 4. Public Documentation Surface Rebaseline

The public documentation surface has been aligned truthfully with the actual product:
- **README.md:** Rewritten completely from scratch; presents `voice-stt-server` and `voice-stt-server-pro`; advertises only `faster_whisper` and `kroko_onnx` as supported production STT engines.
- **Documentation Directory Layout:** Deleted `docs/engines/` directory; relocated maintained engine guides directly to `docs/faster-whisper.md` and `docs/kroko-onnx.md`.
- **docs/fastapi-server.md & docs/quick-start.md:** Recipes updated to present supported production engines (`faster_whisper` and `kroko_onnx`); legacy adapters (`whisper_cpp`, `sherpa_onnx_moonshine`, `parakeet`, `omnilingual_asr`) are segregated under dedicated internal/experimental sections with clear caveats.
- **docs/release-process.md:** Comprehensive guide documenting release architecture, states, multi-platform wheel matrix, and operator setup.
- **Link Integrity:** Verified with 0 broken relative links across all maintained Markdown files (`W5R4-G57`, `W5R4-G64`).

---

## 5. Verification & Regression Evidence

All tests were executed against the exact corrected final tree (`7aa37473f44dcf39587c33dc3cde1fe0caed7ed0` / commit `40a6eee93102b8355067973e94368b55ed2bf049`):

### 5.1 Targeted Test Suites (G61 – G64)

| Suite | Tests Run | Result | Duration | Scope |
| --- | --- | --- | --- | --- |
| **G61: Release Tooling** | 350 (225 subtests) | **PASS (0 failures)** | 15.07s | Engine state machine, candidate manifest v2 with 4 wheels, adapters, aliases, preflight with QUALIFIED barrier and candidate version validation, precheck-pypi with current PyPI urls shape (B5), WindowsCandidateBuildTests |
| **G62: Build & Kroko** | 191 | **PASS (0 failures)** | 18.730s | Distribution wheel packaging, Dockerfile contracts, Kroko fingerprinting, store reuse |
| **G63: Workflows & Security** | 41 (158 subtests) | **PASS (0 failures)** | 0.96s | YAML syntax, least-privilege permissions (`actions: read`, `contents: read`), candidate multi-runner matrix, SHA-pinned actions, manifest version validation step before tag creation (B6) |
| **G64: Documentation Surface** | 30 | **PASS (0 failures)** | 0.113s | Removed guides gone, link integrity, README honesty, engine support claims |

### 5.2 Full Regression Suites (G65, G66)

| Platform | Command / Environment | Result | Duration | Evidence File |
| --- | --- | --- | --- | --- |
| **G65: Windows** | `python -m pytest -q --basetemp=P:\tmp\pt_w5r4_final tests/unit` (Python 3.12.8, Windows 11) | **1930 passed, 14 skipped, 1244 subtests passed, 0 failures** | 677.19s (11m 17s) | `Evidence/08_WindowsRegression/unit_full_final_tree.log` |
| **G66: Ubuntu 24.04** | `python -m pytest -q tests/unit` (Python 3.12.3, native ext4 WSL2) | **1930 passed, 14 skipped, 4 warnings, 1244 subtests passed, 0 failures** | 417.37s (6m 57s) | `Evidence/09_UbuntuRegression/unit_full_final_tree.log` |

### 5.3 Diff, Scope & Secret Review (G67 – G69)

- **W5R4-G67 (`git diff --check`):** PASS (0 whitespace errors or conflict markers).
- **W5R4-G68 (Scope / Security Review):** PASS (No files > 500 KB; zero secrets or credentials committed; changes strictly within release/build/docs scope).
- **W5R4-G69 (Full Diff Archive):** Archived in `Evidence/11_Diff/corrected_final_diff.patch` (SHA256: `F16F5BBB296DCB32B6030A06B6FB528F2F428C17B812D1B6783286CCE8DEC3D8`).

---

## 6. Zero Public / Mutative Writes Confirmation

It is explicitly confirmed that during this run:
- **Zero git pushes to durable branches** occurred (`git push` was never executed against `feat/einheitliche-triggerarchitektur-distributed`, `feat/einheitliche-triggerarchitektur`, or `main`).
- **Authorized dirty review push** was executed exclusively to temporary inspection branch `review/ap-srv-070-w5-r04-root` pointing to commit `40a6eee93102b8355067973e94368b55ed2bf049`.
- **Zero git tags** were created or pushed.
- **Zero packages** were uploaded to PyPI or TestPyPI.
- **Zero images** were pushed to Docker Hub.
- **Zero packages/images** were pushed to public GHCR.
- **Zero packages/images** were pushed to private staging GHCR.
- **Zero GitHub Releases** were created.
- Remote branch `feat/einheitliche-triggerarchitektur-distributed` remains untouched at `934e3be7c78aa9358f9b42b9fa4dc282bed54d6c`.

---

## 7. Closure Conclusion

All 75 gates (W5R4-G01 through W5R4-G75) are accounted for and satisfied (with G09 superseded by binding packaging authority as documented in `07_GATE_INDEX.md` and `08_DEVIATIONS.md`). All findings from Root Review 1 (B1–B4, E1) and Root Review 2 (B5, B6) are resolved.

Exactly one corrected local implementation commit (`40a6eee93102b8355067973e94368b55ed2bf049`) exists directly parented to the binding start commit `934e3be7c78aa9358f9b42b9fa4dc282bed54d6c`. The working directory is literally clean.

The run is complete and submitted for review. **Only an external Root Review may grant Root PASS.**
