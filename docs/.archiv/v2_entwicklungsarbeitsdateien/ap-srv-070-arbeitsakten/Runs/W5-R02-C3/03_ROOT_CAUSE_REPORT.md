# AP-SRV-070 / W5-R02-C3 — Root Cause Report

Written before the implementation was finalised. Every statement below is
labelled as **observed fact**, **evidence-supported inference**, or **proven
conclusion**. Nothing here is called conclusive unless a control establishes it
directly.

---

## 1. The question

W5-R02-C2 found an intermittent hang at the third section of
`test_store_outage_closes_live_stream_and_recovery_allows_new_stream` — the
"new `/ws/logs` connection while the canonical store is already degraded"
check — and measured it at 4/100 on the C2 tree and 6/100 on the unmodified
binding commit `7f1ad1f...`. C2 inferred a `starlette.testclient` / `anyio`
blocking-portal lost wakeup but explicitly did not prove it.

C3 had to decide between:

- **A1** production defect in the `/ws/logs` degraded fast path,
- **A2** TestClient / AnyIO / in-process harness lifecycle issue,
- **A3** test-structure defect,
- **A4** something else.

---

## 2. Control matrix

All controls ran on WSL2 Ubuntu 24.04.4 LTS, Python 3.12.3, against a native
ext4 copy of the **unmodified binding tree** (`7f1ad1f...`, tree
`9c51c365...`). Packages: fastapi 0.141.1, starlette 1.6.0, anyio 4.15.1,
httpx 0.28.1, httpcore 1.0.9, h11 0.16.0, uvicorn 0.52.4, websockets 16.0,
pytest 9.1.1. No dependency version was changed at any point.

| Control | Same TestClient? | Sequential sockets? | Store degraded? | Real network? | Attempts | Hangs | Result |
|---|---:|---:|---:|---:|---:|---:|---|
| **1** baseline combined test (pytest, unmodified) | yes | yes | yes (assumed) | no | 50 | 0 | 48 PASS / 2 FAIL — both the *ordering* defect (`'log.event' != 'log.error'`), which masks the hang |
| **1b** instrumented replica of the same sequence | yes | yes | yes (measured `false` every time) | no | 100 | 0 | 100 PASS |
| **1c** same replica, commit-control race amplified | yes | yes | **measured, mixed** | no | 100 | **86** | 14 PASS / 86 HANG — see §3 |
| **1d** causal isolation of the state flip | yes | no | flipped on purpose | no | 100 | 0 | 71 PASS / 29 FAIL (all failures are precondition races, never a contradiction) |
| **2** isolated already-degraded single connection | yes | no | asserted `false` before connect | no | 100 | **18** | 82 PASS / 18 HANG |
| **2b** control 2 plus a deterministic startup barrier | yes | no | asserted `false` before connect | no | 100 | 0 | **100 PASS** |
| **3** two sequential `/ws/logs` lifecycles, healthy store | yes | **yes** | no | no | 100 | 0 | **100 PASS** |
| **4** degraded connection across a fresh TestClient lifecycle | no (two clients) | yes | asserted `false` before connect | no | 100 | 0 | **100 PASS** |
| **5** real Uvicorn server + real WebSocket client | **no TestClient at all** | no | asserted `false` before connect | **yes** | 50 | 0 | **50 PASS**, ~10 ms per probe |

Raw evidence: `Evidence/02_Baseline_Reproduction/01_control1_baseline_pytest.txt`,
`Evidence/03_Harness_Control_Matrix/01_control_matrix_results.txt`,
`Evidence/03_Harness_Control_Matrix/02_control1c_hang_faulthandler_stack.txt`,
`Evidence/03_Harness_Control_Matrix/03_state_flip_trace.txt`,
`Evidence/04_Real_ASGI_Network_Probe/01_real_network_probe.txt`.

A methodological correction is recorded with the evidence: on this CPython
build `faulthandler.dump_traceback_later(exit=True)` terminates with status
**0**, so exit codes alone would have reported hangs as passes. The driver
counts PASS only on an explicit final `"result": "PASS"` record with no
faulthandler timeout banner and exit 0. Control 1b's first campaign was re-run
under the corrected classifier and independently re-verified.

---

## 3. What the controls establish

### 3.1 Observed fact — the hang is perfectly correlated with the store state

Control 1c records `events.store_status()` immediately before the second
`/ws/logs` connect. Across all 100 attempts:

```
HANG & store_before_second_connect = ready       86
PASS & store_before_second_connect = degraded    14
```

There is no exception in either direction. Every hang occurred with the
canonical store reporting **ready**; every pass occurred with it reporting
**degraded**.

### 3.2 Observed fact — two legitimate paths re-mark a degraded store as ready

`Evidence/03_Harness_Control_Matrix/03_state_flip_trace.txt` instruments
`EventHub._set_store_state` on the live instance and records every transition
with its stack. Two paths appear, both ordinary product behaviour:

1. **`EventHub.query()` success.** `VoiceSTT_server/event_logging.py` line 1189
   calls `_set_store_state("ready")` after every successful canonical query.
   The still-open first `/ws/logs` connection runs a live loop that calls
   `service.events.query(...)` on every wake-up
   (`api_fastapi_server/server.py` line 8838), including the wake-up caused by
   a `commit` control that was already in flight when the outage began.
2. **An in-flight startup `emit`.** `VoiceSTTService._ready_worker`
   (`api_fastapi_server/server.py` line 7621, thread `VoiceSTTServerReady`)
   emits `server.ready` and the `models.loaded` performance event.
   `EventHub.emit` resolves `self._store.append` and only then calls it, so an
   emit that resolved the *real* method microseconds before the test replaced
   the attribute still succeeds afterwards and reaches
   `_set_store_state("ready")` at `event_logging.py` line 978.

The common cause is that the test simulates the outage by breaking **only**
`_store.append`. Every read path keeps working, and the product's documented
behaviour is to mark the store ready again whenever a canonical operation
succeeds.

### 3.3 Proven conclusion — the state flip, not the harness, produces the hang

Control 1d isolates the causal step deterministically and without any hang:
degrade the store, call `events.query(limit=1)` — the exact call the live loop
makes — and observe

```
store_available_after_successful_query: true      (71 of 71 runs that reached this step; 0 counter-examples)
first_frame_of_new_connection:          "log.hello"
```

That is, once the store reports ready, a new `/ws/logs` connection takes the
**normal subscribe path**, not the degraded fast path. A client that waits for
`log.error` without ever sending a `subscribe` frame — exactly what the binding
test does — therefore blocks forever. The 29 non-passing control 1d attempts
are all precondition races in the same direction (the store had already
flipped, or flipped back); none contradicts the flip.

This also explains the faulthandler signature C2 captured and C3 reproduced
byte-for-byte: the `/ws/logs` handler is **suspended** in
`await websocket.receive_text()`, and a suspended coroutine contributes no
frame to a thread dump. C2 read that absence as "no application code is
running, therefore the harness lost a wakeup". The absence is equally
consistent with — and is in fact produced by — an application coroutine
correctly awaiting a client frame that never arrives.

### 3.4 Proven conclusion — A1 (production defect) is refuted

Control 5 runs the real app under a real Uvicorn server on a real loopback
socket with a real WebSocket client and **no TestClient anywhere**. With the
degraded precondition actually established and asserted, the contract holds
**50/50**, in about 10 ms each:

```
connect -> log.error(event_store_unavailable) -> close 1011
```

Control 2b confirms the same contract 100/100 inside TestClient once the
precondition is established deterministically, and control 4 confirms it
100/100 across a fresh TestClient lifecycle boundary.

### 3.5 Proven conclusion — A2 (TestClient / AnyIO harness) is refuted

Control 3 exercises two complete sequential `/ws/logs` lifecycles on one
TestClient with a healthy store: **100/100 PASS, zero hangs**. Back-to-back
TestClient WebSocket sessions are therefore not, by themselves, unstable. The
hang never appears without the store-state flip, and always appears with it
(§3.1).

### 3.6 Evidence-supported inference — why the binding test masked the hang

On the unmodified binding test an intervening committed `log.event` aborts the
test with a fast assertion failure (`'log.event' != 'log.error'`) *before* it
can reach the second connection. Control 1 reproduces exactly that: 2 of 50
attempts fail that way, 0 hang. Once the (correct) C2 ordering fix consumes
those frames, the same runs proceed to the second connection and hang instead —
which is precisely the 96/100-to-4-hangs shift C2 measured. C2's own numbers and
C3's are consistent with one another under this reading.

---

## 4. Classification

### **RC-A — harness / test-structure confirmed**

The three conditions the prompt requires for RC-A are met:

- the isolated real degraded fast path is stable — control 2b 100/100,
  control 4 100/100;
- the real-network probe is stable — control 5 50/50;
- the intermittent hang is tied to the combined/sequential in-process
  TestClient lifecycle — specifically, to the combined test assuming that a
  degraded store state established in its *first* scenario is still in force in
  its *third* scenario, when the product legitimately clears that state.

More precisely, the defect is **A3, test-structure**. The test bundles two
independent product contracts into one sequence and lets the second one inherit
its precondition from the first. That precondition does not survive, because
the first scenario's own live `/ws/logs` loop performs successful canonical
reads, and because the simulated outage breaks only `append`.

**No production defect was found.** The `/ws/logs` degraded fast path, the
event-store state machine and `VoiceSTT_server/event_logging.py` behave
correctly under every control. No production file is edited by this correction.

---

## 5. What the correction must therefore do

1. Carry forward the validated W5-R02-C2 ordering correction (mandatory
   `log.error(event_store_unavailable)` after zero or more genuinely committed
   `log.event` frames, strict cursor monotonicity, canonical-store identity
   verification, `outage.not_committed` forbidden, unexpected frame fails,
   bounded receive count).
2. Give the "new connection while the store is already degraded" contract its
   own test with its own clean app/TestClient lifecycle, which establishes the
   degraded precondition itself and asserts it.
3. Make that precondition deterministic by joining the service's own startup
   worker (`VoiceSTTService.ready_thread`) before simulating the outage. This
   is not a sleep, not a timeout increase and not a retry: it is a join on the
   exact background thread whose in-flight emit is shown in §3.2 to race with
   the outage patch. The measured effect is control 2 (no barrier)
   82/100 with 18 hangs versus control 2b (barrier) **100/100**.

Coverage is preserved: the degraded-new-connection contract keeps a dedicated
test, and the live-outage/ordering/recovery contract keeps its own.
