# AP-SRV-070 / W5-R02-C3-R1 — Implementation Report (Soll/Ist)

## 1. Planned files (Soll)

`02_PLAN.md` §2, contingent on the Branch B decision taken in
`03_SEMANTIC_AUTHORITY_REVIEW.md`: `VoiceSTT_server/event_logging.py`,
`docs/structured-logging.md`, `tests/unit/test_server_operations.py`,
`tests/unit/test_fastapi_server_multi_user.py`.

## 2. Actual files (Ist)

```
VoiceSTT_server/event_logging.py             |  86 ++++++---
docs/structured-logging.md                   |  27 +++
tests/unit/test_server_operations.py         | 143 +++++++++++++++
tests/unit/test_fastapi_server_multi_user.py | 229 ++++++++++++++++++++--
4 files changed
```

Exactly the planned four. `api_fastapi_server/server.py` is byte-identical to
the binding tree (sha256 `8c10a5dd…`) — the `/ws/logs` handler is not edited,
only the state model it already consulted. `VERSION` stays `2.0.0`.

## 3. Why each file changed

### 3.1 `VoiceSTT_server/event_logging.py` — the state-model correction

Root Review's blocker was that one successful read could erase the state
produced by a persistent write failure. It could, because
`StructuredEventHub` held a single `_store_state` string that every operation
overwrote.

Replaced by two independent capability flags plus a derived state:

- `_store_write_failed` — set by a failed append, cleared **only** by an append
  that actually commits;
- `_store_read_failed` — set by a failed read, cleared by a successful read;
- `_derived_store_state()` — `disabled` without a store, `degraded` if either
  capability is failing, else `ready`.

`_set_store_state(state, *, capability, error=None)` now takes a required
`capability`, and all eight call sites are labelled: `emit`'s two outcomes are
`write`; `query`'s two outcomes and the failure paths of `latest_cursor`,
`oldest_cursor`, `retention_cursor` and `store_status` are `read`.
`store_status()` and `store_available()` report the derived state.

Deliberately preserved: the public key set of `store_status()`, the boolean
shape of `store_available()`, the `store_error` / `store_recovered` control
vocabulary including the existing "re-announce when the error type changes"
behaviour, the SQLite-first ordering inside `emit`, the single
`_store_state_lock` discipline, and every `/ws/logs` protocol behaviour. The
change makes availability strictly *stricter*: no state that was previously
`degraded` can become `ready` under the new model.

### 3.2 `docs/structured-logging.md` — required by prompt Section 17

Product semantics changed, so the current documentation now states what store
availability means, that read and write capability are tracked separately, that
a successful read clears only a read failure, that only a committing append
clears a write failure, and why live logging stays unavailable while canonical
writes are unavailable. One new subsection inside the existing "Persistent
history" section. No historical archive document is rewritten.

### 3.3 `tests/unit/test_server_operations.py` — T1–T5

`test_event_hub_successful_read_never_clears_a_pending_write_failure` covers
T1 (write fails → degraded, event non-canonical), **T2** (a successful
canonical read leaves the store degraded — the central regression), T3 (a
second write still fails and nothing is falsely canonical, and no subscriber
was ever told the store recovered) and T4 (a genuinely committing append
restores availability and announces `store_recovered`).

`test_event_hub_read_failure_is_cleared_by_a_successful_read` covers T5: a
failing read degrades the store, a successful *write* does not clear that read
failure, and a later successful read does.

Both use the file's own `hub.flush()` before any control-frame assertion, so a
negative assertion cannot pass merely because a control frame is still in
flight.

### 3.4 `tests/unit/test_fastapi_server_multi_user.py` — carry-forward and T6

**Ordering carry-forward.** The C2/C3 correction is carried forward with its
semantics intact: bounded at 50 intervening frames, strictly increasing cursor,
`outage.not_committed` rejected, unexpected frame type fails, mandatory
`log.error` with exact code `event_store_unavailable`, mandatory close `1011`.
The canonical-identity proof changed from `events.query(...)` to
`events._store.query(...)` — a direct raw-store read that performs no hub state
mutation. This is the option prompt Section 11.A.5 lists and it answers the
Section 3 objection directly: the assertion no longer records read-capability
health on the very state the test is exercising.

**Degraded new-connection coverage.** Kept as its own test,
`test_new_log_stream_reports_degraded_store_and_closes`, establishing and
asserting its own precondition. The deterministic startup barrier
(`service.ready_thread.join(timeout=30)` plus `assertFalse(is_alive())`) is
retained on **new measurement against the corrected semantics**, not inherited:
without the join 82/100 with 18 hangs, with the join 100/100. The residual race
is a startup append that resolved `_store.append` before the outage patch and
then commits — which under Branch B is genuine write evidence, so the state
model correctly reports `ready`. Joining that exact thread is a barrier, not a
sleep, a timeout or a retry.

**T6.** `test_live_log_stays_unavailable_while_only_reads_recover` is the
user-visible half of the corrected semantics: writes broken, a real
`events.query()` succeeds, availability stays `False`, `/ws/logs` answers
`log.error(event_store_unavailable)` and closes 1011, a second write is still
non-canonical, and only a committing append restores availability — after which
the recovered stream replays canonical history and never exposes either failed
event.

## 4. Coverage

Nothing removed; four tests added (1708 → 1712 in the full Ubuntu suite,
skipped and subtest counts unchanged). The pre-existing store-failure/recovery
tests — `test_event_hub_cursor_remains_unique_after_store_write_failure` and
`test_audio_transcription_continues_while_event_store_is_degraded` — pass
unchanged, which is itself evidence that the corrected model matches the
recovery semantics the suite already encoded.

## 5. No-go areas — untouched

protocol-v2, activation, trigger, wake word, model management, Kroko runtime,
packaging, release tooling, Docker, GitHub Actions workflows, dependencies and
`VERSION`. Verified by `git diff --stat` and by sha256 for
`api_fastapi_server/server.py` and `VERSION`.
