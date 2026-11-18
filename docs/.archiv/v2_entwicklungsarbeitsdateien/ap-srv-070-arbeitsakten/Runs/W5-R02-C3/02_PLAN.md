# AP-SRV-070 / W5-R02-C3 — Plan

Written before the first tracked repository edit. At the time this file was
created, `git status --porcelain` in the C3 worktree was empty (see
`Evidence/00_Preflight/01_preflight_git.txt` and the plan-boundary evidence
`Evidence/00_Preflight/03_plan_boundary.txt`).

## 1. Objective

Two deliverables, in this order:

- **A** — determine, with evidence, whether the intermittent second-connection
  hang is a product defect (RC-B), a TestClient/AnyIO harness issue, or a
  test-structure defect (RC-A), or something else.
- **B** — one narrow local commit carrying forward the validated C2 ordering
  correction plus the minimal correction that removes the hang while preserving
  the production contract.

No conclusion is pre-assumed. In particular this plan does **not** assume the
C2 working hypothesis (TestClient/AnyIO glue). The control matrix decides.

## 2. Working hypotheses to be discriminated

Source reading of the binding tree produced one concrete, falsifiable
alternative to the harness hypothesis, which the controls must test explicitly:

- `VoiceSTT_server/event_logging.py::EventHub.query()` calls
  `_set_store_state("ready")` on every successful query.
- The test simulates the outage by patching **only** `EventHub._store.append`
  to raise; `EventHub._store.query` keeps working.
- The still-open first `/ws/logs` connection runs a live loop
  (`api_fastapi_server/server.py`, the `while True` block after
  `log.replay_completed`) that calls `service.events.query(...)` whenever it has
  ground to cover between `scan_cursor` and `latest_cursor()`.
- Therefore a successful live-loop `query()` occurring after the deliberate
  `append` failure can legitimately flip the store state back from `degraded`
  to `ready`.
- The first connection still closes with 1011 because it acts on the queued
  `store_error` control, not on the current state — so the first half of the
  test still passes.
- The second connection then evaluates `service.events.store_available()`,
  finds `True`, skips the degraded fast path, and blocks in
  `await websocket.receive_text()` waiting for a `subscribe` message the test
  never sends. The test blocks in `receive_json()` indefinitely.

This predicts exactly the C2 faulthandler signature: main thread parked in
`WebSocketTestSession.receive` then portal then `Future.result`, the ASGI loop
thread idle in `select()` (the handler coroutine is *suspended*, so it
contributes no visible frame), and worker threads idle.

**Decisive, directly measurable prediction (P1):** in a hung run,
`events.store_available()` immediately before the second connect is `True`,
not `False`. If P1 holds, the harness hypothesis is refuted as the cause.

## 3. Control matrix to execute (prompt Section 13)

All diagnostics are untracked scripts stored under
`.../Runs/W5-R02-C3/Evidence/` and executed from `/home/marco/c3-diag/`
against the native Ubuntu copy. None of them is a repository change.

- **Control 1 — baseline combined test.** 50 fresh-process runs of the
  unmodified binding target test with `timeout` and `faulthandler`. Confirm the
  known intermittent hang and capture at least one stack.
- **Control 1b — instrumented baseline (decisive).** Same scenario, driven
  directly (no pytest), recording `events.store_status()` immediately before the
  second connect, with a hard watchdog. Correlate hang vs. store state. Tests P1.
- **Control 2 — isolated already-degraded single connection.** Real app, real
  TestClient, degrade via the same real mechanism, verify `store_available()` is
  `False`, then open exactly one `/ws/logs`. Expect `log.error` /
  `event_store_unavailable` / close 1011. Target 100/100.
- **Control 3 — sequential websockets, no outage.** Two complete sequential
  `/ws/logs` lifecycles on one TestClient, store healthy. Target 100/100. Tests
  the pure back-to-back TestClient websocket hypothesis in isolation.
- **Control 4 — fresh TestClient/lifecycle boundary for the degraded case.**
  Degraded connection exercised across a clean app/TestClient boundary.
  Target 100/100.
- **Control 5 — real ASGI network probe.** Real Uvicorn server on an ephemeral
  loopback port, real `websockets` client (already an existing dependency; no
  new dependency is added), same app instance degraded through the same real
  mechanism. Expect connect, then `log.error(event_store_unavailable)`, then
  close 1011. Target at least 30 consecutive PASS, 50 if inexpensive.

`03_ROOT_CAUSE_REPORT.md` is written from these results, with the required
table and an explicit RC-A / RC-B / RC-C classification, before implementation
is finalised.

## 4. Planned implementation (contingent on RC classification)

If **RC-A** (harness/test-structure) is proven, the planned scope is exactly:

- `tests/unit/test_fastapi_server_multi_user.py` — no production file.

Planned shape, following prompt Section 16:

- **Test A** = existing
  `test_store_outage_closes_live_stream_and_recovery_allows_new_stream`,
  carrying forward the validated C2 ordering correction verbatim in semantics
  (bounded loop, strict cursor monotonicity, canonical-store identity check,
  `outage.not_committed` forbidden, unexpected frame fails, mandatory
  `log.error` plus close 1011 preserved), and no longer performing the
  already-degraded *new-connection* check inside the same live/outage sequence.
- **Test B** = a new focused test with its own clean app/TestClient lifecycle
  that establishes the degraded state through the same real failure mechanism,
  asserts the precondition explicitly (`store_available()` is `False`), opens
  exactly one `/ws/logs`, and asserts `log.error` /
  `event_store_unavailable` / close 1011.

Coverage is preserved, not removed: the degraded-new-connection product
contract keeps a dedicated, deterministic test. No sleeps, no timeout increases,
no blind retries, no swallowed timeouts, no weakened assertions, no changed
WebSocket close/error semantics.

If **RC-B** (product defect) is proven, no production edit is made before
`03_ROOT_CAUSE_REPORT.md` documents the exact reproducible product failure, the
violated contract and the minimal intended fix; the fix must stay localized to
the event-store/WebSocket fast path. Broader redesign means STOP.

If **RC-C** (inconclusive), STOP with `NOT READY FOR ROOT REVIEW`, no
success-path commit.

## 5. Planned validation (prompt Section 18)

- Ubuntu, Test A: 100 consecutive runs, hard timeout, 0 hangs, 0 failures.
- Ubuntu, Test B: 100 consecutive runs, hard timeout, 0 hangs, 0 failures.
- Ubuntu, `tests/unit/test_fastapi_server_multi_user.py`: 10 consecutive full
  executions, all PASS.
- Ubuntu, `python -m pytest -q tests/unit`: 2 consecutive full executions, both
  PASS. Expected count change vs. the C1 baseline of `1708 passed, 14 skipped,
  985 subtests`: exactly `+1 passed` if one test is added, to be stated
  explicitly.
- Windows: Test A once, Test B once, whole affected file once — all PASS.
- `git diff --check` PASS; exact full diff archived; adversarial scope review.

## 6. Protected / no-go areas

Untouched unless independently proven defective: `VoiceSTT_server/event_logging.py`,
the `/ws/logs` production handler, the event-store state machine, protocol-v2,
scheduler, model management, Kroko, release tooling, packaging, Docker, CI
workflow, dependency versions. `VERSION` stays `2.0.0`.

## 7. Git end state

Exactly one local commit whose direct parent is
`7f1ad1f02da9b1c4e3bf226f2a056066921ef77a`, clean worktree, remote unchanged,
no push, no tag, no amend after evidence binding, no rebase/merge/force-push,
no publication of any kind.
