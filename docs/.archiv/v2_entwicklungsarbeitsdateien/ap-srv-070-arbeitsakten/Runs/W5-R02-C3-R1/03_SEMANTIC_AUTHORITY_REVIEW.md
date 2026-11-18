# AP-SRV-070 / W5-R02-C3-R1 — Semantic Authority Review

Written before any tracked edit. Nothing here is called "documented" unless a
**current** authority actually states it. Archive material is labelled as
historical design intent, not as current contract.

---

## 1. The question

> If `_store.append` is persistently failing but `_store.query` still succeeds,
> should `EventHub.store_available()` / canonical live-log availability be
> `ready` or `degraded`?

## 2. Authorities consulted

| Priority | Source | Status |
|---|---|---|
| 1 | `docs/structured-logging.md` | **Current authority** |
| 1 | `docs/client-development/02-websocket-protokoll.md`, `docs/fastapi-server.md` | Current authority; contain no store-recovery rule (checked) |
| 1 | `AGENTS.md`, `docs/.archiv/README.md` | Process authority only; no store semantics |
| 2 | `tests/unit/test_server_operations.py::test_event_hub_cursor_remains_unique_after_store_write_failure` | Current test encoding intended recovery |
| 2 | `tests/unit/test_fastapi_server_multi_user.py::test_audio_transcription_continues_while_event_store_is_degraded` | Current test encoding degraded-window behaviour |
| 2 | `tests/unit/test_fastapi_server_multi_user.py::test_store_outage_closes_live_stream_and_recovery_allows_new_stream` | Current test encoding the `/ws/logs` outage contract |
| 3 | `docs/.archiv/sqlite_first_admin_eventstream/2026-08-02_..._PLAN.md` | **Historical** design intent, not current contract |
| 4 | Reproduced end-to-end behaviour, `Evidence/03_Mixed_Capability_Reproduction/01_mixed_capability_before_fix.txt` | Observed fact |
| 5 | `VoiceSTT_server/event_logging.py`, `api_fastapi_server/server.py` | Implementation, consulted last |

## 3. Required table

| Question | Authority/evidence | Conclusion |
|---|---|---|
| What makes an event canonical? | `docs/structured-logging.md`: "`cursor` is assigned by the canonical SQLite append and therefore exists only after the transaction has committed"; "If the SQLite append fails, the attempted event receives no cursor, is not sent as a normal `log.event`, and is not mirrored to JSONL or stdout"; "Sanitization, SQLite append, commit and cursor assignment happen before optional mirrors or live wakeups." | A **committed SQLite row** makes an event canonical. Canonicity is produced by the **write** path alone. |
| What does `store_available()` represent? | Not defined in words by any current document. Its *uses* define it: `create_log_access` sets `logAccess.available`/`replayAvailable` from it; `/health` folds it into `ok`; `/api/logs/*` returns 503 without it; `/ws/logs` sends `log.error(event_store_unavailable)` + 1011 without it. `docs/structured-logging.md`: "If live access is disabled **or the canonical store is unavailable**, `available` is false"; "`log.error(code=event_store_unavailable)` followed by close code `1011` **on store failure**". | It is the **overall canonical-store / live-log availability** signal, not a read-capability flag. The documentation ties it to whether the canonical event pipeline as a whole can be honoured. |
| What constitutes recovery from a **read** failure? | No current document states it. Implementation: a successful `EventHub.query()` sets `ready`. Functionally, a successful `SELECT` is direct evidence that reads work again, and replay/history depend only on reads. | A successful canonical read is adequate, sufficient evidence that **read** capability has recovered. |
| What constitutes recovery from a **write** failure? | Test `test_event_hub_cursor_remains_unique_after_store_write_failure`: append fails → `state == "degraded"` → **a successful `emit`** → `state == "ready"` plus a `store_recovered` control. Test `test_audio_transcription_continues_while_event_store_is_degraded`: append broken → `assertFalse(store_available())` for the whole window → append restored → **successful emit** → `assertTrue(store_available())`. Historical design intent: "Recovery wird sichtbar und neue committed Events funktionieren wieder." | Every current test that demonstrates recovery from a write failure demonstrates it with a **successful write**. **No current test anywhere asserts that a read alone recovers a write failure.** |
| May a successful read clear a persistent write failure? | Current authority contains **no** operation-independent rule that any successful store operation means the whole store recovered — confirmed by full-text search of the current docs. Against it: "For an event that has been generated, no mirror setting can suppress SQLite persistence, replay, or live delivery"; "a mirror overload does not create a client protocol gap because every committed event remains replayable in SQLite"; "**Only a retention gap represents data no longer present in SQLite.**" Observed: in the mixed window the server streams live while silently dropping every new event, emitting no `log.error`, no close, and no `log.gap`. | **No.** Clearing a write failure on a successful read produces exactly the silent, unsignalled loss the documented gap model excludes. A successful `SELECT` proves read capability and nothing more. |
| What should `/ws/logs` advertise/do in a mixed read-ok/write-broken state? | `docs/structured-logging.md`: `log.error(code=event_store_unavailable)` + close `1011` "on store failure"; `logAccess.available` false when "the canonical store is unavailable". Historical intent: "Bei Storeausfall: kein normales Liveevent … bestehende Logverbindungen erhalten einen maschinenlesbaren Fehler und werden mit 1011 beendet, neue Logverbindungen werden abgewiesen, `hello.logAccess.available=false` mit Grund." | While canonical writes are failing, live log delivery cannot be honoured, so `/ws/logs` must answer `log.error(event_store_unavailable)` and close `1011`, and `logAccess.available` must be false. |

## 4. The three capabilities, explicitly distinguished

- **READ capability** — `SELECT` against the canonical store works. Sufficient
  for replay and for `/api/logs/*` history, and provable by a successful
  `EventHub.query()`.
- **WRITE/persistence capability** — `INSERT` + commit + cursor assignment
  works. This is what makes an event canonical at all, and it is provable only
  by a successful append.
- **Overall canonical-store / live-log availability** — what
  `store_available()` reports and what `/ws/logs`, `logAccess`, `/health` and
  `/api/logs/*` act on. Because a live log stream's whole purpose is to deliver
  newly generated events, this cannot be `ready` while new events cannot be
  persisted.

A successful `SELECT` proves the first. It does not prove the second. The
current implementation collapses all three into one last-operation-wins bit,
which is why the same instant yields contradictory public answers.

## 5. Reproduced behaviour at the binding commit (observed fact)

From `Evidence/03_Mixed_Capability_Reproduction/01_mixed_capability_before_fix.txt`,
with `_store.append` raising for the entire window and reads left working:

- persistence is **correct**: each failed append returns `None`, assigns no
  cursor, and the attempted event is absent from canonical history;
- state after the first write failure: `degraded`;
- state after a single successful `EventHub.query()`: `ready`;
- state after a second write failure: `degraded` again;
- the hub publishes the control sequence
  `commit, store_error, store_recovered, store_error` — subscribers are told
  the store **recovered** although no write ever succeeded again;
- over a real Uvicorn socket, in that same window:
  `/health` → `ok: true`, `/api/logs/events` → `200`, and `/ws/logs` → silence,
  then `log.hello`, `log.subscribed`, `log.event`, **no close** — while the
  in-process run of the same scenario produced `ok: false`, `503` and the same
  streaming `/ws/logs`. The answers differ only by which operation last touched
  the store.

## 6. Conclusion — Branch B

The blocker is decided **against** the C3 interpretation.

> A successful canonical read must **not** clear an unresolved canonical write
> failure. Overall canonical-store / live-log availability stays unavailable
> until write capability has actually been demonstrated again by a successful
> append.

Basis, in the priority order the prompt requires:

1. **Current authority** does not state the operation-independent recovery rule
   the current code implements; it does state the SQLite-first persistence
   guarantee, the "no cursor, no `log.event`" rule for a failed append, that
   live access is unavailable while the canonical store is unavailable, and
   that a retention gap is the *only* legitimate representation of missing
   data.
2. **Existing tests** encode write-driven recovery in every case and none
   encode read-driven recovery.
3. **Architecture invariant**: canonicity is created by the write path; a
   successful `SELECT` is not evidence about `INSERT`/commit.
4. **Observable behaviour**: the current rule produces a false
   `store_recovered` announcement, a false-healthy `/health`, and a live log
   stream that silently loses every new event without any documented gap
   signal.
5. **Implementation** is consulted last and is not treated as its own
   justification.

C3's finding that the *hang* was caused by the store legitimately reporting
`ready` again remains factually correct as an observation. What C3 got wrong is
calling that transition legitimate. It is a defect in the state model, and
correcting it removes the hang's cause rather than only its symptom.

## 7. What must change, and what must not

Must change (narrow): `StructuredEventHub` must track read capability and write
capability separately and derive the reported state from both, so a successful
read can recover a read failure without erasing an unresolved write failure.

Must not change: the `store_status()` / `store_available()` public shapes, the
SQLite-first ordering, `log.error(event_store_unavailable)` + close `1011`, the
`store_error` / `store_recovered` control vocabulary, the `/ws/logs` protocol,
or any behaviour outside the canonical-store health model.

Current documentation must be updated narrowly, per prompt Section 17, because
product semantics change.
