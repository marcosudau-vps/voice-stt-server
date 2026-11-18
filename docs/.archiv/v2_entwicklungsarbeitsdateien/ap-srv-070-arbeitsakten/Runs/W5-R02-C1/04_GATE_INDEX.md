# AP-SRV-070 / W5-R02-C1 - Gate Index

| Gate | Status | Short proof | Evidence | Command/Test | Result |
|---|---|---|---|---|---|
| W5C2-G01 | PASS | Start commit/tree exactly match W5-RC1/Distributed | `Evidence/00_Preflight/` | `git rev-parse origin/...` | `bb7a4bb7cc27897aeb257aa5a5b9f3b550b8f602` / `f7b304b1959e48457a8eefd8919484f55214633b` |
| W5C2-G02 | PASS | New clean correction workspace; frozen W5-R02 workspace untouched | `Evidence/00_Preflight/` | `git worktree add`, `git worktree list` | new worktree at `ap-srv-070-w5-r02-c1`, frozen one unvisited |
| W5C2-G03 | PASS | Correction plan created before first source edit | `02_PLAN.md` | plan file predates all `Edit` calls | plan written before any test/source change |
| W5C2-G04 | PASS | VERSION remains exactly 2.0.0 | `Evidence/08_Final_Git_State/` | `cat VERSION` | `2.0.0` |
| W5C2-G05 | PASS | No tag/push/public release performed | `Evidence/08_Final_Git_State/` | full-run audit | none occurred |
| W5C2-G06 | PASS | Affected Kroko tests compare semantic file identity | `Evidence/01_Windows_Path_Contract/` | `assertSameFile()`/`os.path.samefile()` | implemented |
| W5C2-G07 | PASS | Resolver production semantics preserved | `Evidence/01_Windows_Path_Contract/` | `model_resolver.py` diff (none) | file not edited |
| W5C2-G08 | PASS | Four previously-failing Windows Kroko tests PASS | `Evidence/01_Windows_Path_Contract/` | `pytest tests/unit/test_kroko_onnx_engine.py` | all 4 pass |
| W5C2-G09 | PASS | Full Kroko engine unit-test file PASS | `Evidence/01_Windows_Path_Contract/` | same run | 29 passed, 1 skipped, 4 subtests |
| W5C2-G10 | PASS | Wrong-file/precedence/missing-model protections remain tested | `Evidence/01_Windows_Path_Contract/` | unchanged tests still pass | confirmed |
| W5C2-G11 | PASS | Test reflects valid replay events between snapshot and completion | `Evidence/02_Ubuntu_Replay_Race/` | code diff | loop-based replay consumption |
| W5C2-G12 | PASS | Outage/recovery semantics remain strictly asserted | `Evidence/02_Ubuntu_Replay_Race/` | code diff | unchanged |
| W5C2-G13 | PASS | Previously-failing Ubuntu test passes repeatedly (>=20) | `Evidence/02_Ubuntu_Replay_Race/` | 20x loop run | 20/20 pass |
| W5C2-G14 | PASS | Relevant surrounding Ubuntu test class/file PASS | `Evidence/02_Ubuntu_Replay_Race/` | full file run (native fs) | 113 passed, 1 skipped, 0 failed |
| W5C2-G15 | PASS | RC-manifest CLI consumes canonical `wheelSha256` | `Evidence/03_RC_Manifest_Contract/` | `_extract_kroko_artifact_sha256` | implemented |
| W5C2-G16 | PASS | Legacy `sha256` fallback unambiguous, fail-closed on conflict | `Evidence/03_RC_Manifest_Contract/` | 2 new tests | fallback + fail-closed both proven |
| W5C2-G17 | PASS | Contract test uses real production-manifest schema/code boundary | `Evidence/03_RC_Manifest_Contract/` | `ManifestBuildCommandTests` | uses real `bp.resolve_kroko_wheel()` |
| W5C2-G18 | PASS | End-to-end `manifest build` succeeds with production-shaped input | `Evidence/03_RC_Manifest_Contract/`, `Evidence/07_Package_Release_Tooling/` | unit test + real CLI invocation | both succeed |
| W5C2-G19 | PASS | Resulting manifest validates, identities preserved | `Evidence/03_RC_Manifest_Contract/` | assertions on written manifest | fingerprints/hashes/commit/tree preserved |
| W5C2-G20 | PASS | Targeted correction test suite PASS | `Evidence/04_Targeted_Tests/` | see below | all green |
| W5C2-G21 | PASS | Full Windows unit suite PASS in stable environment | `Evidence/05_Windows_Regression/` | `pytest -q tests/unit` | 1709 passed, 13 skipped, 985 subtests, 0 failed |
| W5C2-G22 | PASS | Full Ubuntu 24.04 unit suite PASS in stable environment | `Evidence/06_Ubuntu_Regression/` | `pytest -q tests/unit` (native fs) | 1708 passed, 14 skipped, 985 subtests, 0 failed |
| W5C2-G23 | PASS | Package/release-tool smoke PASS | `Evidence/07_Package_Release_Tooling/` | build, twine, manifest build/validate, dry-run | all PASS, no public write |
| W5C2-G24 | PASS | `git diff --check` PASS | `Evidence/05_Windows_Regression/` | `git diff --check` | clean |
| W5C2-G25 | PASS | Final adversarial diff review finds no unrelated scope expansion | this file / `03_CORRECTION_REPORT.md` | `git diff --stat`, per-file diff review | exactly 4 files, 328 insertions/15 deletions, matches plan exactly |
| W5C2-G26 | PASS | Exactly one local W5-R02-C1 correction commit ahead of Distributed | `Evidence/08_Final_Git_State/` | `git rev-list --count` | `1` |
| W5C2-G27 | PASS | Final workspace clean | `Evidence/08_Final_Git_State/` | `git status --porcelain` | empty |
| W5C2-G28 | PASS | Remote Distributed remains `bb7a4bb7c...`; no push | `Evidence/08_Final_Git_State/` | `git fetch` + `git rev-parse` | unchanged, no push issued |

## Targeted correction test suite detail (W5C2-G20)

- `pytest -q tests/unit/test_kroko_onnx_engine.py` (Windows): 29 passed,
  1 skipped, 4 subtests passed.
- `pytest -q tests/unit/test_fastapi_server_multi_user.py` (Ubuntu,
  native fs): 113 passed, 1 skipped, 10 subtests passed (this file
  alone, includes the corrected replay test plus its 20x repeat proof).
- `pytest -q tests/unit/test_release_cli.py` (Windows): 16 passed (13
  pre-existing + 3 new `ManifestBuildCommandTests`).
- `pytest -q tests/unit/test_release_adapters.py test_release_cli.py
  test_release_engine.py test_release_pipeline.py test_release_preflight.py
  test_release_rc_manifest.py test_release_redaction.py
  test_release_remote_checks.py test_release_state.py
  test_build_production.py` (Windows): 174 passed, 11 subtests passed.

## Final tally

- PASS: 28
- FAIL: 0
- BLOCKED: 0

All mandatory gates PASS -> **READY FOR ROOT REVIEW** (this correction's
own scope; see `06_FINAL_REPORT.md`).
