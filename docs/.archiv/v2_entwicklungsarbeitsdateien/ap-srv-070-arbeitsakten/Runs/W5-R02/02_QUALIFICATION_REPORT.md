# AP-SRV-070 / W5-R02 - Qualification Report

Candidate: W5-RC1 | Version: 2.0.0 | Commit: `bb7a4bb7cc27897aeb257aa5a5b9f3b550b8f602`

| Area | Result | Exact identity | Key evidence | Gate(s) |
|---|---|---|---|---|
| RC freeze | PASS | HEAD/tree exact match, workspace clean | `Evidence/00_RC_Freeze/` | G01-G05 |
| GitHub Actions | **FAIL** | Run 34112912418, 2 full attempts, both platforms | `Evidence/01_GitHub_Actions/` | G06-G09 |
| Source regression | **FAIL** (same finding as CI) | 5 unique failing tests across both platforms | `Evidence/02_Source_Regression/` | G10-G11 |
| Package build | PASS | wheel sha256 `a1902b76e8...`, sdist sha256 `5c8dad084f...` | `Evidence/03_Package_Build/` | G12-G17 |
| Windows fresh install | PASS | installed from wheel, server starts, no checkout dependency | `Evidence/04_Fresh_Install_Windows/` | G18-G19, G22 |
| Ubuntu fresh install | PASS | native WSL2 24.04, same wheel hash, server starts | `Evidence/05_Fresh_Install_Ubuntu/` | G20-G22 |
| Kroko Free | PASS | Linux fp `ab8986fd7fb93756`, Windows fp `28594e6d201fc4a7` | `Evidence/06_Kroko_Free/` | G23, G25-G27 |
| Kroko Pro (build) | PASS | Linux fp `36b440630c0a9475` (build only, no key needed) | `Evidence/07_Kroko_Pro/` | G24 |
| Free image | PASS | `voice-stt-server:2.0.0`, id `sha256:69bd5310...` | `Evidence/08_Production_Image_Free/` | G28, G30-G33 |
| Pro image | PASS | `voice-stt-server-pro:2.0.0`, id `sha256:fa58f19f...` | `Evidence/09_Production_Image_Pro/` | G29-G33 |
| Faster-Whisper E2E | INCONCLUSIVE | correct partial transcript, session ended early | `Evidence/10_Live_E2E_FasterWhisper/` | G35-G36 |
| Kroko Free E2E | INCONCLUSIVE | same pattern, different engine (rules out engine bug) | `Evidence/11_Live_E2E_Kroko_Free/` | G37 |
| Kroko Pro E2E | BLOCKED | no runtime credential in environment | `Evidence/12_Live_E2E_Kroko_Pro/` | G38 |
| Model management | PASS | discovery/refresh/custom-dir provisioning all confirmed live | `Evidence/13_Model_Management/` | G40-G41, G43-G44 |
| Persistence | PASS | full container recreate, identical SHA256 | `Evidence/13_Model_Management/` | G34, G45 |
| Shutdown | PASS | exact required ASGI lifecycle log lines, exit 0 | `Evidence/13_Model_Management/` | G46 |
| Negative/security | PASS | live auth/malformed-request/secret-leak smoke, all clean | `Evidence/16_Negative_Security/` | G47-G52 |
| Release preflight/dry-run | PASS (manifest step worked around) | dry-run `sideEffectFree:true`, exact W6 order; RC-manifest CLI bug found | `Evidence/17_Release_Preflight_DryRun/` | G53-G58 |
| RC manifest | Produced, `releaseReadiness: NOT_QUALIFIED` | sha256 `33ce8dd8a3...` | `05_RC_MANIFEST.json` | G53, G62 |
| Final git state | PASS | unchanged HEAD/tree/remote, clean tree | `Evidence/18_Final_Git_State/` | G59-G61 |

## Summary

Three independent, source-level findings drive the overall verdict, all
fully root-caused and none requiring - or receiving - any source
modification during this qualification-only run:

1. **Windows CI failure** (deterministic, 2/2): a real product code path,
   `VoiceSTT/transcription_engines/model_resolver.py::resolve_kroko_model()`,
   calls `Path.resolve()`, which on GitHub-hosted Windows runners returns
   the 8.3 short form of the runner's home directory, breaking four exact
   string-equality assertions in `tests/unit/test_kroko_onnx_engine.py`.
2. **Ubuntu CI failure** (reproduced 2/2): a timing race in
   `tests/unit/test_fastapi_server_multi_user.py` between a client-side
   cursor snapshot and the server's own replay-window query, made visible
   by the real `AutoScheduler` background task.
3. **RC-manifest tooling bug**: `tools/build_production.py` writes the
   Kroko artifact hash as `wheelSha256`; `release_tooling/cli.py`'s
   `manifest build` subcommand reads `sha256` at the same path and
   crashes with a `KeyError` on real build output. No existing unit test
   exercises this specific cross-tool integration.

Both CI findings are why `.github/workflows/ci.yml` - introduced by this
exact commit and run for the very first time in this qualification -
cannot currently be shown green on GitHub's real infrastructure without
a forbidden source change. This alone determines the overall result.

Separately, both real-engine live E2E attempts (Faster-Whisper and Kroko
Free) produced correct, non-hallucinated transcriptions for roughly the
first half of the reference audio but did not reach full-audio session
completion - an identical pattern across two structurally different
engines, pointing at the specific load-test harness/single-client
configuration rather than either engine. The Kroko Pro E2E is honestly
reported BLOCKED for lack of a credential, not faked.

Everything else attempted - package build, fresh installs on both
target platforms, Kroko Free/Pro build identity, both production images,
model management, persistence-across-recreate, graceful shutdown, and
negative/security behavior - passed cleanly with live, real evidence.

See `06_FINAL_REPORT.md` for the formal verdict and `04_DEVIATIONS.md`
for the complete deviation list.
