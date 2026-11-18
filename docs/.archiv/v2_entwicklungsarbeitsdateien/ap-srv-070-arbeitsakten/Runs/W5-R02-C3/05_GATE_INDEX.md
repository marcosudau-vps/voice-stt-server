# AP-SRV-070 / W5-R02-C3 — Gate Index

Literal gate semantics per prompt Section 4. No N/A is used on any mandatory
success-path gate.

## Identity / governance

| Gate | Status | Requirement | Evidence | Result |
|---|---|---|---|---|
| W5C4-G01 | PASS | Remote Distributed exactly `7f1ad1f02da9b1c4e3bf226f2a056066921ef77a` | `Evidence/00_Preflight/01_preflight_git.txt`, `Evidence/09_Final_Git_State/01_final_git_state.txt` | `git fetch origin` then `git rev-parse origin/feat/einheitliche-triggerarchitektur-distributed` = `7f1ad1f…`, before and after the run |
| W5C4-G02 | PASS | Start tree exactly `9c51c365701357e3b35dece563b156fc611b2c6e` | `Evidence/00_Preflight/01_preflight_git.txt` | `git rev-parse HEAD^{tree}` = `9c51c365…` |
| W5C4-G03 | PASS | New C3 worktree created clean from the binding commit | `Evidence/00_Preflight/01_preflight_git.txt` | `git worktree add -b work/ap-srv-070-w5-r02-c3 … 7f1ad1f…`; `git status --porcelain` empty at creation |
| W5C4-G04 | PASS | `02_PLAN.md` existed before the first tracked edit, no edit/revert exception | `Evidence/00_Preflight/03_plan_boundary.txt` | With `02_PLAN.md` already written (sha256 `ad5e1905…`), both `git status --porcelain` and `git diff --stat` were empty. No tracked file was edited and reverted at any point in this run |
| W5C4-G05 | PASS | VERSION remains `2.0.0` | `Evidence/05_Final_Diff/01_full_diff.txt`, `Evidence/06_Ubuntu_Stress/02_post_fix_source_identity.txt` | `VERSION` not in the diff; hash identical in worktree and Ubuntu copy |
| W5C4-G06 | PASS | No push / tag / publication | `Evidence/09_Final_Git_State/01_final_git_state.txt` | No push, tag, release, PyPI, GHCR, Docker Hub, canonical branch or main operation was performed; remote unchanged |

## Root-cause evidence

| Gate | Status | Requirement | Evidence | Result |
|---|---|---|---|---|
| W5C4-G07 | PASS | C2 hang evidence independently reviewed and accurately represented | `Evidence/01_C2_Evidence_Review/01_c2_uncommitted_diff.txt`, `03_ROOT_CAUSE_REPORT.md` §3.3 | C2's diff captured verbatim read-only; C2's 96/100 and 94/100 numbers restated without alteration; C2's *interpretation* of its faulthandler dump is corrected with evidence rather than silently reused |
| W5C4-G08 | PASS | Baseline combined-test behaviour characterised with bounded/faulthandler diagnostics | `Evidence/02_Baseline_Reproduction/01_control1_baseline_pytest.txt` | 50 fresh processes under `timeout --signal=ABRT 25` with faulthandler: 48 PASS / 2 FAIL (the ordering defect) / 0 HANG, and the masking mechanism is explained rather than treated as the hang having vanished |
| W5C4-G09 | PASS | Isolated already-degraded single-connection TestClient control executed repeatedly | `Evidence/03_Harness_Control_Matrix/01_control_matrix_results.txt` | control2 100 attempts (82 PASS / 18 HANG, precondition race), control2b 100 attempts **100/100 PASS** |
| W5C4-G10 | PASS | Sequential-socket non-degraded control executed repeatedly | same | control3, 100 attempts, **100/100 PASS**, 0 hangs |
| W5C4-G11 | PASS | Fresh-TestClient/lifecycle degraded control executed repeatedly | same | control4, 100 attempts, **100/100 PASS**, 0 hangs |
| W5C4-G12 | PASS | Real local ASGI/network degraded-connection probe executed successfully | `Evidence/04_Real_ASGI_Network_Probe/01_real_network_probe.txt` | Real Uvicorn on an ephemeral loopback port + real `websockets` client, no TestClient: **50/50 PASS**, ~10 ms each. No new dependency was added |
| W5C4-G13 | PASS | Root cause classified RC-A or RC-B with evidence, not speculation | `03_ROOT_CAUSE_REPORT.md`, `Evidence/03_Harness_Control_Matrix/01..03` | **RC-A**, sub-case A3 (test structure). Supported by: exact 100/100 correlation between hang and store state (control1c); deterministic causal isolation of the state flip (control1d); stack-level trace of both flip paths (03_state_flip_trace.txt); refutation of A1 (control5) and A2 (control3) |

## Correctness / implementation

| Gate | Status | Requirement | Evidence | Result |
|---|---|---|---|---|
| W5C4-G14 | PASS | Validated C2 committed-event-before-error semantics carried forward | `Evidence/05_Final_Diff/01_full_diff.txt`, `04_IMPLEMENTATION_REPORT.md` §3.1 | Bounded loop with strict cursor monotonicity and canonical-store identity verification, semantics identical to the archived C2 diff |
| W5C4-G15 | PASS | `outage.not_committed` can never be accepted as committed | `Evidence/05_Final_Diff/01_full_diff.txt` | `assertNotEqual(event_name, "outage.not_committed", …)` inside the loop; the recovery section's `assertNotIn` checks are unchanged |
| W5C4-G16 | PASS | Mandatory `log.error(event_store_unavailable)` preserved | same | The loop terminates only on `log.error`; `assertEqual(error["code"], "event_store_unavailable")` unchanged in the ordering test and asserted again in the new test |
| W5C4-G17 | PASS | Mandatory close 1011 preserved | same | `assertRaises(WebSocketDisconnect)` + `assertEqual(closed.exception.code, 1011)` unchanged in the ordering test and asserted again in the new test |
| W5C4-G18 | PASS | New degraded-connection contract remains explicitly covered | same | `test_new_log_stream_reports_degraded_store_and_closes` asserts `log.error`, `event_store_unavailable` and close `1011`, with its own explicitly asserted degraded precondition. Coverage moved, never removed |
| W5C4-G19 | PASS | No sleeps / blind retries / assertion weakening | `Evidence/05_Final_Diff/02_adversarial_scope_review.txt` | Each forbidden shape from prompt Section 6 checked individually against the diff text; all absent. The diff only adds assertions |
| W5C4-G20 | PASS | Production source unchanged (RC-A) | `Evidence/06_Ubuntu_Stress/02_post_fix_source_identity.txt` | `api_fastapi_server/server.py` `8c10a5dd…` and `VoiceSTT_server/event_logging.py` `3d707945…` byte-identical to the binding tree, both in the worktree and in the Ubuntu copy that executed every campaign |

## Stress / regression

| Gate | Status | Requirement | Evidence | Result |
|---|---|---|---|---|
| W5C4-G21 | PASS | Ubuntu C2 ordering scenario 100/100 PASS | `Evidence/06_Ubuntu_Stress/01_stress_campaigns.txt` | `attempts=100 pass=100 fail=0 hang=0` |
| W5C4-G22 | PASS | Ubuntu degraded-new-connection scenario 100/100 PASS | same | `attempts=100 pass=100 fail=0 hang=0` |
| W5C4-G23 | PASS | Ubuntu affected file 10/10 complete PASS | same | `attempts=10 pass=10 fail=0 hang=0`, each `55 passed, 6 subtests passed` |
| W5C4-G24 | PASS | Ubuntu full suite 2/2 PASS | `Evidence/07_Ubuntu_Full_Regression/01_full_suite_two_runs.txt` | Both runs `1709 passed, 14 skipped, 985 subtests passed`, 0 failed. `1709 = 1708 (C1 baseline) + 1` — the one added test, as predicted in `02_PLAN.md` §5 |
| W5C4-G25 | PASS | Windows targeted scenarios PASS | `Evidence/08_Windows_Regression/01_windows_regression.txt` | Ordering scenario `1 passed in 4.06s`; degraded-new-connection `1 passed in 2.27s` |
| W5C4-G26 | PASS | Windows affected file PASS | same | `55 passed, 6 subtests passed in 48.50s` |
| W5C4-G27 | PASS | `git diff --check` PASS | `Evidence/05_Final_Diff/01_full_diff.txt` | Empty output, exit 0 |
| W5C4-G28 | PASS | Exact full diff archived and adversarial scope review PASS | `Evidence/05_Final_Diff/01_full_diff.txt`, `02_adversarial_scope_review.txt` | Full verbatim diff plus a per-item review against prompt Sections 6, 17 and 19 |

## Final Git

| Gate | Status | Requirement | Evidence | Result |
|---|---|---|---|---|
| W5C4-G29 | PASS | Exactly one local final C3 commit directly on `7f1ad1f…` | `Evidence/09_Final_Git_State/01_final_git_state.txt` | One commit; `git rev-parse HEAD^` = `7f1ad1f02da9b1c4e3bf226f2a056066921ef77a`; `git rev-list --count origin/…distributed..HEAD` = 1 |
| W5C4-G30 | PASS | Final workspace genuinely clean | same | `git status --porcelain` empty (literal semantics: empty output, not "empty apart from an intended modification") |
| W5C4-G31 | PASS | Remote Distributed still exactly `7f1ad1f…`; no push | same | `git fetch origin` then `git rev-parse origin/…` = `7f1ad1f…` after the commit |
| W5C4-G32 | PASS | Final commit/tree/parent identities recorded and internally consistent | same | Commit, tree and parent SHAs recorded and cross-checked |

## Tally

- PASS: **32 of 32**
- FAIL: 0
- N/A: 0

All 32 mandatory gates PASS.
