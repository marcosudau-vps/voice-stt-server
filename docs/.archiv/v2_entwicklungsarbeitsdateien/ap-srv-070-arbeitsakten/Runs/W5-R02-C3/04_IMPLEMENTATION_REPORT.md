# AP-SRV-070 / W5-R02-C3 — Implementation Report (Soll/Ist)

## 1. Planned files (Soll)

`02_PLAN.md` Section 4 committed to this scope, contingent on the root-cause
classification:

- **RC-A path:** `tests/unit/test_fastapi_server_multi_user.py` only. No
  production file.
- **RC-B path:** a narrow production edit, only after a documented, reproducible
  product failure.

## 2. Actual files (Ist)

```
tests/unit/test_fastapi_server_multi_user.py | 149 +++++++++++++++++++++++++--
1 file changed, 140 insertions(+), 9 deletions(-)
```

Exactly one file. No production file, no workflow file, no packaging, Docker,
dependency or version change. `VERSION` remains `2.0.0`.

Verified by hash, not only by `git diff`: `api_fastapi_server/server.py`
(`8c10a5dd…`) and `VoiceSTT_server/event_logging.py` (`3d707945…`) are
byte-identical to the binding tree both in the worktree and in the Ubuntu copy
that actually executed every stress campaign — see
`Evidence/06_Ubuntu_Stress/02_post_fix_source_identity.txt`.

`03_ROOT_CAUSE_REPORT.md` classified the finding **RC-A**, so the RC-B path was
never entered and no production edit was made.

## 3. Why each change was made

### 3.1 Carry-forward of the validated W5-R02-C2 ordering correction

Inside
`test_store_outage_closes_live_stream_and_recovery_allows_new_stream`, the
single blind `error = logs.receive_json()` after the deliberate store failure is
replaced by the bounded, proving receive loop C2 developed. Semantics carried
forward unchanged:

- zero or more already-committed `log.event` frames are accepted **before** the
  mandatory `log.error`;
- each intervening cursor must strictly advance past the previously consumed
  cursor (continuing the same `replay_cursor` variable W5-R02-C1 introduced);
- each intervening event is verified against the canonical store via
  `events.query(after_cursor=cursor-1, until_cursor=cursor, limit=1)`, and both
  its cursor and its event name must match — a live in-memory echo is not
  accepted as proof of commit;
- `outage.not_committed` is explicitly rejected, so the deliberately failed
  event can never be accepted as committed;
- the loop is bounded at 50 intervening frames and calls `self.fail(...)` when
  exceeded, so a genuine regression fails fast instead of hanging;
- any unexpected frame type calls `self.fail(...)`;
- the mandatory `log.error` cannot be skipped: the loop only terminates on
  `log.error`, and the subsequent
  `assertEqual(error["code"], "event_store_unavailable")` and
  `assertEqual(closed.exception.code, 1011)` assertions are unchanged.

The C2 text was inspected before reuse rather than copied blindly; no
correctness problem was found, so it is carried forward as-is. The exact C2
source diff is archived verbatim at
`Evidence/01_C2_Evidence_Review/01_c2_uncommitted_diff.txt`.

C3 independently reproduced the defect this fix addresses: 2 of 50 baseline runs
failed with `AssertionError: 'log.event' != 'log.error'`, the same failure real
GitHub Actions run `34135266167` produced
(`Evidence/02_Baseline_Reproduction/01_control1_baseline_pytest.txt`).

### 3.2 The hang fix — separating two independent contracts

The `with client.websocket_connect("/ws/logs") as unavailable:` block is removed
from that test and re-established as its own test,
`test_new_log_stream_reports_degraded_store_and_closes`, with its own
`tempfile.TemporaryDirectory`, its own `create_app`, and its own `TestClient`
lifecycle.

Reason, per `03_ROOT_CAUSE_REPORT.md`: inside the combined test that block
inherited its precondition from the outage staged earlier in the same sequence,
and the product legitimately clears that precondition. `EventHub.query()` marks
the canonical store `ready` on every successful read
(`VoiceSTT_server/event_logging.py` line 1189), and the test's own still-open
live `/ws/logs` loop performs exactly such a read whenever it drains a commit
control (`api_fastapi_server/server.py` line 8838). With the store reporting
ready again, a new connection correctly takes the normal subscribe path, and a
client waiting for `log.error` without subscribing waits forever. Control 1c
showed this correlation in 100 of 100 attempts with no exception in either
direction.

The new test establishes the degraded state itself, through the same real
failure mechanism (`_store.append` raises `OSError`), and **asserts** the
precondition with `assertFalse(events.store_available(), ...)` before opening
the connection. It then asserts the full product contract, unchanged and
unweakened: `log.error`, `code == "event_store_unavailable"`,
`WebSocketDisconnect` with code `1011`. `_store.append` is restored in a
`finally` block so the client shutdown path is not left in a broken state.

### 3.3 The deterministic startup barrier

`service.ready_thread.join(timeout=30)` plus
`assertFalse(service.ready_thread.is_alive(), ...)` runs before the outage is
simulated.

Reason: `VoiceSTTService._ready_worker` (`api_fastapi_server/server.py`
line 7621, thread `VoiceSTTServerReady`) emits `server.ready` and the
`models.loaded` performance event on its own thread. `EventHub.emit` resolves
`self._store.append` and only then calls it, so an emit that resolved the real
method microseconds before the test replaces the attribute still succeeds and
re-marks the store `ready` (`event_logging.py` line 978). This second flip path
was traced with stacks in
`Evidence/03_Harness_Control_Matrix/03_state_flip_trace.txt`.

Joining that exact thread is a deterministic barrier on the product's own
startup worker. It is **not** a sleep, **not** an increased timeout and **not** a
retry: nothing is polled, nothing is re-attempted, and no assertion is relaxed.
The measured effect is control 2 (no barrier) 82/100 with 18 hangs versus
control 2b (barrier) 100/100.

## 4. Coverage

No coverage is removed. Both contracts remain asserted, now independently:

| Contract | Before C3 | After C3 |
|---|---|---|
| live stream outage → committed-event drain → mandatory `log.error` → close 1011 → recovery/replay | inside the combined test | unchanged, still in `test_store_outage_closes_live_stream_and_recovery_allows_new_stream`, now with the C2 ordering proof |
| new connection while the store is already degraded → `log.error(event_store_unavailable)` → close 1011 | inside the same combined test, inheriting its precondition | own test `test_new_log_stream_reports_degraded_store_and_closes`, establishing and asserting its own precondition |

The affected file goes from 54 to 55 tests — exactly the one test added.

## 5. No-go areas — untouched

Confirmed untouched by `git diff --stat` and by hash comparison against the
binding tree: `VoiceSTT_server/event_logging.py`, the `/ws/logs` production
handler in `api_fastapi_server/server.py`, the event-store state machine,
protocol-v2 behaviour, scheduler, model management, Kroko, release tooling,
packaging, Docker, the CI workflow, and every dependency version. `VERSION`
remains `2.0.0`.

None of the forbidden shapes from prompt Section 6 is used: no `sleep()`, no
increased timeout, no blind `receive_json()` retry, no swallowed timeout marked
PASS, no changed WebSocket close/error semantics, no weakened assertion, no
global serialization of event delivery, no dependency change, no concurrency
refactor.
