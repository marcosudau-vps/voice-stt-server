# AP-SRV-070 / W5-R02-C3-R1 — Plan

Written before the first tracked repository edit. `git status --porcelain` and
`git diff` in the R1 worktree were both empty at the moment this file was
created — see `Evidence/00_Preflight/02_plan_boundary.txt`. Everything executed
so far (authority review, mixed-capability reproduction) used untracked
diagnostics under the run archive and a native Ubuntu copy; no tracked file was
edited, and none was edited and reverted.

## 1. Semantic decision — Branch B

`03_SEMANTIC_AUTHORITY_REVIEW.md` decides the blocker **against** the C3
interpretation:

> A successful canonical read must not clear an unresolved canonical write
> failure. Overall canonical-store / live-log availability stays unavailable
> until write capability has actually been demonstrated again by a successful
> append.

Basis: current documentation states the SQLite-first persistence guarantee, the
"failed append → no cursor, no `log.event`" rule, that live access is
unavailable while the canonical store is unavailable, and that a retention gap
is the only legitimate representation of missing data; no current document
states an operation-independent recovery rule; every existing test that shows
recovery from a write failure shows it through a **successful write**; and the
reproduction shows the current rule produces a false `store_recovered`
announcement, a false-healthy `/health`, and a live `/ws/logs` stream that
silently loses every newly generated event.

## 2. Planned implementation

### 2.1 Product — `VoiceSTT_server/event_logging.py` (only production file)

Replace the single last-operation-wins `_store_state` string with two
independent capability flags inside `StructuredEventHub`, and derive the
reported state from them:

- `_store_write_failed` — set by a failed append, cleared by a successful
  append;
- `_store_read_failed` — set by a failed read, cleared by a successful read;
- derived state: `disabled` when there is no store, otherwise `degraded` if
  either capability is failing, else `ready`.

`_set_store_state(state, *, error=None)` gains a required `capability`
argument (`"write"` or `"read"`) and each of its eight call sites is labelled:

| Call site | Capability |
|---|---|
| `emit`, append raised | write |
| `emit`, append succeeded | write |
| `query`, raised / succeeded | read |
| `latest_cursor`, raised | read |
| `oldest_cursor`, raised | read |
| `retention_cursor`, raised | read |
| `store_status`, cursor read raised | read |

Preserved exactly: the public shapes of `store_status()` (same keys) and
`store_available()`; the `store_error` / `store_recovered` control vocabulary
and their existing "re-announce on a new error type" behaviour; SQLite-first
ordering; every `/ws/logs` protocol behaviour.

This is a state-model correction, not a redesign: no public API shape changes,
no new dependency, no concurrency change, and nothing outside the canonical
store health model is touched.

### 2.2 Documentation — `docs/structured-logging.md`

Required by prompt Section 17 because product semantics change. Narrow
addition stating what store availability means, that a successful read recovers
a read failure only, that a write failure is cleared only by a successful
append, and what live logging does while canonical writes are unavailable. No
historical archive document is rewritten.

### 2.3 Tests — `tests/unit/test_server_operations.py` and
`tests/unit/test_fastapi_server_multi_user.py`

Targeted semantic tests T1–T6 from prompt Section 13:

- **T1** write failure → degraded, failed event non-canonical;
- **T2** successful read after write failure → **still degraded** (the central
  regression test);
- **T3** second write still fails, nothing falsely canonical;
- **T4** real write recovery → ready, `store_recovered` published;
- **T5** read failure → degraded, successful read → ready when no write failure
  is outstanding;
- **T6** mixed capability + `/ws/logs` → `log.error(event_store_unavailable)` +
  close 1011, verified in-process and at least once over a real network.

Carried forward from C2/C3:

- the ordering correction (bounded loop, strictly increasing cursor,
  `outage.not_committed` forbidden, unexpected frame fails, mandatory exact
  error code, mandatory close 1011) — but the canonical-identity proof switches
  from `events.query(...)` to a **direct raw-store read**
  (`events._store.query(...)`), which performs no hub state mutation. This is
  the "direct raw-store read specifically isolated from EventHub state
  mutation" option the prompt lists, and it removes the state-mutating
  assertion Root Review objected to;
- explicit degraded-new-connection coverage, kept as its own test.

Under Branch B the degraded state now survives a read, so the C3 test no longer
depends on nothing having read the store. The service-startup join is
re-evaluated against measurement: it is kept only if a successful *write* from
the startup worker can still race the outage, which Branch B does not change;
whichever shape measures deterministic is used, and the choice is recorded.

## 3. Planned validation (prompt Section 14)

Ubuntu 24.04 / Python 3.12: ordering scenario 100/100; degraded-new-connection
100/100; mixed-capability/recovery regression 100/100;
`tests/unit/test_fastapi_server_multi_user.py` 10/10;
`tests/unit/test_server_operations.py` 10/10; `pytest -q tests/unit` 2/2.
Windows 11 / Python 3.12: ordering, degraded-new-connection, mixed-capability
targeted tests, and both affected files. Real-network final mixed-capability
probe ≥ 50 consecutive PASS. `git diff --check`, full diff archived,
adversarial scope review. Hard timeout protection on every stress loop.

## 4. Out of scope

Untouched: protocol-v2, activation, trigger, wake word, model management, Kroko
runtime, packaging, release tooling, Docker, GitHub Actions, dependencies,
`VERSION` (stays `2.0.0`). The `/ws/logs` handler in
`api_fastapi_server/server.py` is not edited — the correction is in the state
model it reads.

## 5. Git end state

Exactly one local commit whose direct parent is
`7f1ad1f02da9b1c4e3bf226f2a056066921ef77a`. The rejected C3 commit
`d60936c…` is not merged, cherry-picked or built upon; the R1 branch was
created directly from the remote binding commit and this is proven in
preflight. Clean worktree, remote unchanged, no push, no tag, no publication.

## 6. Stop conditions

If the state-model correction cannot be kept narrow, if canonical SQLite-first
guarantees would be weakened, if a failed event could be exposed as committed,
or if any mandatory campaign fails, stop with `NOT READY FOR ROOT REVIEW`.
