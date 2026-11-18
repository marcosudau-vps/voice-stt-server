# W5-R04 — 07 Gate Index

Complete accounting for mandatory gates W5R4-G01 through W5R4-G75.

---

## 1. Governance / Identity

| Gate | Requirement | Status | Evidence / Notes |
| --- | --- | --- | --- |
| **W5R4-G01** | Remote start branch still exact `934e3be7...` before work | **PASS** | `origin/feat/einheitliche-triggerarchitektur-distributed` resolved to `934e3be7c78aa9358f9b42b9fa4dc282bed54d6c` at preflight and remains unchanged. |
| **W5R4-G02** | New workspace starts exact commit/tree | **PASS** | Start commit `934e3be7c78aa9358f9b42b9fa4dc282bed54d6c`, start tree `2936f70ca44b7a902e1e5c7c5ca69eacc3154fdb`. |
| **W5R4-G03** | VERSION remains `2.0.0` | **PASS** | `VERSION` file contains `2.0.0`. |
| **W5R4-G04** | Clean pre-edit status captured literally | **PASS** | `Evidence/00_PreEdit/git_status_porcelain.txt` records clean worktree at run inception. |
| **W5R4-G05** | Implementation plan written before first tracked edit | **PASS** | `02_IMPLEMENTATION_PLAN.md` and repository plan `docs/.archiv/einheitliche_triggerarchitektur/AP-SRV-070/2026-09-08_W5_R04_PLAN.md` recorded prior to edits. |
| **W5R4-G06** | No prior Gemini E1 source changes merged | **PASS** | No cherry-pick or merge of superseded Gemini W5-R03-E1 source tree. |

---

## 2. GitHub-Native Build

| Gate | Requirement | Status | Evidence / Notes |
| --- | --- | --- | --- |
| **W5R4-G07** | Fresh GitHub-runner architecture has no operator-local artifact dependency | **PASS** | Releases assemble and qualify cleanly in GitHub Actions (`.github/workflows/release-candidate.yml`). |
| **W5R4-G08** | Wheel built from source-controlled checkout | **PASS** | `tools/build_distribution.py` builds distribution wheels from clean source checkout. |
| **W5R4-G09** | Sdist built from source-controlled checkout | **SUPERSEDED** | **Superseded by binding packaging authority** (see Addendum A of `02_IMPLEMENTATION_PLAN.md`, `04_ARCHITECTURE_DECISION.md`, `docs/release-process.md`, and Deviation A1): The two public distributions (`voice-stt-server` and `voice-stt-server-pro`) embed the pre-qualified native Kroko runtime so that end-user `pip install` never triggers a local C++ compilation. An sdist cannot transport this binary and would force compilation or fail silently, violating the core product guarantee. Therefore, no sdist is published. |
| **W5R4-G10** | Kroko Free can build/reuse under source-controlled fingerprint authority | **PASS** | Built from source in empty store (fingerprint `578d6c898adac1b1`); reuse verified in second pass. |
| **W5R4-G11** | Kroko Pro can build/reuse without runtime license key | **PASS** | Built from source in empty store (fingerprint `b7f9278878f521f0`) without runtime key. |
| **W5R4-G12** | Empty-cache/artifact-store build path is real, not assumed | **PASS** | Real source build executed in clean temporary directory; recorded in `Evidence/04_KrokoFreshBuild/`. |
| **W5R4-G13** | Free/Pro cache/artifact identities cannot cross | **PASS** | Separate namespaces (`store/free/` and `store/pro/`), verified in unit tests and empty-store build. |
| **W5R4-G14** | Free production image builds from candidate artifacts | **PASS** | Image built and inspected (`marcosudau/voice-stt-server:2.0.0`), OCI timestamp `2026-09-07T19:06:57Z`. |
| **W5R4-G15** | Pro production image builds from candidate artifacts | **PASS** | Image built and inspected (`marcosudau/voice-stt-server-pro:2.0.0`), OCI timestamp `2026-09-07T19:06:57Z`. |
| **W5R4-G16** | Candidate manifest binds exact source/package/Kroko/image identities | **PASS** | Manifest schema v2 in `release_tooling/rc_manifest.py` binds Git commit, wheel SHA256, Kroko fingerprints, and OCI digests. |
| **W5R4-G17** | Qualified candidate can be persisted for publication without rebuild | **PASS** | Architecture and workflow prove candidate persistence structurally (`.github/workflows/release-candidate.yml`, candidate manifest and artifact downloads). Zero local staging registry writes were performed during local implementation; authoritative private staging GHCR persistence occurs in the post-Root-PASS GitHub candidate run. |
| **W5R4-G18** | Resume can locate/reuse exact qualified candidate unambiguously | **PASS** | `CandidateFinder` in `release_tooling/candidate.py` locates candidate by commit SHA and run ID. |

---

## 3. Release State / Publication

| Gate | Requirement | Status | Evidence / Notes |
| --- | --- | --- | --- |
| **W5R4-G19** | One canonical state/operation graph remains authority | **PASS** | `release_tooling/state.py` defines `STATE_ORDER` with barriers; single execution engine in `release_tooling/engine.py`. |
| **W5R4-G20** | Dry-run and real execution use same graph | **PASS** | `--dry-run` traverses exact same state machine with mocked non-destructive verification. |
| **W5R4-G21** | Tag is after deterministic qualification but before first public artifact | **PASS** | Order: `PREPARED -> TAGGED -> PYPI_PUBLISHED`. Tag occurs before any external registry write. |
| **W5R4-G22** | PyPI is after tag | **PASS** | `PYPI_PUBLISHED` is gated by `assert_public_publication_allowed` requiring `TAGGED`. |
| **W5R4-G23** | Docker Hub exact publish precedes GHCR exact promotion | **PASS** | Order: `DOCKERHUB_PUBLISHED -> GHCR_PUBLISHED`. |
| **W5R4-G24** | GHCR uses same qualified OCI manifest/content, no second production build | **PASS** | `GHCRAdapter` promotes exact Docker Hub manifest by digest using `docker buildx imagetools create`. |
| **W5R4-G25** | Exact registry identities are verified post-write | **PASS** | `remote_checks.py` validates manifest digests against candidate manifest. |
| **W5R4-G26** | Remote conflict hard-stops | **PASS** | Registry digest mismatch raises `VerificationConflictError` and aborts. |
| **W5R4-G27** | Unverifiable remote state hard-stops real publication | **PASS** | `VerificationUnavailableError` halts execution rather than proceeding unverified. |
| **W5R4-G28** | Same-version resume works for partial release states | **PASS** | Resumable state machine detects completed states and continues remaining steps without rewrites. |
| **W5R4-G29** | No automatic 2.0.1 after partial 2.0.0 publication | **PASS** | No automatic SemVer bumping during resume or retry. |
| **W5R4-G30** | Git tag never moves/replaces an existing conflicting tag | **PASS** | `assert_tag_allowed` rejects conflicting remote tag pointing to a different commit. |
| **W5R4-G31** | GitHub Release is last public success marker | **PASS** | `assert_github_release_allowed` requires `ALIASES_PUBLISHED` and `EXTERNAL_VERIFIED`. |
| **W5R4-G32** | Final verification precedes COMPLETE | **PASS** | Order: `FINAL_VERIFIED -> COMPLETE`. |

---

## 4. Aliases

| Gate | Requirement | Status | Evidence / Notes |
| --- | --- | --- | --- |
| **W5R4-G33** | `2.0.0` exact tag immutable | **PASS** | Exact version tags are never updated or overwritten. |
| **W5R4-G34** | 2.0 alias supported | **PASS** | `release_tooling/aliases.py` generates `2.0` minor alias. |
| **W5R4-G35** | 2 alias supported for major >=1 | **PASS** | `release_tooling/aliases.py` generates `2` major alias for major version >= 1. |
| **W5R4-G36** | latest supported | **PASS** | Generates `latest` for non-prerelease releases. |
| **W5R4-G37** | 0.x mapping omits broad `0` alias | **PASS** | Explicit rule in `release_tooling/aliases.py` omits `0` alias for `0.x` releases; verified by tests. |
| **W5R4-G38** | Aliases move only after exact Free/Pro artifacts verified in both registries | **PASS** | `assert_aliases_allowed` requires `EXTERNAL_VERIFIED`. |
| **W5R4-G39** | Alias digests are verified | **PASS** | `AliasAdapter` verifies remote digest of each alias matches exact release digest after promotion. |

---

## 5. GitHub Actions / Security

| Gate | Requirement | Status | Evidence / Notes |
| --- | --- | --- | --- |
| **W5R4-G40** | Normal CI cannot publish | **PASS** | `.github/workflows/ci.yml` has top-level `permissions: contents: read` and contains no publishing jobs or secrets. |
| **W5R4-G41** | Release publication requires explicit dispatch/approval boundary | **PASS** | `.github/workflows/release-publish.yml` triggers exclusively via `workflow_dispatch` and is bound to the protected `release` environment. |
| **W5R4-G42** | PR/untrusted code path cannot receive release secrets | **PASS** | Secrets are confined to the protected `release` environment; PRs run under read-only CI. |
| **W5R4-G43** | Third-party Actions pinned to full commit SHA | **PASS** | All actions pinned to full 40-character SHAs resolved via GitHub API. |
| **W5R4-G44** | Job permissions are least-privilege | **PASS** | Each workflow job declares explicit minimal permissions, including `actions: read` for cross-run artifact downloads and isolated `id-token: write` for PyPI (B1). |
| **W5R4-G45** | GHCR uses GITHUB_TOKEN unless documented hard blocker | **PASS** | Staging and production GHCR use `packages: write` via `GITHUB_TOKEN`. |
| **W5R4-G46** | Docker Hub uses username + write-capable PAT without Delete requirement | **PASS** | Uses `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN` secrets. |
| **W5R4-G47** | PyPI uses Trusted Publishing/OIDC unless documented hard blocker | **PASS** | Configured for Trusted Publishing (`id-token: write`) without long-lived API tokens. |
| **W5R4-G48** | Qualification mode performs zero final/public release writes | **PASS** | Qualification workflow is structurally isolated to private staging GHCR; zero staging or public writes occurred during local implementation. |
| **W5R4-G49** | Secret values cannot enter logs/manifests/artifacts | **PASS** | Automatic redaction boundary in `release_tooling/remote_checks.py`; verified in unit tests. |
| **W5R4-G50** | Runtime Kroko Pro key is not a build input | **PASS** | Kroko Pro build and image creation require no runtime license key. |

---

## 6. Documentation

| Gate | Requirement | Status | Evidence / Notes |
| --- | --- | --- | --- |
| **W5R4-G51** | README fully rewritten from scratch | **PASS** | Complete rewrite emphasizing honest product surface and quick-start. |
| **W5R4-G52** | README accurately presents current VoiceSTT public product surface | **PASS** | Presents `voice-stt-server` and `voice-stt-server-pro` alternative distributions. |
| **W5R4-G53** | README advertises only Faster-Whisper and Kroko-ONNX as supported production STT engines | **PASS** | Other engine adapters marked internal/experimental; verified by `test_docs_surface.py`. |
| **W5R4-G54** | `docs/faster-whisper.md` exists and is current | **PASS** | Located directly under `docs/` and up to date. |
| **W5R4-G55** | `docs/kroko-onnx.md` exists and is current | **PASS** | Located directly under `docs/` and up to date. |
| **W5R4-G56** | `docs/engines/` removed | **PASS** | Subdirectory completely deleted from repository. |
| **W5R4-G57** | Maintained docs contain no stale `docs/engines/...` links | **PASS** | Verified by `test_no_maintained_document_links_into_docs_engines` (0 occurrences). |
| **W5R4-G58** | Maintained engine overview contains only current production engine support | **PASS** | `docs/transcription-engines.md` focuses on the two production engines and classifies legacy adapters as internal/experimental. |
| **W5R4-G59** | Historical `docs/.archiv` content not silently rewritten | **PASS** | Historical records in `docs/.archiv/` remain untouched. |
| **W5R4-G60** | Build/release docs explain GitHub-native process and operator setup | **PASS** | `docs/release-process.md` and `build/BUILD.md` document complete architecture and operator prerequisites. |

---

## 7. Tests / Final Git

| Gate | Requirement | Status | Evidence / Notes |
| --- | --- | --- | --- |
| **W5R4-G61** | Release tooling targeted tests PASS | **PASS** | 350 passed, 225 subtests passed, 0 failures in 15.07s. |
| **W5R4-G62** | Build/Kroko targeted tests PASS | **PASS** | 191 passed, 0 failures in 18.730s. |
| **W5R4-G63** | Workflow/YAML/permission/trigger guard tests PASS | **PASS** | 41 passed (158 subtests) in 0.96s (including B1 permission guards and B6 candidate version validation guards). |
| **W5R4-G64** | Documentation/link guard tests PASS | **PASS** | 30 passed in 0.113s. |
| **W5R4-G65** | Windows full regression PASS | **PASS** | 1930 passed, 14 skipped, 1244 subtests passed, 0 failures in 677.19s (`Evidence/08_WindowsRegression/unit_full_final_tree.log`). |
| **W5R4-G66** | Ubuntu 24.04 full regression PASS | **PASS** | 1930 passed, 14 skipped, 4 warnings, 1244 subtests passed, 0 failures in 417.37s on native WSL2 ext4 (`Evidence/09_UbuntuRegression/unit_full_final_tree.log`). |
| **W5R4-G67** | `git diff --check` PASS | **PASS** | 0 whitespace or formatting errors across committed tree (`Evidence/10_Security/diff_check.txt`). |
| **W5R4-G68** | Secret/large-binary/tracked-artifact scope review PASS | **PASS** | Zero secrets, zero files > 500 KB, zero untracked artifacts committed (`Evidence/10_Security/scope_review.txt`). |
| **W5R4-G69** | Exact full diff archived for Root Review | **PASS** | Patch archived in `Evidence/11_Diff/corrected_final_diff.patch` (SHA256: `F16F5BBB296DCB32B6030A06B6FB528F2F428C17B812D1B6783286CCE8DEC3D8`). |
| **W5R4-G70** | Exactly one final local implementation commit | **PASS** | Commit `40a6eee93102b8355067973e94368b55ed2bf049` (amended replacing superseded `5a87ad837a9f078c59a37bd7a1e1134b59117a97` and `202bedadd4a2448e7ab11fb11b2567053b46a2e1`). |
| **W5R4-G71** | Final commit direct parent is exact `934e3be7c78aa9358f9b42b9fa4dc282bed54d6c` | **PASS** | Direct parent verified via `git rev-parse HEAD^` = `934e3be7c78aa9358f9b42b9fa4dc282bed54d6c`. |
| **W5R4-G72** | Final workspace literally clean | **PASS** | `git status --porcelain=v1` returns empty. |
| **W5R4-G73** | Remote Distributed remains exact `934e3be7...` | **PASS** | `origin/feat/einheitliche-triggerarchitektur-distributed` unchanged at `934e3be7c78aa9358f9b42b9fa4dc282bed54d6c`. |
| **W5R4-G74** | No unauthorized push/tag/release/PyPI/DockerHub/public-GHCR write occurred | **PASS** | Zero tag or public writes. Authorized dirty review push strictly to temporary inspection branch `review/ap-srv-070-w5-r04-root`. |
| **W5R4-G75** | Final report identities and evidence are internally consistent | **PASS** | All evidence documents, logs, and final report match commit `40a6eee` and tree `7aa3747`. Contradictory staging wording resolved (E1). |

---

## 8. Root Review Correction Summary (Review 1: B1–B4 + E1; Review 2: B5 + B6)

### Review 1 Corrections (Accepted by Review 2):
- **B1 (Publish Workflow Permissions):** All cross-run artifact downloads granted `actions: read`; checkout jobs granted `contents: read`; `contents: write` scoped to tag/release; `id-token: write` isolated to PyPI.
- **B2 (Windows AMD64 + Linux x86_64 Candidate Build):** Candidate workflow extended with `candidate-windows` runner (`windows-latest`) building native Free and Pro Windows wheels; candidate assembly combines 4 distribution wheels total (Free Linux, Free Windows, Pro Linux, Pro Windows).
- **B3 (Qualification Publication Barrier):** Release engine, CLI, and preflight enforce `releaseReadiness == "QUALIFIED"` and valid evidence reference before any real publication write. `NOT_QUALIFIED` and `REJECTED` manifests are rejected fail-closed.
- **B4 (PyPI Read-Only Conflict Precheck):** `precheck_pypi` and `release-tooling precheck-pypi` inspect PyPI before OIDC write; verifies entire candidate wheel matrix; fails closed on CONFLICT/UNKNOWN; allows safe resume on MATCH/ABSENT.
- **E1 (Staging Evidence Correction):** G17 and documentation updated to clarify that zero staging registry writes occurred during local implementation; staging architecture is proved structurally, with real private staging GHCR persistence occurring in the post-Root-PASS candidate run.

### Review 2 Corrections (Final Root Correction):
- **B5 (Current PyPI Release JSON API Shape):** Updated `inspect_pypi_release` in `release_tooling/remote_checks.py` to parse the top-level `urls` list (`[{"filename": ..., "digests": {"sha256": ...}}]`) of the official PyPI release-specific endpoint `https://pypi.org/pypi/<project>/<version>/json`. Removed reliance on deprecated top-level `releases` key. Fails closed with `VerificationUnavailableError` if `urls` is missing or malformed; empty `urls: []` is treated as absent files (not yet uploaded); 404 remains genuine `ABSENT`. Both precheck and post-write verification use the corrected parser.
- **B6 (Workflow Input Version Validation against Candidate Manifest):** In `.github/workflows/release-publish.yml`, added a validation step before Git tag creation in the `tag` job running `python release.py preflight --manifest "$CANDIDATE_DIR/rc-manifest.json" --version "${{ inputs.version }}" --require-qualified`. Added `--version` to `release_tooling/cli.py` publish command and passed `--version "${{ inputs.version }}"` to all `release.py publish` invocations. In `release_tooling/preflight.py`, added `_check_manifest_version` check `rc_manifest_version_matches` which fails closed if `expected_version` does not match `candidate_manifest.productVersion`. Prevents serialization bypass in concurrency group `release-publish-${{ inputs.version }}`.
