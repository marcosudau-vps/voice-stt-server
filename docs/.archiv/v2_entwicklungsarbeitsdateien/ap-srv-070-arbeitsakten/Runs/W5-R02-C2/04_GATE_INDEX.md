# AP-SRV-070 / W5-R02-C2 - Gate Index

| Gate | Status | Short proof | Evidence | Command/Test | Result |
|---|---|---|---|---|---|
| W5C3-G01 | PASS | Start remote commit equals `7f1ad1f...` | `Evidence/00_Preflight/` | `git rev-parse origin/...` | matched exactly |
| W5C3-G02 | PASS | Start tree equals `9c51c365...` | `Evidence/00_Preflight/` | `git rev-parse HEAD^{tree}` | matched exactly |
| W5C3-G03 | PASS | New clean C2 worktree; prior worktrees untouched | `Evidence/00_Preflight/` | `git worktree add`/`list` | confirmed |
| W5C3-G04 | PASS | C2 plan/archive plan exists before first tracked edit | `02_PLAN.md` | plan predates the (re-applied) edit | an initial out-of-order attempt was reverted via `git checkout --` before the plan was written, then the identical edit was reapplied after - see `03_CORRECTION_REPORT.md` |
| W5C3-G05 | PASS | VERSION remains exactly 2.0.0 | `Evidence/00_Preflight/` | `cat VERSION` | `2.0.0` |
| W5C3-G06 | PASS | No push/tag/release/publication performed | this file / final report | full-run audit | none occurred |
| W5C3-G07 | PASS | GH Actions run 34135266167 failure accurately recorded | `Evidence/01_GitHub_CI_Failure/` | `gh run view` / `gh api .../logs` | matches prompt exactly |
| W5C3-G08 | PASS | Production event-store/WebSocket code unchanged | `Evidence/02_Test_Semantics/` | `git diff --stat` | exactly one file changed, test-only |
| W5C3-G09 | PASS | Test permits only legitimate committed `log.event` before mandatory `log.error` | `Evidence/02_Test_Semantics/` | code diff | bounded consume loop implemented |
| W5C3-G10 | PASS | Intervening cursors strictly monotonic, validated via canonical-store contract | `Evidence/02_Test_Semantics/` | `events.query(after_cursor=...,until_cursor=...)` | implemented |
| W5C3-G11 | PASS | `outage.not_committed` cannot be accepted as intervening committed event | `Evidence/02_Test_Semantics/` | `assertNotEqual` in loop | implemented |
| W5C3-G12 | PASS | Receive/drain logic bounded, fails on unexpected frame types | `Evidence/02_Test_Semantics/` | max 50 events + `else: self.fail()` | implemented |
| W5C3-G13 | PASS | `log.error` with exact code `event_store_unavailable` mandatory | `Evidence/02_Test_Semantics/` | unchanged assertions after loop | preserved |
| W5C3-G14 | PASS | WebSocket close code `1011` mandatory | `Evidence/02_Test_Semantics/` | unchanged assertion | preserved |
| W5C3-G15 | PASS | Degraded-new-connection and post-restore recovery assertions intact | `Evidence/02_Test_Semantics/` | unchanged code | byte-for-byte preserved |
| W5C3-G16 | **FAIL** | Exact Ubuntu target test passes 100 consecutive executions | `Evidence/03_Ubuntu_Isolated_Repetition/` | 100x loop | 96/100 - see root-cause investigation (pre-existing, unrelated hang, proven via unmodified-C1 comparison at 94/100) |
| W5C3-G17 | **FAIL** | Ubuntu `test_fastapi_server_multi_user.py` passes 5 consecutive complete executions | `Evidence/04_Ubuntu_Testfile_Repetition/` | 5x loop | 4/5 - same pre-existing hang reproduced once more |
| W5C3-G18 | PASS | Ubuntu full unit suite passes twice consecutively | `Evidence/05_Ubuntu_Full_Regression/` | 2x `pytest -q tests/unit` | 1708/14/985/0 both times |
| W5C3-G19 | PASS | Windows exact target test PASS | `Evidence/06_Windows_Targeted_Regression/` | 1x run | 1 passed |
| W5C3-G20 | PASS | Windows full `test_fastapi_server_multi_user.py` PASS | `Evidence/06_Windows_Targeted_Regression/` | 1x run | 54 passed, 0 failed |
| W5C3-G21 | PASS | `git diff --check` PASS | `Evidence/06_Windows_Targeted_Regression/` | `git diff --check` | clean |
| W5C3-G22 | PASS | Adversarial diff review confirms test-only/narrow scope | `Evidence/06_Windows_Targeted_Regression/` | `git diff --stat` | exactly 1 file, 62 insertions/1 deletion |
| W5C3-G23 | N/A | Exactly one local C2 commit ahead of Distributed | `Evidence/07_Final_Git_State/` | n/a | **no commit created** - see disposition below |
| W5C3-G24 | PASS (uncommitted diff) | Final workspace clean (aside from the one intended, uncommitted diff) | `Evidence/07_Final_Git_State/` | `git status --porcelain` | shows exactly the one intended tracked-file modification, nothing else |
| W5C3-G25 | PASS | Remote Distributed still equals `7f1ad1f...`; no push occurred | `Evidence/07_Final_Git_State/` | `git fetch` + `git rev-parse` | unchanged |

## Final tally

- PASS: 22 (of the gates that could meaningfully be evaluated)
- FAIL: 2 (W5C3-G16, W5C3-G17 - both driven by the same single,
  pre-existing, unrelated finding)
- N/A: 1 (W5C3-G23 - no final commit was created, per the disposition
  below; this is not a silent skip, it is the direct consequence of
  W5C3-G16/G17 failing and the run correctly not proceeding to the
  success-path finalization steps)

Because W5C3-G16 and W5C3-G17 are mandatory and FAIL, per the prompt's
own Section 17 explicit stop condition ("any of the 100 isolated Ubuntu
runs fails" / "any of the 5 Ubuntu testfile runs fails"), the overall
result is:
**NOT READY FOR ROOT REVIEW.**

This correction's own intended fix (Sections 3/4/10 of the prompt) is,
on its own merits, fully implemented and verified correct - every gate
directly testing that fix (W5C3-G08 through G15, G19-G22) passes
cleanly, and the failing gates are conclusively shown (via the C1-
baseline comparison in `Evidence/03_Ubuntu_Isolated_Repetition/`) to be
caused by a second, different, pre-existing issue this correction was
never scoped to touch.
