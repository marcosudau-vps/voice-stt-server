# AP-SRV-070 / W5-R02-C3-R1 — Mixed-Capability Reproduction Report

Prompt Section 10. The condition `READ: works / WRITE: persistently fails` was
established through real operations on the real `StructuredEventHub` and the
real SQLite store. `_store.append` raises for the entire observation window and
is never lifted mid-probe; `_store_state` is never written directly.

Raw evidence:
`Evidence/03_Mixed_Capability_Reproduction/01_mixed_capability_before_fix.txt`
(binding tree) and `Evidence/04_Recovery_Proof/01_mixed_capability_after_fix.txt`
(with the correction).

## Required observations 1–9

| # | Observation | Binding tree `7f1ad1f…` | With the R1 correction |
|---|---|---|---|
| 1 | a generated event cannot be committed | `emit(...)` returns `None` | unchanged: `None` |
| 2 | the attempted event gets no cursor / is absent from canonical history | cursor unchanged; event absent | unchanged: cursor unchanged; event absent |
| 3 | `store_available()` immediately after the write failure | `degraded` / `False` | `degraded` / `False` |
| 4 | a canonical `query()` succeeds | yes | yes |
| 5 | `store_available()` immediately after that successful query | **`ready` / `True`** | **`degraded` / `False`** |
| 6 | a second generated event still cannot be committed | `None`, absent from history | `None`, absent from history |
| 7 | state after that second write failure | `degraded` | `degraded` |
| 8 | `/ws/logs` behaviour in the mixed window | TestClient: `log.hello`, `log.subscribed`, `log.event`. Real network: silence, then `log.hello`, `log.subscribed`, `log.event`, **no close** | `log.error(event_store_unavailable)` then **close 1011**, both in-process and over a real socket |
| 9 | other surfaces exposing the same state | in-process `/health` `ok:false`, `logAccess.available:false`, history `503`; real network in the same window `/health` `ok:true`, history `200` | `/health` `ok:false`, `logAccess.available:false`, history `503` — consistently, in both |

## What the reproduction establishes

**Observed fact.** The persistence guarantee itself was never broken. At the
binding commit, every failed append correctly returns `None`, assigns no
cursor, and leaves the attempted event out of canonical history.

**Observed fact.** The availability signal is a single last-operation-wins bit.
The same instant reports `ready` or `degraded` depending only on whether a read
or a write touched the store most recently, which is why the real-network run
and the in-process run of the identical scenario disagreed about `/health` and
about `/api/logs/events`.

**Observed fact.** Subscribers were told the store had recovered when it had
not. The hub-level control sequence in the mixed window was
`commit, store_error, store_recovered, store_error`, and no write ever
succeeded between the two `store_error` frames.

**Evidence-supported inference.** In that state a live `/ws/logs` client
receives a normal, healthy-looking stream while every newly generated event is
dropped, with no `log.error`, no close and no `log.gap`. Since
`docs/structured-logging.md` states that a generated event's SQLite
persistence, replay and live delivery cannot be suppressed, and that only a
retention gap represents data no longer present in SQLite, the current rule
produces loss the documented model has no way to express.

**Proven conclusion.** With the corrected model the same probe, run 50
consecutive times over a real Uvicorn socket with the contract asserted, is
50/50 PASS: state stays `degraded` across the successful read, the false
`store_recovered` is gone, `/ws/logs` answers
`log.error(event_store_unavailable)` and closes `1011`, and `/health`,
`logAccess` and `/api/logs/*` all agree with it.

## Does a read failure still recover?

Yes, and it is directly tested
(`test_event_hub_read_failure_is_cleared_by_a_successful_read`): a failing
`_store.query` degrades the store, a successful write does **not** clear that
read failure, and a later successful read does clear it. The model is
symmetric — each capability is cleared only by evidence about that capability.
