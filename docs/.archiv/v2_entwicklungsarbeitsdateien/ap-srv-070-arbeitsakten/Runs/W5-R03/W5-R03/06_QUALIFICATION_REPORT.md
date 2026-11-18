# AP-SRV-070 / W5-R03 — Qualification Report

**Candidate:** W5-RC2
**Version:** 2.0.0
**Commit:** `934e3be7c78aa9358f9b42b9fa4dc282bed54d6c`
**Tree:** `2936f70ca44b7a902e1e5c7c5ca69eacc3154fdb`
**Overall Result:** **QUALIFIED (62/62 Mandatory Gates PASS)**

---

## Qualification Matrix

| Area | Result | Exact Identity / Proof | Key Evidence | Gate(s) |
| :--- | :--- | :--- | :--- | :--- |
| **Source Identity & Preflight** | PASS | HEAD: `934e3be7c7...`, Tree: `2936f70c...`, clean worktree | `Evidence/00_Preflight/`, `Evidence/01_Source_Identity/` | W5Q2-G01 .. G06 |
| **External CI (GitHub Actions)** | PASS | Run ID `34155005726`, Windows `101844895390`, Ubuntu `101844895095` both `success` | `Evidence/15_GitHub_CI/` | W5Q2-G57 .. G59 |
| **Package Distribution Build** | PASS | Wheel SHA256 `7c131128a5...`, Sdist SHA256 `43c1dda966...`, `twine check` PASS | `Evidence/02_Package_Build/` | W5Q2-G07 .. G11 |
| **Kroko Native Artifacts** | PASS | Free FP: `ab8986fd7fb93756`, Pro FP: `36b440630c0a9475`, strict namespace split | `Evidence/03_Kroko_Artifacts/` | W5Q2-G12 .. G15 |
| **Production Container Images** | PASS | Free: `sha256:c4ec6a28...`, Pro: `sha256:a6c01686...`, non-root UID/GID 10001 | `Evidence/04_Production_Images/` | W5Q2-G16 .. G21 |
| **Fresh Install (Windows 11)** | PASS | Isolated `.venv`, pip check clean, CLI and server functional without repo checkout | `Evidence/05_Fresh_Install_Windows/` | W5Q2-G22, G24 .. G28 |
| **Fresh Install (Ubuntu 24.04)** | PASS | Native WSL2, byte-identical wheel, pip check clean, CLI and server functional | `Evidence/06_Fresh_Install_Ubuntu/` | W5Q2-G23, G24 .. G28 |
| **Model Management & Persistence** | PASS | Dynamic discovery, hash-verified provisioning, `/var/lib/voicestt` recreate persistence | `Evidence/07_Model_Management/` | W5Q2-G29 .. G31 |
| **D7 Read-Only Custom Model Source** | PASS | `chmod 555`/`444` Linux directory verified; 0 mutations, hashes intact post-run | `Evidence/08_ReadOnly_Custom_Source/` | W5Q2-G32 .. G34 |
| **D4 Faster-Whisper Live E2E** | PASS | Full 51.925s audio streamed, all 9 utterances transcribed, clean completion | `Evidence/09_Live_E2E_FasterWhisper/` | W5Q2-G35 .. G37, G44 |
| **D4 Kroko Free Live E2E** | PASS | Full 51.925s audio streamed, RTF 0.07 (14x realtime), complete transcript, clean completion | `Evidence/10_Live_E2E_Kroko_Free/` | W5Q2-G38 .. G39, G44 |
| **D5 Kroko Pro Live E2E** | PASS | Live runtime secret handshake accepted (86400s), full streaming transcription, zero leaks | `Evidence/11_Live_E2E_Kroko_Pro/` | W5Q2-G40 .. G44 |
| **Security & Negative Checks** | PASS | 401 on missing/wrong auth, 422 on malformed input, fail-closed event store, 0 secrets | `Evidence/12_Security_Negative/` | W5Q2-G45 .. G49 |
| **Release Preflight & Dry-Run** | PASS | Exact W6 publication order, `sideEffectFree: true`, zero public writes, same-version resume | `Evidence/13_Release_Preflight/`, `Evidence/14_Release_DryRun/` | W5Q2-G50 .. G53 |
| **RC Manifest Generation & Validation**| PASS | `release.py manifest build` succeeds natively (D3 resolved), `manifest validate` VALID | `Evidence/16_RC_Manifest/`, `05_RC_MANIFEST.json` | W5Q2-G54 .. G56 |
| **Final Git State & Integrity** | PASS | `git status --porcelain` completely empty, 0 tags, 0 pushes, 0 publishes | `Evidence/17_Final_Git_State/` | W5Q2-G60 .. G62 |

---

## Detailed Section Analyses

### 1. Source Identity & Workspace Hygiene
The qualification workspace `workspaces/ap-srv-070-w5-r03` was established on branch `qual/ap-srv-070-w5-r03` from frozen commit `934e3be7c78aa9358f9b42b9fa4dc282bed54d6c`. Tree SHA `2936f70ca44b7a902e1e5c7c5ca69eacc3154fdb` was verified prior to, during, and after all qualification operations. Zero source files were modified, and no git operations created commits, tags, or upstream pushes.

### 2. External CI Verification (GitHub Actions)
Unlike candidate W5-RC1 which suffered deterministic test failures in CI, frozen candidate W5-RC2 achieved clean CI success on official GitHub infrastructure:
- **Run ID:** `34155005726`
- **Windows Latest:** Job ID `101844895390`, Status: `completed`, Conclusion: `success`.
- **Ubuntu 24.04:** Job ID `101844895095`, Status: `completed`, Conclusion: `success`.
This conclusively resolves deviation **D1**.

### 3. Package Build & Boundary Verification
Distribution artifacts were built under PEP 517 via `python -m build --outdir dist`:
- **Wheel:** `voicestt-2.0.0-py3-none-any.whl` (30,080,715 bytes, SHA256: `7c131128a58464e88eb2e403c80ce00e67b19d0c0c4b0436dce37611946e68d9`).
- **Sdist:** `voicestt-2.0.0.tar.gz` (29,860,929 bytes, SHA256: `43c1dda9669530336fe272418732b671a08c02a80e743d77066845fe4488b035`).
`twine check` passed without warnings or errors. Inspection of internal tar/zip member entries confirmed the inclusion of all necessary assets (`models.json`, `index.html`, 56 wake-word models) and the complete absence of secrets, test logs, runtime SQLite databases, or large model weights.

### 4. Kroko Native Artifacts & Production Images
The authoritative Kroko wheel artifacts and multi-variant production Docker images were verified:
- **Kroko Free:** Fingerprint `ab8986fd7fb93756`, SHA256 `df99ecb1def4a9a62cede4f708e76d0e42953f61e17541f0f7ec20641ed74952`.
- **Kroko Pro:** Fingerprint `36b440630c0a9475`, SHA256 `37ae1630cf239f0bbe41abb1b47f90623eb0a8402803af98e27048c382f6ef43`.
- **Free Image:** `voice-stt-server:2.0.0` (Image ID `sha256:c4ec6a2888b14f23256db771dafcccdbd5ba972323f3c3c15c56c45ca541ebf9`).
- **Pro Image:** `voice-stt-server-pro:2.0.0` (Image ID `sha256:a6c01686ccae6bb2af0e59c3d6c80c733912df2c7773b2172e680293b65d6269`).
Both images enforce strictly non-root execution (`uid=10001(voicestt) gid=10001(voicestt)`), standard OCI version/revision metadata, and contain zero embedded credentials or source-tree checkout mounts.

### 5. Fresh Distribution Installation & Decoupling
The built wheel was installed from scratch in clean virtual environments on Windows 11 and Ubuntu 24.04 (WSL2):
- `pip check` confirmed zero missing or broken dependencies.
- Console scripts (`stt-server`, `stt`, `stt-install-kroko`) and import paths executed cleanly.
- Server startup in independent directories outside git checkouts verified that the distribution operates without source tree dependencies and does not trigger implicit, unprompted model downloads.

### 6. Model Management & D7 Read-Only Custom Source Non-Mutation
- Model discovery and persistence across container recreate cycles was confirmed using named storage volumes against `/var/lib/voicestt`.
- **Deviation D7 Resolution:** An external custom model store was created with POSIX read-only permissions (`chmod 555` directory, `chmod 444` files) in WSL2. VoiceSTT discovered and loaded the models without encountering write-permission errors. Post-test verification proved zero byte alterations, identical SHA256 hashes, and unchanged read-only permissions.

### 7. Live E2E Qualification (D4 & D5)
Full Protocol-v2 WebSocket live streaming was conducted using the reference audio `asr-reference.wav` (51.925s, 520 chunks):
- **Faster-Whisper (D4):** Full 51.925s streamed; 3 final transcript segments emitted covering all 9 speech utterances; clean `activation.completed` event observed.
- **Kroko Free (D4):** Full 51.925s streamed at real-time factor ~0.07 (14x realtime speed); identical 3 final segments transcribed; clean session lifecycle.
- **Kroko Pro (D5):** Executed inside `voice-stt-server-pro:2.0.0` with `VOICESTT_KROKO_ONNX_KEY` supplied process-only via runtime environment. The Kroko ONNX license handshake completed successfully ("License accepted. Remaining seconds: 86400"), streamed full audio, emitted high-accuracy transcripts for all utterances, and terminated cleanly. Zero secret values or keys leaked into logs or artifacts.

### 8. Security & Negative Semantics
- Unauthenticated requests to administrative endpoints (`/api/models/management`) yielded HTTP 401 Unauthorized with generic error messaging.
- Requests with invalid Bearer tokens yielded HTTP 401 without reflecting token values.
- Malformed JSON payloads yielded structured HTTP 422 Unprocessable Entity responses without 500 crashes or stack traces.
- Wheel, sdist, and container images were confirmed free of `.env` files, API keys, and credential strings.
- Canonical event-store failure and cancellation semantics were verified via the multi-user and segment ledger test suites (fail-closed behavior, zero uncommitted failed events).

### 9. Release Tooling & RC Manifest (D3)
- `python release.py preflight` accepted target version 2.0.0, exact commit, exact tree, clean working tree, and verified the RC manifest.
- `python release.py dry-run` demonstrated the canonical publication order:
  `pypi -> ghcr -> dockerhub -> external_verification -> git_tag -> github_release -> final_verification -> complete`
  with `sideEffectFree: true` and zero public writes.
- **Deviation D3 Resolution:** `python release.py manifest build` natively extracted `wheelSha256` from production build manifests without KeyError, resolving the schema mismatch from W5-R02. The manifest was validated via `python release.py manifest validate` and assigned readiness state `QUALIFIED`.

---

## Conclusion

All 62 mandatory qualification gates have been evaluated with live evidence and marked **PASS**.
All historical deviations (D1 through D7) are fully resolved.
Zero new defects or blockers were identified.

Internal Candidate **W5-RC2** is qualified and **READY FOR ROOT REVIEW**.
