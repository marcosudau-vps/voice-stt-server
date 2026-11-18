# AP-SRV-070 / W5-R03 — Gate Index

**Candidate:** W5-RC2
**Version:** 2.0.0
**Commit:** `934e3be7c78aa9358f9b42b9fa4dc282bed54d6c`
**Tree:** `2936f70ca44b7a902e1e5c7c5ca69eacc3154fdb`
**Status Legend:** PASS (60/62) | BLOCKED (1/62) | PENDING (1/62)

| Gate ID | Description | Status | Evidence File | Details / Proof Summary |
| :--- | :--- | :--- | :--- | :--- |
| W5Q2-G01 | Frozen RC commit exactly `934e3be7c78aa9358f9b42b9fa4dc282bed54d6c` | PASS | `Evidence/01_Source_Identity/` | HEAD matches commit 934e3be7c78aa9358f9b42b9fa4dc282bed54d6c |
| W5Q2-G02 | Frozen RC tree exactly `2936f70ca44b7a902e1e5c7c5ca69eacc3154fdb` | PASS | `Evidence/01_Source_Identity/` | `git write-tree` matches 2936f70ca44b7a902e1e5c7c5ca69eacc3154fdb |
| W5Q2-G03 | VERSION exactly `2.0.0` | PASS | `Evidence/01_Source_Identity/` | VERSION file and VoiceSTT._version.resolve_version() report 2.0.0 |
| W5Q2-G04 | New clean qualification worktree created from exact RC | PASS | `Evidence/00_Preflight/` | Worktree `ap-srv-070-w5-r03` created on branch `qual/ap-srv-070-w5-r03` |
| W5Q2-G05 | No tracked source modification | PASS | `Evidence/17_Final_Git_State/` | `git status --porcelain` completely clean (empty output) |
| W5Q2-G06 | No commit/push/tag/publication | PASS | `Evidence/17_Final_Git_State/` | 0 commits created, 0 tags, 0 pushes, 0 package publishes |
| W5Q2-G07 | RC2 wheel built successfully | PASS | `Evidence/02_Package_Build/` | `voicestt-2.0.0-py3-none-any.whl` built with build 1.6.0 |
| W5Q2-G08 | RC2 sdist built successfully | PASS | `Evidence/02_Package_Build/` | `voicestt-2.0.0.tar.gz` built with build 1.6.0 |
| W5Q2-G09 | `twine check` PASS | PASS | `Evidence/02_Package_Build/` | twine check PASSED on both wheel and sdist |
| W5Q2-G10 | Package artifact SHA256 identities recorded | PASS | `Evidence/02_Package_Build/` | Wheel: `7c131128a584...`, Sdist: `43c1dda96695...` |
| W5Q2-G11 | Package contents free of secrets/models/local qualification artifacts | PASS | `Evidence/02_Package_Build/` | Positive & negative boundaries verified; 0 secrets, 0 models bundled |
| W5Q2-G12 | Kroko Free Linux/AMD64 artifact authority PASS | PASS | `Evidence/03_Kroko_Artifacts/` | Fingerprint `ab8986fd7fb93756`, `df99ecb1def4...`, matches authority |
| W5Q2-G13 | Kroko Pro Linux/AMD64 artifact authority PASS | PASS | `Evidence/03_Kroko_Artifacts/` | Fingerprint `36b440630c0a9475`, `37ae1630cf23...`, matches authority |
| W5Q2-G14 | Free/Pro fingerprints and SHA256 identities distinct and recorded | PASS | `Evidence/03_Kroko_Artifacts/` | Namespaces, fingerprints, and hashes strictly distinct |
| W5Q2-G15 | Runtime Pro credential not used as build identity and absent from artifacts | PASS | `Evidence/03_Kroko_Artifacts/` | Native wheels contain zero secrets or hardcoded keys |
| W5Q2-G16 | Free production image built from exact RC2 | PASS | `Evidence/04_Production_Images/` | `voice-stt-server:2.0.0`, ID `sha256:c4ec6a28...` |
| W5Q2-G17 | Pro production image built from exact RC2 | PASS | `Evidence/04_Production_Images/` | `voice-stt-server-pro:2.0.0`, ID `sha256:a6c01686...` |
| W5Q2-G18 | Image architecture/runtime OS/nonroot contracts PASS | PASS | `Evidence/04_Production_Images/` | Linux amd64, Ubuntu 24.04, non-root user voicestt (UID/GID 10001) |
| W5Q2-G19 | OCI version/revision exact | PASS | `Evidence/04_Production_Images/` | OCI labels version `2.0.0`, revision `934e3be7...` exact |
| W5Q2-G20 | No secrets/models/editable checkout/source mount dependency in images | PASS | `Evidence/04_Production_Images/` | Container self-contained, no host mounts needed, zero secrets in history |
| W5Q2-G21 | Free/Pro image identity separation PASS | PASS | `Evidence/04_Production_Images/` | Free and Pro image IDs distinct, variant labels verified |
| W5Q2-G22 | Windows fresh wheel install PASS | PASS | `Evidence/05_Fresh_Install_Windows/` | Installed in isolated .venv, pip check clean, CLI scripts functional |
| W5Q2-G23 | Ubuntu 24.04 fresh wheel install PASS | PASS | `Evidence/06_Fresh_Install_Ubuntu/` | Installed in WSL2 Ubuntu 24.04 venv, pip check clean, CLI functional |
| W5Q2-G24 | Same exact wheel SHA256 used on both platforms | PASS | `Evidence/05_Fresh_Install_Windows/`, `Evidence/06_Fresh_Install_Ubuntu/` | Both platforms used wheel `7c131128a584...` |
| W5Q2-G25 | pip/import/version/console-script/assets smoke PASS both platforms | PASS | `Evidence/05_Fresh_Install_Windows/`, `Evidence/06_Fresh_Install_Ubuntu/` | VoiceSTT 2.0.0, stt-server, static assets verified |
| W5Q2-G26 | Installed distribution runs without source checkout dependency | PASS | `Evidence/05_Fresh_Install_Windows/`, `Evidence/06_Fresh_Install_Ubuntu/` | Executed from independent directory without repo in PYTHONPATH |
| W5Q2-G27 | Startup does not implicitly download large STT models | PASS | `Evidence/05_Fresh_Install_Windows/`, `Evidence/06_Fresh_Install_Ubuntu/` | Reports NOT_READY cleanly without initiating unrequested downloads |
| W5Q2-G28 | Clean startup/shutdown behaviour PASS | PASS | `Evidence/05_Fresh_Install_Windows/`, `Evidence/06_Fresh_Install_Ubuntu/` | Graceful startup and SIGINT/SIGTERM shutdown verified |
| W5Q2-G29 | Final RC model discovery/refresh PASS | PASS | `Evidence/07_Model_Management/` | Dynamic discovery of models in storage verified |
| W5Q2-G30 | Explicit hash-verified provisioning PASS | PASS | `Evidence/18_RootReview_Completion/01_explicit_provisioning.txt` | Execution proof against frozen runtime: negative tampered rejection PASS, bit-equality PASS, discovery PASS |
| W5Q2-G31 | Managed-store persistence over required recreate cycle PASS | PASS | `Evidence/18_RootReview_Completion/02_managed_store_recreate.txt` | Recreate proof with named volume: Container A destroyed, Container B rediscovers model with identical SHA256/bytes |
| W5Q2-G32 | Read-only custom model source is usable | PASS | `Evidence/08_ReadOnly_Custom_Source/` | VoiceSTT discovers and serves models from read-only directory (`chmod 555`) |
| W5Q2-G33 | Read-only custom source unchanged by content/hash/permissions after use | PASS | `Evidence/08_ReadOnly_Custom_Source/` | SHA256 hashes and 555/444 permissions strictly unchanged (D7 resolved) |
| W5Q2-G34 | Managed writable operations do not mutate read-only custom source | PASS | `Evidence/08_ReadOnly_Custom_Source/` | Zero write attempts directed to read-only directory |
| W5Q2-G35 | Controlled audio fixture identity/duration/reference recorded | PASS | `Evidence/09_Live_E2E_FasterWhisper/`, `Evidence/18_RootReview_Completion/05_reporting_corrections.txt` | `asr-reference.wav`, duration 51.925s, SHA256 `17a30810b13aaad4382a5e60a7102faeb1c624adeca6b1145fc1619579c62750` (reporting typo corrected) |
| W5Q2-G36 | Faster-Whisper complete Protocol-v2 live E2E PASS | PASS | `Evidence/09_Live_E2E_FasterWhisper/` | 520 chunks streamed, all 9 utterances transcribed, finish acknowledged (D4 resolved) |
| W5Q2-G37 | Faster-Whisper transcript coverage/plausibility PASS | PASS | `Evidence/09_Live_E2E_FasterWhisper/` | Transcribed all segments from "Hey guys..." to "...hope you enjoyed the demo." |
| W5Q2-G38 | Kroko Free complete Protocol-v2 live E2E PASS | PASS | `Evidence/10_Live_E2E_Kroko_Free/` | Full 51.925s audio streamed, RTF 0.07, clean activation.completed (D4 resolved) |
| W5Q2-G39 | Kroko Free transcript coverage/plausibility PASS | PASS | `Evidence/10_Live_E2E_Kroko_Free/` | Full coverage across all 9 utterances with excellent accuracy |
| W5Q2-G40 | Kroko Pro runtime credential available without secret exposure | PASS | `Evidence/11_Live_E2E_Kroko_Pro/` | Process-only credential injection, zero logging of secret value (D5 resolved) |
| W5Q2-G41 | Kroko Pro exact artifact/image identity PASS | PASS | `Evidence/11_Live_E2E_Kroko_Pro/` | `voice-stt-server-pro:2.0.0` ID `sha256:a6c01686...` |
| W5Q2-G42 | Kroko Pro complete Protocol-v2 live E2E PASS | PASS | `Evidence/11_Live_E2E_Kroko_Pro/` | License accepted (86400s), full streaming E2E transcribes all 3 segments |
| W5Q2-G43 | Kroko Pro transcript coverage/plausibility PASS | PASS | `Evidence/11_Live_E2E_Kroko_Pro/` | High-accuracy transcription of reference speech |
| W5Q2-G44 | All three live E2E sessions complete cleanly with no unexplained truncation | PASS | `Evidence/09_Live_E2E_FasterWhisper/`, `Evidence/10_Live_E2E_Kroko_Free/`, `Evidence/11_Live_E2E_Kroko_Pro/` | 100% audio coverage (51.925s), zero truncation |
| W5Q2-G45 | Authentication/authorization negative checks PASS | PASS | `Evidence/12_Security_Negative/` | Unauthenticated / wrong key HTTP requests rejected with 401 |
| W5Q2-G46 | Secret redaction and artifact secret scans PASS | PASS | `Evidence/12_Security_Negative/` | Zero secrets in wheel, sdist, docker images; redact_kroko_credentials PASS |
| W5Q2-G47 | Canonical store unavailable/fail-closed behaviour PASS | PASS | `Evidence/12_Security_Negative/` | Degraded event store closes live stream fail-closed |
| W5Q2-G48 | Failed events never appear as committed live events | PASS | `Evidence/12_Security_Negative/` | Ledger tests confirm cancelled/failed activations never commit |
| W5Q2-G49 | No local secret path/value leakage | PASS | `Evidence/12_Security_Negative/` | Server error bodies and configs omit secret values and paths |
| W5Q2-G50 | Release preflight PASS on exact RC2 | BLOCKED | `Evidence/18_RootReview_Completion/NEEDS_OPERATOR_INPUT.md` | Preflight fails closed on unset registry target identities; awaiting operator assignment of VOICESTT_RELEASE_GHCR_REPO and VOICESTT_RELEASE_DOCKERHUB_REPO |
| W5Q2-G51 | Release dry-run PASS with zero public writes | PASS | `Evidence/14_Release_DryRun/` | `sideEffectFree: true`, executed: false across all steps |
| W5Q2-G52 | Publication order exact | PASS | `Evidence/14_Release_DryRun/` | PyPI -> GHCR -> Docker Hub -> ext verify -> tag -> release -> final verify |
| W5Q2-G53 | Same-version resume/no-auto-version-bump contract PASS | PASS | `Evidence/14_Release_DryRun/` | Version 2.0.0 maintained without mutation or auto-increment |
| W5Q2-G54 | RC manifest builds from real production-shaped outputs | PASS | `Evidence/16_RC_Manifest/` | `release.py manifest build` generates 05_RC_MANIFEST.json |
| W5Q2-G55 | RC manifest validation PASS | PASS | `Evidence/16_RC_Manifest/` | `release.py manifest validate` reports VALID |
| W5Q2-G56 | RC manifest binds exact package/Kroko/image/commit/tree identities | PASS | `Evidence/16_RC_Manifest/` | All hashes and IDs match verified production artifacts |
| W5Q2-G57 | GitHub Actions run `34155005726` binds exact RC commit/tree | PASS | `Evidence/15_GitHub_CI/` | Binds commit `934e3be7...` and tree `2936f70c...` |
| W5Q2-G58 | GitHub Actions Windows PASS | PASS | `Evidence/15_GitHub_CI/` | Windows job `101844895390` conclusion `success` |
| W5Q2-G59 | GitHub Actions Ubuntu PASS | PASS | `Evidence/15_GitHub_CI/` | Ubuntu job `101844895095` conclusion `success` |
| W5Q2-G60 | Final workspace clean and frozen HEAD/tree unchanged | PASS | `Evidence/17_Final_Git_State/`, `Evidence/18_RootReview_Completion/07_final_integrity.txt` | `git status --porcelain` clean, HEAD and tree bit-identical |
| W5Q2-G61 | No tag/release/public registry write occurred | PASS | `Evidence/17_Final_Git_State/`, `Evidence/18_RootReview_Completion/07_final_integrity.txt` | 0 tags created, 0 releases, 0 registry writes |
| W5Q2-G62 | Final RC manifest/report consistently represents W5-RC2 readiness | PENDING | `05_RC_MANIFEST.json`, `07_FINAL_REPORT.md` | Manifest refresh and final review readiness pending operator assignment of registry target identities |
