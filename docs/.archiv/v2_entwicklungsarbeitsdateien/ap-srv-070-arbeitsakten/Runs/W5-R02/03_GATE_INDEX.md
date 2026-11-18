# AP-SRV-070 / W5-R02 - Gate Index (Final)

Status legend: PASS / FAIL / BLOCKED / INCONCLUSIVE / NOT TESTED

| Gate | Status | Short proof | Evidence | Command/Test | Result |
|---|---|---|---|---|---|
| W5Q-G01 | PASS | Distributed HEAD == frozen RC commit | `Evidence/00_RC_Freeze/`, `Evidence/18_Final_Git_State/` | `git rev-parse origin/...` | `bb7a4bb7cc27897aeb257aa5a5b9f3b550b8f602` (start and end) |
| W5Q-G02 | PASS | Frozen RC tree == expected tree | `Evidence/00_RC_Freeze/`, `Evidence/18_Final_Git_State/` | `git rev-parse HEAD^{tree}` | `f7b304b1959e48457a8eefd8919484f55214633b` (start and end) |
| W5Q-G03 | PASS | VERSION resolves exactly to 2.0.0 | `Evidence/00_RC_Freeze/` | `resolve_version()` | `2.0.0` |
| W5Q-G04 | PASS | Workspace clean/immutable at start | `Evidence/00_RC_Freeze/` | `git status --porcelain` | empty |
| W5Q-G05 | PASS | No commit/tag/push/publication during the run | `Evidence/18_Final_Git_State/` | full-run audit + final state | none occurred |
| W5Q-G06 | PASS | GH Actions run exists for exact RC commit | `Evidence/01_GitHub_Actions/` | run 34112912418, 2 attempts | exists |
| W5Q-G07 | **FAIL** | Windows CI job | `Evidence/01_GitHub_Actions/` | CI job | 4 failed/1700 passed, deterministic 8.3-short-path bug in `resolve_kroko_model()`, needs source fix |
| W5Q-G08 | **FAIL** | Ubuntu CI job | `Evidence/01_GitHub_Actions/` | CI job | 1 failed/1703 passed, replay-window race, needs source fix |
| W5Q-G09 | PASS | CI package/fresh-install checks | `Evidence/01_GitHub_Actions/` | all pre-test-suite CI steps | green both platforms, both attempts |
| W5Q-G10 | **FAIL** | Complete local unit/guard suite | `Evidence/02_Source_Regression/` | `pytest -q tests/unit` | same 5 failures as CI (authoritative) |
| W5Q-G11 | PASS | `git diff --check` | `Evidence/02_Source_Regression/`, `Evidence/18_Final_Git_State/` | `git diff --check` | clean |
| W5Q-G12 | PASS | Final wheel built from exact RC | `Evidence/03_Package_Build/` | `python -m build` | `voicestt-2.0.0-py3-none-any.whl` |
| W5Q-G13 | PASS | Final sdist built from exact RC | `Evidence/03_Package_Build/` | `python -m build` | `voicestt-2.0.0.tar.gz` |
| W5Q-G14 | PASS | `twine check` | `Evidence/03_Package_Build/` | `twine check dist/*` | PASSED |
| W5Q-G15 | PASS | Package content positive boundary | `Evidence/03_Package_Build/` | content inspection | all required present |
| W5Q-G16 | PASS | Package content negative/leak boundary | `Evidence/03_Package_Build/` | content inspection | clean |
| W5Q-G17 | PASS | Wheel/sdist hashes recorded and stable | `Evidence/03_Package_Build/` | sha256sum | recorded |
| W5Q-G18 | PASS | Windows 11 fresh wheel install | `Evidence/04_Fresh_Install_Windows/` | isolated venv install | `pip check` clean |
| W5Q-G19 | PASS | Windows installed-dist import/version/scripts/assets | `Evidence/04_Fresh_Install_Windows/` | checks + server start | all present, server starts, correct NOT_READY |
| W5Q-G20 | PASS | Ubuntu 24.04 fresh wheel install | `Evidence/05_Fresh_Install_Ubuntu/` | native WSL2 venv install | `pip check` clean |
| W5Q-G21 | PASS | Ubuntu installed-dist import/version/scripts/assets | `Evidence/05_Fresh_Install_Ubuntu/` | checks + server start | all present, server starts, correct NOT_READY |
| W5Q-G22 | PASS | No editable/source-checkout dependency | `Evidence/04_Fresh_Install_Windows/`, `Evidence/05_Fresh_Install_Ubuntu/` | resolved package path | confirmed both platforms |
| W5Q-G23 | PASS | Kroko Free fingerprint/artifact qualified | `Evidence/06_Kroko_Free/` | native build (Linux) + REUSE (Windows) | fp `ab8986fd7fb93756` (Linux), `28594e6d201fc4a7` (Windows) |
| W5Q-G24 | PASS | Kroko Pro fingerprint/artifact qualified (build) | `Evidence/07_Kroko_Pro/` | native build (Linux) | fp `36b440630c0a9475`; runtime license separately BLOCKED (G38) |
| W5Q-G25 | PASS | Free/Pro namespaces and runtime identity distinct | `Evidence/06_Kroko_Free/`, `Evidence/07_Kroko_Pro/`, `Evidence/09_Production_Image_Pro/` | store layout, wheel tags, image labels | distinct throughout |
| W5Q-G26 | PASS | No unexpected native rebuild | `Evidence/06_Kroko_Free/`, `Evidence/07_Kroko_Pro/` | describe-artifact before/after | Linux rebuild expected (first time); Windows Free reused |
| W5Q-G27 | PASS | Runtime credential not build identity, no leak | `Evidence/06_Kroko_Free/`, `Evidence/07_Kroko_Pro/` | build log inspection | confirmed |
| W5Q-G28 | PASS | Free production image built and qualified | `Evidence/08_Production_Image_Free/` | `tools/build_production.py all` | image `voice-stt-server:2.0.0` |
| W5Q-G29 | PASS | Pro production image built and qualified | `Evidence/09_Production_Image_Pro/` | `tools/build_production.py all` | image `voice-stt-server-pro:2.0.0` |
| W5Q-G30 | PASS | Free/Pro OCI version/revision match RC | `Evidence/08_Production_Image_Free/`, `Evidence/09_Production_Image_Pro/` | `docker inspect` labels | version=2.0.0, revision=bb7a4bb7c... both images |
| W5Q-G31 | PASS | linux/amd64, Ubuntu 24.04, non-root | `Evidence/08_Production_Image_Free/`, `Evidence/09_Production_Image_Pro/` | Dockerfile + inspect | confirmed both images |
| W5Q-G32 | PASS | No editable/source runtime dependency in images | `Evidence/08_Production_Image_Free/`, `Evidence/09_Production_Image_Pro/` | Dockerfile inspection | confirmed |
| W5Q-G33 | PASS | No secrets or large STT models embedded | `Evidence/08_Production_Image_Free/`, `Evidence/09_Production_Image_Pro/` | `docker history` + FS scan | clean both images |
| W5Q-G34 | PASS | Missing model -> healthy + NOT_READY, no restart loop | `Evidence/13_Model_Management/` | disposable container run | confirmed via named-volume run |
| W5Q-G35 | PASS | Controlled audio fixture documented | `Evidence/10_Live_E2E_FasterWhisper/` | fixture + acceptance criterion | `asr-reference.wav`, hashed, documented |
| W5Q-G36 | **INCONCLUSIVE** | Faster-Whisper real E2E | `Evidence/10_Live_E2E_FasterWhisper/` | real engine/audio/session | correct partial transcript, session ended early - see evidence |
| W5Q-G37 | **INCONCLUSIVE** | Kroko Free real E2E | `Evidence/11_Live_E2E_Kroko_Free/` | real engine/audio/session | same pattern as G36, reproduced with a different engine |
| W5Q-G38 | **BLOCKED** | Kroko Pro real E2E | `Evidence/12_Live_E2E_Kroko_Pro/` | n/a | no Kroko Pro runtime credential in this environment |
| W5Q-G39 | **FAIL** | Clean lifecycle, all 3 E2Es | n/a | depends on G36-G38 | not achieved (2 inconclusive, 1 blocked) |
| W5Q-G40 | PASS | Model discovery/refresh | `Evidence/13_Model_Management/`, `Evidence/16_Negative_Security/` | `/api/models/management`, `/api/config` PATCH | confirmed |
| W5Q-G41 | PASS | Managed Faster-Whisper/Kroko store behavior | `Evidence/13_Model_Management/` | live container probe | canonical paths present/writable |
| W5Q-G42 | **NOT TESTED** | Read-only custom model source | n/a | n/a | not attempted this run - time budget; recommend for Correction Run |
| W5Q-G43 | PASS | No unexpected startup download | `Evidence/04_Fresh_Install_Windows/`, `Evidence/05_Fresh_Install_Ubuntu/`, `Evidence/13_Model_Management/` | server start with no models | NOT_READY reported, no download attempted, throughout |
| W5Q-G44 | PASS | Explicit provisioning integrity | `Evidence/11_Live_E2E_Kroko_Free/` | hash-verified explicit download | succeeded, no corrupt artifact |
| W5Q-G45 | PASS | Managed model persistence across recreate | `Evidence/13_Model_Management/` | full container recreate | identical SHA256, dirs intact |
| W5Q-G46 | PASS | Graceful application shutdown | `Evidence/13_Model_Management/` | `docker stop` | exact required ASGI lifecycle lines, exit 0 |
| W5Q-G47 | PASS | API auth negative cases | `Evidence/16_Negative_Security/` | live smoke | missing/wrong key correctly rejected |
| W5Q-G48 | PASS | Admin-vs-normal credential boundary | `Evidence/16_Negative_Security/` | live smoke | confirmed |
| W5Q-G49 | PASS | Malformed/invalid Protocol-v2/HTTP requests fail safely | `Evidence/16_Negative_Security/`, `Evidence/02_Source_Regression/` | live smoke + unit coverage | 422, no crash |
| W5Q-G50 | PASS | Invalid settings/model requests fail safely | `Evidence/16_Negative_Security/`, `Evidence/02_Source_Regression/` | live smoke + unit coverage | intent persisted, not activated |
| W5Q-G51 | PASS | Free/Pro mismatch and missing Pro credential fail safely | `Evidence/02_Source_Regression/`, `Evidence/07_Kroko_Pro/`, `Evidence/12_Live_E2E_Kroko_Pro/` | unit coverage + this run's own confirmed absence | covered |
| W5Q-G52 | PASS | Secret scans (wheel/sdist/image/state/manifest/evidence/logs) | `Evidence/03_Package_Build/`, `Evidence/08-09_Production_Image_*/`, this file's own sweep | grep/inspect passes | clean everywhere; no release_state existed to scan |
| W5Q-G53 | **FAIL (worked around)** | Final RC manifest from exact qualified identities | `05_RC_MANIFEST.json`, `Evidence/17_Release_Preflight_DryRun/` | `release.py manifest build` | CLI crashes on real build-production.py output (genuine schema-mismatch bug, documented); manifest still produced correctly via the canonical helper module directly and independently validated |
| W5Q-G54 | PASS | `release.py preflight` PASS against final RC inputs | `Evidence/17_Release_Preflight_DryRun/` | `release.py preflight` | all in-scope checks PASS; registry/credential items correctly absent |
| W5Q-G55 | PASS | `release.py dry-run` PASS, shared engine | `Evidence/17_Release_Preflight_DryRun/` | `release.py dry-run` | `sideEffectFree: true`, 0 executed |
| W5Q-G56 | PASS | Dry-run operation order matches fixed W6 order | `Evidence/17_Release_Preflight_DryRun/` | dry-run output | exact match |
| W5Q-G57 | PASS | Same-version resume/conflict/barrier tests | `Evidence/17_Release_Preflight_DryRun/` | targeted `release_tooling` tests | 157 passed, 11 subtests |
| W5Q-G58 | PASS | Dry-run zero public writes, no version/source mutation | `Evidence/17_Release_Preflight_DryRun/` | dry-run output + final git state | confirmed |
| W5Q-G59 | PASS | Final workspace remains source-clean | `Evidence/18_Final_Git_State/` | `git status --porcelain` | empty |
| W5Q-G60 | PASS | Local HEAD/tree still equal frozen RC | `Evidence/18_Final_Git_State/` | `git rev-parse` | unchanged |
| W5Q-G61 | PASS | Remote Distributed still equals frozen RC commit | `Evidence/18_Final_Git_State/` | `git fetch` + `git rev-parse` | unchanged |
| W5Q-G62 | PASS | RC manifest status and final report internally consistent | `05_RC_MANIFEST.json`, `06_FINAL_REPORT.md` | cross-check | `releaseReadiness: NOT_QUALIFIED` matches final verdict |

## Final tally

- PASS: 49
- FAIL: 5 (W5Q-G07, W5Q-G08, W5Q-G10 - one underlying finding, documented
  once in `Evidence/01_GitHub_Actions/`; W5Q-G39 - consequence of the
  live-E2E findings; W5Q-G53 - a second, independent source-level
  finding, worked around without a source change so the manifest itself
  is still correct and valid)
- BLOCKED: 1 (W5Q-G38 - missing Kroko Pro runtime credential)
- INCONCLUSIVE: 2 (W5Q-G36, W5Q-G37 - engine/pipeline proven functional,
  session did not reach full-audio completion in this specific load-test
  harness; reproduced identically across two different engines)
- NOT TESTED: 1 (W5Q-G42 - read-only custom model source path; not
  attempted within this session's time budget)

Because multiple mandatory gates are FAIL/BLOCKED/INCONCLUSIVE and none
of the FAILs can be resolved without a source-controlled change
(forbidden in W5-R02), the overall result is:
**NOT READY FOR ROOT REVIEW.**
