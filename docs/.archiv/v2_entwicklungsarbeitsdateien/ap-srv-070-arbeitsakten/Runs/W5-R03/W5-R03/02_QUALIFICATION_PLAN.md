# AP-SRV-070 / W5-R03 — Qualification Plan

**Internal Candidate:** W5-RC2
**Target Version:** 2.0.0
**Commit:** `934e3be7c78aa9358f9b42b9fa4dc282bed54d6c`
**Tree:** `2936f70ca44b7a902e1e5c7c5ca69eacc3154fdb`
**Parent:** `7f1ad1f02da9b1c4e3bf226f2a056066921ef77a`
**Branch:** `feat/einheitliche-triggerarchitektur-distributed`
**Workspace:** `P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-070-w5-r03`
**Local Branch:** `qual/ap-srv-070-w5-r03`
**Run/Evidence Directory:** `P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W5-R03\`

---

## 1. Objectives & Scope

W5-R03 is the **final frozen release-candidate qualification run** for internal candidate `W5-RC2` of VoiceSTT Server v2.0.0.

The run exists to qualify the exact frozen commit `934e3be7c78aa9358f9b42b9fa4dc282bed54d6c` following the successful fixes in C1/C2/C3/C3-R1 (confirmed passing in GitHub Actions CI run `34155005726`), with special focus on closing the open items from W5-R02:
1. **D4 — Live E2E (Faster-Whisper & Kroko Free):** Replace inconclusive unit-test load harness with a faithful, real Protocol-v2 WebSocket qualification client that delivers the full 51.9s reference audio, avoids premature disconnects, captures all final utterances, and verifies clean session completion.
2. **D5 — Kroko Pro Live E2E:** Execute live qualification using the authoritative local process-only runtime secret `VOICESTT_KROKO_ONNX_KEY` from `secrets/voice-stt.env` without logging or leaking secret values.
3. **D7 — Read-Only Custom Model Source:** Explicitly verify discovery and execution from a read-only filesystem source, proving zero file mutation, identical hashes, and preserved permissions.
4. **End-to-End Release Manifest & Dry-Run:** Bind real production-shaped outputs into `05_RC_MANIFEST.json` and validate release preflight and dry-run with zero public writes.

---

## 2. Operating Constraints & Rules

1. **Frozen Source Code:** No modifications, refactorings, style tweaks, or test alterations in tracked repository files.
2. **No Repository Commits/Pushes/Tags:** Zero commits, zero pushes, zero git tags, zero public package or image publishing.
3. **Secret Hygiene:** `secrets/voice-stt.env` is never printed, copied into git, copied into Docker contexts, hashed, or recorded in evidence.
4. **External Harness & Artifacts:** Qualification scripts, venvs, test audio, manifests, and reports live strictly outside the git tree under `P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W5-R03\`.
5. **Gate Rigor:** All 62 mandatory gates (W5Q2-G01 to W5Q2-G62) must be evaluated. If a genuine blocker is found, document precisely and report `NOT READY FOR ROOT REVIEW` — no repairs in this run.

---

## 3. Mandatory Gate Matrix (62 Gates)

| Gate ID | Category | Description | Target |
| :--- | :--- | :--- | :--- |
| **W5Q2-G01** | RC Identity | Frozen RC commit exactly `934e3be7c78aa9358f9b42b9fa4dc282bed54d6c` | PASS |
| **W5Q2-G02** | RC Identity | Frozen RC tree exactly `2936f70ca44b7a902e1e5c7c5ca69eacc3154fdb` | PASS |
| **W5Q2-G03** | RC Identity | VERSION file contains exactly `2.0.0` | PASS |
| **W5Q2-G04** | RC Identity | Dedicated clean worktree created from exact RC | PASS |
| **W5Q2-G05** | RC Governance | No tracked source modification during run | PASS |
| **W5Q2-G06** | RC Governance | No commit, push, tag, or publication executed | PASS |
| **W5Q2-G07** | Package | RC2 wheel built successfully via PEP 517 build | PASS |
| **W5Q2-G08** | Package | RC2 sdist built successfully | PASS |
| **W5Q2-G09** | Package | `twine check` PASS on wheel and sdist | PASS |
| **W5Q2-G10** | Package | Package artifact SHA256 and sizes recorded | PASS |
| **W5Q2-G11** | Package | Package archives free of secrets, models, dev artifacts | PASS |
| **W5Q2-G12** | Kroko Artifacts | Kroko Free Linux/AMD64 artifact authority PASS | PASS |
| **W5Q2-G13** | Kroko Artifacts | Kroko Pro Linux/AMD64 artifact authority PASS | PASS |
| **W5Q2-G14** | Kroko Artifacts | Free and Pro fingerprints and SHA256 distinct and recorded | PASS |
| **W5Q2-G15** | Kroko Artifacts | Runtime Pro credential absent from build and artifacts | PASS |
| **W5Q2-G16** | Production Images | Free production image built from exact RC2 | PASS |
| **W5Q2-G17** | Production Images | Pro production image built from exact RC2 | PASS |
| **W5Q2-G18** | Production Images | Linux/AMD64, Ubuntu 24.04 runtime, non-root user PASS | PASS |
| **W5Q2-G19** | Production Images | OCI version `2.0.0`, OCI revision exact commit | PASS |
| **W5Q2-G20** | Production Images | No secrets, models, or checkout mounts in images | PASS |
| **W5Q2-G21** | Production Images | Free and Pro image identity separation PASS | PASS |
| **W5Q2-G22** | Fresh Install | Windows 11 fresh wheel install PASS in clean venv | PASS |
| **W5Q2-G23** | Fresh Install | Ubuntu 24.04 fresh wheel install PASS in clean venv | PASS |
| **W5Q2-G24** | Fresh Install | Same exact wheel SHA256 installed on both platforms | PASS |
| **W5Q2-G25** | Fresh Install | pip check, import, version, console scripts, assets PASS | PASS |
| **W5Q2-G26** | Fresh Install | Installed distribution runs without source checkout | PASS |
| **W5Q2-G27** | Fresh Install | Startup does not implicitly download large STT models | PASS |
| **W5Q2-G28** | Fresh Install | Clean server startup and graceful shutdown PASS | PASS |
| **W5Q2-G29** | Model Management | Model discovery and transactional refresh PASS | PASS |
| **W5Q2-G30** | Model Management | Explicit hash-verified model provisioning PASS | PASS |
| **W5Q2-G31** | Model Management | Managed-store persistence over container recreation PASS | PASS |
| **W5Q2-G32** | Custom Source | Read-only custom model source is discoverable and usable | PASS |
| **W5Q2-G33** | Custom Source | Read-only custom source unchanged by content, hash, permissions | PASS |
| **W5Q2-G34** | Custom Source | Managed writable operations do not mutate custom source | PASS |
| **W5Q2-G35** | Live E2E | Controlled audio fixture (`asr-reference.wav`) verified & hashed | PASS |
| **W5Q2-G36** | Live E2E | Faster-Whisper complete Protocol-v2 live E2E PASS | PASS |
| **W5Q2-G37** | Live E2E | Faster-Whisper transcript coverage/plausibility PASS | PASS |
| **W5Q2-G38** | Live E2E | Kroko Free complete Protocol-v2 live E2E PASS | PASS |
| **W5Q2-G39** | Live E2E | Kroko Free transcript coverage/plausibility PASS | PASS |
| **W5Q2-G40** | Live E2E | Kroko Pro runtime credential available without exposure | PASS |
| **W5Q2-G41** | Live E2E | Kroko Pro exact artifact and image identity PASS | PASS |
| **W5Q2-G42** | Live E2E | Kroko Pro complete Protocol-v2 live E2E PASS | PASS |
| **W5Q2-G43** | Live E2E | Kroko Pro transcript coverage/plausibility PASS | PASS |
| **W5Q2-G44** | Live E2E | All three live sessions complete cleanly without truncation | PASS |
| **W5Q2-G45** | Security | Authentication & authorization negative checks PASS | PASS |
| **W5Q2-G46** | Security | Secret redaction & artifact secret scans PASS | PASS |
| **W5Q2-G47** | Security | Canonical event store unavailable fail-closed PASS | PASS |
| **W5Q2-G48** | Security | Failed events never appear as committed log events | PASS |
| **W5Q2-G49** | Security | No local secret path or value leakage | PASS |
| **W5Q2-G50** | Release Tooling | Release preflight PASS on exact RC2 | PASS |
| **W5Q2-G51** | Release Tooling | Release dry-run PASS with zero public writes | PASS |
| **W5Q2-G52** | Release Tooling | Publication operation order exact | PASS |
| **W5Q2-G53** | Release Tooling | Same-version resume and no-auto-version-bump contract PASS | PASS |
| **W5Q2-G54** | RC Manifest | RC manifest builds from real production-shaped outputs | PASS |
| **W5Q2-G55** | RC Manifest | RC manifest schema validation PASS | PASS |
| **W5Q2-G56** | RC Manifest | Manifest binds exact package, Kroko, image, commit, tree IDs | PASS |
| **W5Q2-G57** | GitHub Actions | Run `34155005726` binds exact commit and tree | PASS |
| **W5Q2-G58** | GitHub Actions | Windows CI job PASS (`success`) | PASS |
| **W5Q2-G59** | GitHub Actions | Ubuntu 24.04 CI job PASS (`success`) | PASS |
| **W5Q2-G60** | Final Integrity | Workspace clean, frozen HEAD and tree unchanged | PASS |
| **W5Q2-G61** | Final Integrity | No tag, release, or public registry write occurred | PASS |
| **W5Q2-G62** | Final Integrity | Final RC manifest and reports reflect readiness consistently | PASS |

---

## 4. Execution Phases

### Phase 1: Preflight, Source Identity & GitHub CI Verification
- Verify worktree HEAD, tree, VERSION, parent, origin branch.
- Verify GitHub Actions CI run `34155005726` on exact commit/tree with green Windows and Ubuntu jobs.
- Record evidence in `Evidence/00_Preflight/` and `Evidence/01_Source_Identity/` and `Evidence/15_GitHub_CI/`.

### Phase 2: Package Build & Validation
- Build wheel and sdist using `python -m build --outdir ...` from frozen source into an external directory or dedicated clean dist folder.
- Execute `twine check`.
- Record SHA256 hashes and file sizes.
- Inspect archive members for forbidden paths, secrets, or large files.
- Record evidence in `Evidence/02_Package_Build/`.

### Phase 3: Kroko Artifact Qualification (Free & Pro)
- Build or obtain Kroko Free and Kroko Pro Linux/AMD64 artifacts per official artifact authority.
- Record distinct fingerprints, wheel SHA256, and metadata.
- Verify that no Pro license key is embedded.
- Record evidence in `Evidence/03_Kroko_Artifacts/`.

### Phase 4: Production Images Build & Qualification
- Build Free and Pro Docker production images from exact RC2 using official Docker paths.
- Inspect images: OCI version (`2.0.0`), OCI revision (`934e3be...`), base OS (Ubuntu 24.04), non-root user (UID 10001).
- Verify image layers and history are free of secrets and large models.
- Record evidence in `Evidence/04_Production_Images/`.

### Phase 5: Fresh Installed Distribution Qualification
- Create isolated virtual environments on Windows 11 and WSL2 Ubuntu 24.04.
- Install exact RC2 wheel (verifying matching SHA256).
- Run `pip check`, version check, console script smoke, asset verification.
- Test server startup and graceful shutdown outside source checkout.
- Record evidence in `Evidence/05_Fresh_Install_Windows/` and `Evidence/06_Fresh_Install_Ubuntu/`.

### Phase 6: Model Management & D7 Read-Only Custom Source
- Test model discovery, refresh, and hash-verified provisioning.
- Test container volume persistence over recreate cycle.
- **D7:** Set up a controlled custom model path, set filesystem permissions to read-only (`chmod 555` on Linux/WSL2), run VoiceSTT against it, verify discovery/usage, and prove zero byte changes, identical hashes, and preserved permissions before and after.
- Record evidence in `Evidence/07_Model_Management/` and `Evidence/08_ReadOnly_Custom_Source/`.

### Phase 7: Live E2E Qualification (D4 & D5)
- Audio fixture: `tests/unit/audio/asr-reference.wav` (51.925s, 16kHz, 9 expected utterances).
- Develop external Protocol-v2 WebSocket test client (`W5-R03/Evidence/live_e2e_client.py`) that streams full audio in real-time chunks, captures interim and final events, issues `{"type":"stop"}` cleanly, and waits for final transcription without premature cutoff.
- **D4 Faster-Whisper:** Run against Faster-Whisper model, capture all 9 utterance regions, verify plausible transcript and clean exit.
- **D4 Kroko Free:** Run against Kroko Free engine in production container/runtime, verify complete transcript and clean exit.
- **D5 Kroko Pro:** Load `VOICESTT_KROKO_ONNX_KEY` process-only from `secrets/voice-stt.env`, run against Kroko Pro engine, verify complete transcript, Pro engine initialization, and clean exit.
- Generate machine-readable JSON summaries for all 3 engines.
- Record evidence in `Evidence/09_Live_E2E_FasterWhisper/`, `Evidence/10_Live_E2E_Kroko_Free/`, `Evidence/11_Live_E2E_Kroko_Pro/`.

### Phase 8: Security & Negative Checks
- Negative authentication checks (invalid/missing tokens).
- Fail-closed canonical log store checks.
- Redaction verification (ensure credentials never leak in logs, settings, or events).
- Record evidence in `Evidence/12_Security_Negative/`.

### Phase 9: Release Preflight, Dry-Run & RC Manifest
- Run `release_tooling` preflight on exact RC2 (zero public writes).
- Run `release_tooling` dry-run (zero public writes).
- Build `05_RC_MANIFEST.json` binding exact wheel, sdist, Kroko, image, and git identities.
- Run manifest validation.
- Record evidence in `Evidence/13_Release_Preflight/`, `Evidence/14_Release_DryRun/`, `Evidence/16_RC_Manifest/`.

### Phase 10: Final Git Integrity & Reporting
- Verify git status is completely clean, HEAD and tree unchanged.
- Compile `06_QUALIFICATION_REPORT.md` and `07_FINAL_REPORT.md`.
- Record final git state in `Evidence/17_Final_Git_State/`.
