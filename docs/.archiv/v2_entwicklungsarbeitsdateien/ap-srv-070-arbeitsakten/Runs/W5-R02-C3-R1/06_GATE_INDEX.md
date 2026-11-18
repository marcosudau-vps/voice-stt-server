# AP-SRV-070 / W5-R02-C3-R1 — Gate Index

Literal gate semantics. No mandatory success-path gate is marked N/A.

## Governance

| Gate | Status | Requirement | Evidence | Result |
|---|---|---|---|---|
| W5C5-G01 | PASS | Remote Distributed start exactly `7f1ad1f02da9b1c4e3bf226f2a056066921ef77a` | `Evidence/00_Preflight/01_preflight_git.txt`, `Evidence/09_Final_Git_State/01_final_git_state.txt` | `git fetch origin` then `git rev-parse origin/feat/einheitliche-triggerarchitektur-distributed` = `7f1ad1f…`, before and after the run |
| W5C5-G02 | PASS | Start tree exactly `9c51c365701357e3b35dece563b156fc611b2c6e` | `Evidence/00_Preflight/01_preflight_git.txt` | `git rev-parse HEAD^{tree}` = `9c51c365…` |
| W5C5-G03 | PASS | New clean R1 workspace directly from the binding commit | `Evidence/00_Preflight/01_preflight_git.txt` | Worktree created from `7f1ad1f…`; empty status; `git merge-base --is-ancestor d60936c… HEAD` returns non-zero, proving the branch is **not** based on the rejected C3 commit; `git reflog` shows a single "Created from 7f1ad1f…" entry |
| W5C5-G04 | PASS | Plan exists before the first tracked edit, with literal clean proof | `Evidence/00_Preflight/02_plan_boundary.txt` | With `02_PLAN.md` and `03_SEMANTIC_AUTHORITY_REVIEW.md` already written, both `git status --porcelain` and `git diff` were empty; the branch reflog shows no earlier edit/revert cycle |
| W5C5-G05 | PASS | Rejected C3 workspace remains read-only/unmodified | `Evidence/02_C3_Reference/01_c3_reference_review.txt`, `Evidence/09_Final_Git_State/01_final_git_state.txt` | Still `d60936c…` / tree `71da4a1a…`, `git status --porcelain` empty, before and after this run |
| W5C5-G06 | PASS | VERSION remains exactly `2.0.0` | `Evidence/05_Final_Diff/01_full_diff.txt`, `Evidence/06_Ubuntu_Stress/02_post_fix_source_identity.txt` | Not in the diff; hash identical in worktree and Ubuntu copy |
| W5C5-G07 | PASS | No push/tag/release/publication | `Evidence/09_Final_Git_State/01_final_git_state.txt` | Only `git worktree add`, `git add`, `git commit` were performed as writes; `git fetch` is read-only; no tag points at HEAD; remote unchanged |

## Authority / semantics

| Gate | Status | Requirement | Evidence | Result |
|---|---|---|---|---|
| W5C5-G08 | PASS | Current structured-logging authority reviewed and quoted accurately | `03_SEMANTIC_AUTHORITY_REVIEW.md`, `Evidence/01_Authority/01_authority_search.txt` | The binding sentences of `docs/structured-logging.md` are quoted with line references; a full-text search of all current (non-archive) docs shows **no** statement that any successful store operation means the whole store recovered; archive material is labelled historical, never as current contract |
| W5C5-G09 | PASS | Existing tests for store failure/recovery semantics inventoried | `Evidence/01_Authority/01_authority_search.txt` | Complete grep inventory of `tests/` plus the decisive existing test quoted verbatim. Every existing test demonstrates write-failure recovery through a **successful write**; none asserts read-driven recovery |
| W5C5-G10 | PASS | Read capability, write capability and global availability explicitly distinguished | `03_SEMANTIC_AUTHORITY_REVIEW.md` §4 | Three-way distinction stated and used as the basis for the decision and for the implementation |
| W5C5-G11 | PASS | Mixed read-ok/write-broken state reproduced from real operations | `Evidence/03_Mixed_Capability_Reproduction/01_mixed_capability_before_fix.txt`, `04_REPRODUCTION_REPORT.md` | Reproduced at hub level, app level and over a real Uvicorn socket; `_store.append` raises for the whole window; `_store_state` never written directly |
| W5C5-G12 | PASS | First failed append proven non-canonical | same | `emit(...)` returns `None`, `latest_cursor()` unchanged, event absent from canonical history — before and after the fix |
| W5C5-G13 | PASS | Successful read-after-write-failure state transition measured | same, plus `Evidence/04_Recovery_Proof/01_mixed_capability_after_fix.txt` | Before: `degraded → ready` with a false `store_recovered` control. After: stays `degraded`, no `store_recovered` |
| W5C5-G14 | PASS | Persistent second write failure measured after the successful read | same | Second `emit(...)` returns `None` and stays non-canonical in both trees |
| W5C5-G15 | PASS | User-visible `/ws/logs` behaviour in mixed capability measured with a real network | `Evidence/03_…/01_…before_fix.txt`, `Evidence/04_Recovery_Proof/01_…after_fix.txt` | Before: silence, then `log.hello`/`log.subscribed`/`log.event`, no close, with `/health` `ok:true` and history `200`. After: `log.error(event_store_unavailable)` + close `1011`, `/health` `ok:false`, history `503` |
| W5C5-G16 | PASS | Final semantic decision supported by authority/evidence, not implementation circularity | `03_SEMANTIC_AUTHORITY_REVIEW.md` | **Branch B**, decided in the prompt's priority order; the implementation is consulted last and explicitly not treated as its own justification. The C3 conclusion is revised rather than defended |

## Implementation correctness

| Gate | Status | Requirement | Evidence | Result |
|---|---|---|---|---|
| W5C5-G17 | PASS | Valid C2/C3 ordering fix carried forward without state-mutating canonical verification | `Evidence/05_Final_Diff/01_full_diff.txt`, `05_IMPLEMENTATION_REPORT.md` §3.4 | The identity proof uses `events._store.query(...)`, a direct raw-store read that performs no `EventHub` state mutation; `events.query(...)` no longer appears in that assertion |
| W5C5-G18 | PASS | Intervening committed events retain strict cursor/identity proof | `Evidence/05_Final_Diff/01_full_diff.txt` | `assertGreater(event_cursor, replay_cursor, …)` plus a canonical row whose `cursor` and `event` must both match |
| W5C5-G19 | PASS | `outage.not_committed` cannot be accepted/delivered as canonical | same | `assertNotEqual(event_name, "outage.not_committed", …)` in the loop; the recovery-replay `assertNotIn` checks retained; T6 additionally asserts a second failed event is absent from the raw store |
| W5C5-G20 | PASS | `log.error(event_store_unavailable)` and close 1011 preserved where the store is unavailable | same, `Evidence/04_Recovery_Proof/01_mixed_capability_after_fix.txt` | Asserted in the ordering test, in the degraded-connection test, in T6, and verified 50/50 over a real network |
| W5C5-G21 | PASS | Successful read-after-write-failure behaviour has a direct regression test | `tests/unit/test_server_operations.py::test_event_hub_successful_read_never_clears_a_pending_write_failure`; `…multi_user.py::test_live_log_stays_unavailable_while_only_reads_recover` | T2 at hub level and T6 at the public-contract level |
| W5C5-G22 | PASS | Successful real write recovery has a direct regression test | same tests (T4) plus the pre-existing `test_event_hub_cursor_remains_unique_after_store_write_failure` | Only a committing append restores availability and publishes `store_recovered` |
| W5C5-G23 | PASS | Read-failure/read-recovery behaviour remains correct and directly tested | `tests/unit/test_server_operations.py::test_event_hub_read_failure_is_cleared_by_a_successful_read` | T5: a read failure degrades, a successful write does not clear it, a successful read does |
| W5C5-G24 | PASS | No arbitrary sleeps/blind retries/timeout masking | `Evidence/05_Final_Diff/02_adversarial_scope_review.txt` §4 | Each forbidden shape checked individually against the diff text; all absent. The only new numeric is `join(timeout=30)`, an upper bound whose expiry is asserted to be a failure |
| W5C5-G25 | PASS | Scope is minimal for the selected branch | `Evidence/05_Final_Diff/01_full_diff.txt`, `02_adversarial_scope_review.txt` | Exactly the four files Branch B allows; `api_fastapi_server/server.py` byte-identical to the binding tree; no dependency, workflow, packaging or VERSION change |

## Validation

| Gate | Status | Requirement | Evidence | Result |
|---|---|---|---|---|
| W5C5-G26 | PASS | Ubuntu ordering scenario 100/100 PASS | `Evidence/06_Ubuntu_Stress/01_stress_campaigns.txt` | `attempts=100 pass=100 fail=0 hang=0` |
| W5C5-G27 | PASS | Ubuntu degraded-new-connection scenario 100/100 PASS | same | `attempts=100 pass=100 fail=0 hang=0` |
| W5C5-G28 | PASS | Ubuntu mixed-capability/recovery scenario 100/100 PASS | same | `attempts=100 pass=100 fail=0 hang=0` (T6 plus the three hub-level recovery tests in one process per attempt) |
| W5C5-G29 | PASS | Ubuntu affected FastAPI file 10/10 PASS | same | `attempts=10 pass=10 fail=0 hang=0`, each `56 passed, 6 subtests passed` |
| W5C5-G30 | PASS | Ubuntu relevant EventHub/event-logging file 10/10 PASS | same | `attempts=10 pass=10 fail=0 hang=0`, each `27 passed` |
| W5C5-G31 | PASS | Ubuntu full suite 2/2 PASS | `Evidence/07_Ubuntu_Full_Regression/01_full_suite_two_runs.txt` | Both runs `1712 passed, 14 skipped, 985 subtests passed`, 0 failed. `1712 = 1708 (C1 baseline) + 4` added tests |
| W5C5-G32 | PASS | Windows targeted + affected files PASS | `Evidence/08_Windows_Regression/01_windows_regression.txt` | Ordering `1 passed`; degraded-new-connection `1 passed`; mixed-capability/recovery targeted `4 passed`; `test_fastapi_server_multi_user.py` `56 passed`; `test_server_operations.py` `27 passed`. The pre-existing, environmental pytest-basetemp permission issue is proven at the binding commit and documented in `07_DEVIATIONS.md` B3 |
| W5C5-G33 | PASS | Final real-network mixed-capability probe ≥ 50 consecutive PASS | `Evidence/04_Recovery_Proof/01_mixed_capability_after_fix.txt` | `attempts=50 pass=50 fail=0 hang=0`, each asserting state, first frame, exact code, close 1011 and `/health` |
| W5C5-G34 | PASS | `git diff --check` PASS | `Evidence/05_Final_Diff/01_full_diff.txt` | Empty output, exit 0 |
| W5C5-G35 | PASS | Exact full diff archived; adversarial scope review PASS | `Evidence/05_Final_Diff/01_full_diff.txt`, `02_adversarial_scope_review.txt` | Full verbatim diff plus a per-item review against prompt Sections 11, 12, 16 and 18 |

## Final Git

| Gate | Status | Requirement | Evidence | Result |
|---|---|---|---|---|
| W5C5-G36 | PASS | Exactly one local final commit directly on `7f1ad1f…` | `Evidence/09_Final_Git_State/01_final_git_state.txt` | One commit; `git rev-parse HEAD^` = `7f1ad1f02da9b1c4e3bf226f2a056066921ef77a`; `git rev-list --count origin/…distributed..HEAD` = 1; `d60936c…` is not an ancestor |
| W5C5-G37 | PASS | Final workspace literally clean | same | `git status --porcelain` empty |
| W5C5-G38 | PASS | Remote Distributed still exactly `7f1ad1f…`; no push | same | `git fetch origin` after the commit; `origin/…distributed` = `7f1ad1f…` |
| W5C5-G39 | PASS | Final commit/tree/parent identities recorded and consistent | same | Commit, tree and parent SHAs recorded and cross-checked |

## Tally

- PASS: **39 of 39**
- FAIL: 0
- N/A: 0
