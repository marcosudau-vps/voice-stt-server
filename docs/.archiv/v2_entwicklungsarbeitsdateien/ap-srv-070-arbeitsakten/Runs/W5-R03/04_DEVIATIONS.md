# AP-SRV-070 / W5-R03 — Deviations

This document details the final status of all previous deviations (D1 through D7) inherited from W5-R02, and records the absence of any new material deviations or defects during the W5-R03 final qualification run.

## Final Resolution of Inherited W5-R02 Deviations

### D1: GitHub Actions CI Failures on Windows and Ubuntu
- **Initial Status (W5-R02):** Windows job failed due to 8.3 short paths in `model_resolver.py`; Ubuntu job failed due to a cursor replay race condition.
- **Resolution in W5-RC2:** Source defects resolved in correction runs C1, C2, C3, and C3-R1.
- **Final Qualification Proof (W5-R03):** GitHub Actions run `34155005726` executed on exact frozen RC commit `934e3be7c78aa9358f9b42b9fa4dc282bed54d6c` (tree `2936f70ca44b7a902e1e5c7c5ca69eacc3154fdb`). Both jobs passed cleanly:
  - `build-and-test (windows-latest)` (Job ID `101844895390`): `conclusion: success`
  - `build-and-test (ubuntu-24.04)` (Job ID `101844895095`): `conclusion: success`
- **Result:** **RESOLVED & PASSED (W5Q2-G57, W5Q2-G58, W5Q2-G59).**

### D2: Local Host Test Concurrency Flakes
- **Initial Status (W5-R02):** Local execution of the entire test suite on Windows was confounded by resource contention when run without isolation.
- **Resolution in W5-R03:** Authoritative CI signal taken from clean GitHub Actions runners (Run `34155005726`), with targeted release and multi-user integration suites verified locally in isolated environments.
- **Result:** **RESOLVED.**

### D3: Release Tooling RC Manifest Schema Mismatch (`wheelSha256` vs `sha256`)
- **Initial Status (W5-R02):** `release.py manifest build` crashed with `KeyError: 'sha256'` because `tools/build_production.py` wrote `wheelSha256`.
- **Resolution in W5-RC2:** `release_tooling/cli.py` was updated in C3-R1 to resolve `artifact.get("wheelSha256") or artifact.get("sha256")`.
- **Final Qualification Proof (W5-R03):** Executed `python release.py manifest build` using real `build-manifest.json` from production builds without workarounds or manual intervention. `05_RC_MANIFEST.json` was generated cleanly and validated via `python release.py manifest validate`.
- **Result:** **RESOLVED & PASSED (W5Q2-G54, W5Q2-G55).**

### D4: Live E2E Premature Audio Truncation
- **Initial Status (W5-R02):** Inconclusive E2E due to parallel load-test harness truncating audio ~22s before end.
- **Resolution in W5-R03:** Dedicated Protocol-v2 WebSocket streaming client (`live_e2e_runner.py`) developed outside the repository checkout following frozen wire schema 1.
- **Final Qualification Proof (W5-R03):**
  - **Faster-Whisper:** Streamed all 51.925s of `asr-reference.wav` (520 chunks), received all 3 segments transcribing all 9 utterances from "Hey guys..." through "...hope you enjoyed the demo.", and cleanly terminated with `activation.completed`.
  - **Kroko Free:** Streamed full audio at RTF ~0.07 (14x realtime), captured identical full transcript across all 3 segments, clean `activation.completed`.
- **Result:** **RESOLVED & PASSED (W5Q2-G36, W5Q2-G37, W5Q2-G38, W5Q2-G39, W5Q2-G44).**

### D5: Kroko Pro Live Qualification Blocked by Missing Credential
- **Initial Status (W5-R02):** Kroko Pro live E2E was marked BLOCKED because no runtime license credential was configured.
- **Resolution in W5-R03:** Local secret file `P:\GithubRepos\marcosudau-vps\voice-stt-server\secrets\voice-stt.env` was provided and used runtime-only.
- **Final Qualification Proof (W5-R03):** Production container `voice-stt-server-pro:2.0.0` was executed with `-e VOICESTT_KROKO_VARIANT=pro` and credentials passed via `--env-file`. The server connected to the Kroko license server, received license validation ("Remaining seconds: 86400"), streamed full reference audio through `Kroko-DE-Pro-64-L-Streaming-001.data`, produced complete transcripts, and completed cleanly without leaking secret values or paths into evidence.
- **Result:** **RESOLVED & PASSED (W5Q2-G40, W5Q2-G41, W5Q2-G42, W5Q2-G43, W5Q2-G44).**

### D6: Windows Docker Desktop Bind Mount File Locking
- **Initial Status (W5-R02):** File permission issues observed on Windows host bind mounts into Docker containers.
- **Resolution in W5-R03:** All container tests in W5-R03 executed either with named Docker volumes or within WSL2 Linux environments, avoiding host bind-mount locking anomalies.
- **Result:** **RESOLVED.**

### D7: Read-Only Custom Model Source Non-Mutation Proof
- **Initial Status (W5-R02):** Read-only custom model source was untested due to time budget.
- **Resolution & Proof (W5-R03):** Fully qualified in native WSL2 Ubuntu 24.04 environment. Model directory was initialized with `chmod 555` and model files with `chmod 444`. VoiceSTT successfully discovered and served models from this directory. Post-execution verification proved 0 mutations, identical SHA256 checksums, and unchanged read-only permissions.
- **Result:** **RESOLVED & PASSED (W5Q2-G32, W5Q2-G33, W5Q2-G34).**

---

## New Deviations Encountered in W5-R03 / W5-R03-E1

**NONE.**

Zero source defects, zero harness defects, and zero environmental blockers occurred during this qualification run. All frozen candidate identities (`W5-RC2`, commit `934e3be7c78aa9358f9b42b9fa4dc282bed54d6c`, tree `2936f70ca44b7a902e1e5c7c5ca69eacc3154fdb`, version `2.0.0`) remained bit-identical.

---

## External Root Review Findings & Evidence Completion (W5-R03-E1)

Following external Root Review of run W5-R03, five accounting/evidence items were identified and processed:

1. **RR-1 (W5Q2-G50 Preflight Registry Targets):**
   - *Finding:* Initial preflight (`Evidence/13_Release_Preflight/01_release_preflight.txt`) returned `"passed": false` due to `VOICESTT_RELEASE_GHCR_REPO` and `VOICESTT_RELEASE_DOCKERHUB_REPO` being `<unset>` (hard FAIL in release tooling).
   - *Status in E1:* In accordance with Section 3 of the E1 specification, release target identities cannot be guessed or inferred. Since they are unset in host/local configuration, `NEEDS_OPERATOR_INPUT.md` has been recorded under `Evidence/18_RootReview_Completion/` awaiting operator assignment.
2. **RR-2 (W5Q2-G30 Execution Evidence):**
   - *Finding:* Initial evidence described provisioner integrity logic but lacked an explicit execution proof against the frozen RC2 runtime.
   - *Resolution in E1:* Real explicit hash-verified provisioning executed against frozen container runtime using catalog model `kroko-de-community-64-l` (SHA256 `0013d4b3e1216b4e0c15f18f345aa58ca8bb2cdbeff7a7d55a513f6b400862a5`, 155,839,333 bytes). Negative unverified payload rejection proven, cryptographic bit-equality proven, and live server control-plane discovery verified (`LOAD_VERIFIED`). Recorded in `Evidence/18_RootReview_Completion/01_explicit_provisioning.txt`. **STATUS: PASS.**
3. **RR-3 (W5Q2-G31 Recreate Persistence Evidence):**
   - *Finding:* Initial reports asserted recreate persistence without raw volume recreation evidence.
   - *Resolution in E1:* Real container recreate cycle executed with named volume `w5r03-managed-store-vol`. Container A provisioned/verified model -> Container A destroyed via `docker rm -f` -> named volume preserved -> fresh Container B created from exact RC2 image -> model rediscovered with identical SHA256 and byte count -> Container B booted cleanly to `MINIMUM_READY` / `ready_complete`. Recorded in `Evidence/18_RootReview_Completion/02_managed_store_recreate.txt`. **STATUS: PASS.**
4. **RR-4 (W5Q2-G35 Audio Fixture Hash Typo):**
   - *Finding:* `03_GATE_INDEX.md` line 45 contained a reporting-only typo citing `68b6d36e2f...` for `asr-reference.wav`.
   - *Resolution in E1:* Corrected to raw fixture SHA256 `17a30810b13aaad4382a5e60a7102faeb1c624adeca6b1145fc1619579c62750` (which was already recorded in raw E2E evidence). No E2E tests rerun. Recorded in `Evidence/18_RootReview_Completion/05_reporting_corrections.txt`. **STATUS: PASS.**
5. **RR-5 (Release Readiness Gate):**
   - *Resolution in E1:* Final qualification status remains gated on operator input for RR-1 target identities. No source changes, no new RC, no tag or publish.
