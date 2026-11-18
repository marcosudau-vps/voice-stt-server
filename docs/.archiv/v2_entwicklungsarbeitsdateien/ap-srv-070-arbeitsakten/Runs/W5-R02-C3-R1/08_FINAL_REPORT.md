READY FOR ROOT REVIEW

# AP-SRV-070 / W5-R02-C3-R1 — Final Report

## Selected semantic branch

**Branch B — persistent write failure must remain degraded.**

> A successful canonical read must not clear an unresolved canonical write
> failure. Overall canonical-store / live-log availability stays unavailable
> until write capability has actually been demonstrated again by a committing
> append.

External Root Review was right to refuse C3's interpretation. C3's factual
observation — that the hang occurred because the store reported `ready` again —
is confirmed and carried forward. C3's judgement that this transition was
legitimate product recovery is revised.

## Authority basis

Decided in the prompt's priority order, with the implementation consulted last
(`03_SEMANTIC_AUTHORITY_REVIEW.md`):

1. **Current documentation.** `docs/structured-logging.md` ties canonicity to
   the write path ("`cursor` … exists only after the transaction has
   committed"; "If the SQLite append fails, the attempted event receives no
   cursor, is not sent as a normal `log.event`"), states that for a generated
   event "no mirror setting can suppress SQLite persistence, replay, or live
   delivery", that live access is unavailable when "the canonical store is
   unavailable", and that "**Only a retention gap represents data no longer
   present in SQLite.**" A full-text search of all current, non-archive
   documentation found **no** statement that any successful store operation
   means the whole store recovered.
2. **Existing tests.** `test_event_hub_cursor_remains_unique_after_store_write_failure`
   and `test_audio_transcription_continues_while_event_store_is_degraded` both
   demonstrate recovery from a write failure through a **successful write**. No
   existing test asserts read-driven recovery.
3. **Architecture invariant.** A successful `SELECT` proves read capability. It
   is not evidence about `INSERT`/commit, and nothing becomes canonical without
   one.
4. **Observable behaviour.** See below.

## Mixed-capability reproduction

With `_store.append` raising for the entire window and reads left working, on
the unmodified binding tree (`04_REPRODUCTION_REPORT.md`,
`Evidence/03_Mixed_Capability_Reproduction/`):

- persistence itself was correct — every failed append returned `None`, took no
  cursor, and stayed out of canonical history;
- the state was a last-operation-wins bit: `degraded` after a write, `ready`
  after one successful read, `degraded` again after the next write;
- the hub published `commit, store_error, **store_recovered**, store_error` —
  subscribers were told the store had recovered although no write ever
  succeeded again;
- over a real Uvicorn socket, in that same window, `/health` answered
  `ok: true`, `/api/logs/events` answered `200`, and `/ws/logs` answered
  silence, then `log.hello`, `log.subscribed`, `log.event`, **no close** —
  while the in-process run of the identical scenario answered `ok: false`,
  `503`. A live log stream was accepting subscriptions and silently dropping
  every newly generated event, with no `log.error`, no close and no `log.gap`.

## Exact before/after state semantics

| Situation | Before | After |
|---|---|---|
| append fails | `degraded` | `degraded` |
| successful read while a write failure is unresolved | **`ready`** | **`degraded`** |
| successful write while a read failure is unresolved | `ready` | `degraded` |
| successful read while no write failure is outstanding | `ready` | `ready` |
| committing append after a write failure | `ready` | `ready` (+ `store_recovered`) |
| control frames in the mixed window | `commit, store_error, store_recovered, store_error` | `commit, store_error` |
| `/ws/logs` in the mixed window | `log.hello`/`log.subscribed`/`log.event`, no close | `log.error(event_store_unavailable)` + close `1011` |
| `/health`, `logAccess.available`, `/api/logs/*` in the mixed window | inconsistent with `/ws/logs` | all agree: `ok:false`, `false`, `503` |

Availability only ever becomes **stricter**: no state that was previously
`degraded` can now report `ready`.

## Final tracked files

```
VoiceSTT_server/event_logging.py             |  86 +++++++---
docs/structured-logging.md                   |  27 ++++
tests/unit/test_fastapi_server_multi_user.py | 229 +++++++++++++++++++++++++--
tests/unit/test_server_operations.py         | 143 +++++++++++++++++
4 files changed, 457 insertions(+), 28 deletions(-)
```

## Production source changed: yes, and why

`VoiceSTT_server/event_logging.py` only. `StructuredEventHub` now tracks
`_store_write_failed` and `_store_read_failed` separately and derives the
reported state from both; `_set_store_state` takes a required `capability`
argument and all eight call sites are labelled. This is the smallest change
that can represent mixed capability at all — the previous single bit
structurally could not.

Preserved: the public key set of `store_status()`, the boolean shape of
`store_available()`, the `store_error`/`store_recovered` vocabulary, SQLite-first
ordering, the single existing lock, and every `/ws/logs` protocol behaviour.
`api_fastapi_server/server.py` is byte-identical to the binding tree
(sha256 `8c10a5dd…`) — the `/ws/logs` handler was not edited.
`docs/structured-logging.md` was updated narrowly as prompt Section 17 requires.

## Ordering correction proof

Carried forward with its semantics intact: bounded at 50 intervening frames,
strictly increasing cursor, `outage.not_committed` rejected, unexpected frame
type fails, mandatory `log.error` with exact code `event_store_unavailable`,
mandatory close `1011`. The canonical-identity proof now uses
`events._store.query(...)` — a direct raw-store read that performs no
`EventHub` state mutation — instead of `events.query(...)`. That answers the
Root Review objection in prompt Section 3 directly: the assertion no longer
records read-capability health on the very state the test exercises.

The degraded-new-connection contract keeps its own test. Its deterministic
startup barrier was re-measured against the corrected semantics rather than
inherited: without the join 82/100 with 18 hangs, with the join 100/100.

## Validation summaries

| Requirement | Result |
|---|---|
| Ubuntu, ordering scenario, 100 consecutive | **100/100 PASS**, 0 hangs |
| Ubuntu, degraded-new-connection, 100 consecutive | **100/100 PASS**, 0 hangs |
| Ubuntu, mixed-capability/recovery, 100 consecutive | **100/100 PASS**, 0 hangs |
| Ubuntu, `test_fastapi_server_multi_user.py`, 10 consecutive | **10/10 PASS**, each `56 passed, 6 subtests` |
| Ubuntu, `test_server_operations.py`, 10 consecutive | **10/10 PASS**, each `27 passed` |
| Ubuntu, `pytest -q tests/unit`, 2 consecutive | **2/2 PASS**: `1712 passed, 14 skipped, 985 subtests`, both runs |
| Windows, ordering / degraded-connection / mixed-capability targeted | PASS: `1 passed`, `1 passed`, `4 passed` |
| Windows, both affected files | PASS: `56 passed, 6 subtests`; `27 passed` |
| `git diff --check` | PASS, clean |

320 fresh stress processes, each under `timeout --signal=ABRT` with
faulthandler: zero failures, zero hangs.

Count change vs. the pushed C1 baseline of `1708 passed, 14 skipped, 985
subtests`: exactly **+4 passed** — the four tests this correction adds
(T1–T4 combined, T5, the degraded-connection test, and T6). Skipped and subtest
counts unchanged; nothing was removed, skipped or renamed away.

## Real-network final probe

**50/50 consecutive PASS.** Real Uvicorn on an ephemeral loopback port, real
`websockets` client and real `httpx` requests, no TestClient. Each attempt
establishes the mixed condition through real EventHub/store operations —
including a real `EventHub.query()` in between — and asserts the state stays
`degraded`, the first frame is `log.error` with code `event_store_unavailable`,
the close code is `1011`, and `/health` reports `ok: false`. No new dependency
was added; `uvicorn`, `websockets` and `httpx` are existing project
dependencies.

## Version

`VERSION` = `2.0.0`, unchanged.

## Final Git state

- **Commit: `934e3be7c78aa9358f9b42b9fa4dc282bed54d6c`**
- **Tree: `2936f70ca44b7a902e1e5c7c5ca69eacc3154fdb`**
- **Direct parent: `7f1ad1f02da9b1c4e3bf226f2a056066921ef77a`**
- Branch: `work/ap-srv-070-w5-r02-c3-r1`
- Exactly **1** commit ahead of Distributed, 0 behind.
- The rejected C3 commit `d60936c…` is **not** an ancestor
  (`git merge-base --is-ancestor` returns non-zero) and was neither merged nor
  cherry-picked. Its workspace is unchanged at `d60936c…` with an empty status.
- `git status --porcelain` is literally empty.
- `origin/feat/einheitliche-triggerarchitektur-distributed` verified unchanged
  at `7f1ad1f…` after the commit.

## No public writes

Not pushed. No tag, no GitHub Release, no PyPI, no GHCR, no Docker Hub, no
canonical branch, no main. No amend after evidence binding, no rebase, no
merge, no cherry-pick, no force-push. The operator secret bundle was not read,
printed, copied, hashed, loaded or archived.

## Gates

**39 of 39 mandatory gates PASS. 0 FAIL. 0 N/A.** See `06_GATE_INDEX.md`.

## Deviations

`Keine bekannten W5-R02-C3-R1-Abweichungen.` Three items are recorded in
`07_DEVIATIONS.md` for transparency: the explicit revision of C3's conclusion,
the intended product-behaviour change under Branch B, and a pre-existing
Windows pytest-basetemp permission issue that is proven environmental by
reproducing it at the untouched binding commit.

## W5-RC2 status

**W5-RC2 is not frozen.** Freezing requires, in order: external Root PASS on
commit `934e3be7c78aa9358f9b42b9fa4dc282bed54d6c`; an exact authorized push of
that commit; and green GitHub Actions on that exact commit for **both** Windows
and Ubuntu. Nothing in this run substitutes for that, and no Root PASS is
claimed here.
