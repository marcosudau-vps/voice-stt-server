READY FOR ROOT REVIEW

# AP-SRV-070 / W5-R02-C3 — Final Report

## Identity

- Binding start commit: `7f1ad1f02da9b1c4e3bf226f2a056066921ef77a`
- Binding start tree: `9c51c365701357e3b35dece563b156fc611b2c6e`
- **Final C3 commit: `d60936c509d7b95e406c671fd3f91cc5f2af5add`**
- **Final tree: `71da4a1ab4d75844825c90a28c91644d18f01d3e`**
- **Parent: `7f1ad1f02da9b1c4e3bf226f2a056066921ef77a`** (direct, exactly as required)
- Branch: `work/ap-srv-070-w5-r02-c3`
- VERSION: `2.0.0`, unchanged
- Remote `origin/feat/einheitliche-triggerarchitektur-distributed`: still
  `7f1ad1f02da9b1c4e3bf226f2a056066921ef77a`. **Not pushed.**

## Root cause — RC-A, with evidence

The intermittent hang is **neither a production defect nor a TestClient/AnyIO
harness defect**. It is a test-structure defect (A3).

`test_store_outage_closes_live_stream_and_recovery_allows_new_stream` bundled
two independent product contracts into one sequence and let the second inherit
its precondition from the first. That precondition does not survive:

- the test simulates the outage by breaking **only** `_store.append`; every
  canonical read keeps working;
- `EventHub.query()` marks the store `ready` on every successful read
  (`VoiceSTT_server/event_logging.py` line 1189);
- the test's own still-open live `/ws/logs` loop calls
  `service.events.query(...)` whenever it drains a commit control
  (`api_fastapi_server/server.py` line 8838);
- a second path exists too: an in-flight `emit` from the service's own startup
  worker `VoiceSTTServerReady` resolves `self._store.append` before the outage
  patch replaces it, still succeeds, and reaches `_set_store_state("ready")`
  (`event_logging.py` line 978);
- with the store reporting `ready`, a new `/ws/logs` connection correctly takes
  the **normal subscribe path**, and a client waiting for `log.error` without
  ever sending `subscribe` blocks forever.

C2's reading of its own faulthandler dump is corrected: the missing `/ws/logs`
frame does not show that no application code was running. The handler coroutine
was **suspended** in `await websocket.receive_text()`, and a suspended coroutine
contributes no frame to a thread dump.

### Control matrix

| Control | Attempts | Hangs | Result |
|---|---:|---:|---|
| 1 baseline combined test (pytest, unmodified binding tree) | 50 | 0 | 48 PASS / 2 FAIL — both the ordering defect, which masks the hang |
| 1b instrumented replica | 100 | 0 | 100 PASS; store measured `degraded` every time |
| 1c same replica, commit-control race amplified | 100 | **86** | 14 PASS / 86 HANG — **exact 100/100 correlation**: HANG ⟺ store `ready`, PASS ⟺ store `degraded` |
| 1d deterministic causal isolation | 100 | 0 | one successful `query()` flips `degraded → ready`; the new connection then answers `log.hello`, not `log.error` |
| 2 isolated degraded connection, no startup barrier | 100 | 18 | 82 PASS |
| 2b same, with the startup barrier | 100 | 0 | **100 PASS** |
| 3 two sequential `/ws/logs` lifecycles, healthy store | 100 | 0 | **100 PASS** → refutes A2 (TestClient/AnyIO) |
| 4 degraded connection across a fresh TestClient lifecycle | 100 | 0 | **100 PASS** |
| 5 real Uvicorn server + real WebSocket client, no TestClient | 50 | 0 | **50 PASS**, ~10 ms each → refutes A1 (production defect) |

Full detail in `03_ROOT_CAUSE_REPORT.md` and `Evidence/02..04`.

## Exact file changed

```
tests/unit/test_fastapi_server_multi_user.py | 149 +++++++++++++++++++++++++--
1 file changed, 140 insertions(+), 9 deletions(-)
```

## Production source: unchanged

No production file was edited. Confirmed by `git diff --stat` and additionally
by sha256, both in the worktree and in the Ubuntu copy that actually executed
every stress campaign: `api_fastapi_server/server.py` `8c10a5dd…` and
`VoiceSTT_server/event_logging.py` `3d707945…`, identical to the binding tree.

## What the commit contains

1. **The validated W5-R02-C2 ordering correction, carried forward.** Bounded
   receive loop (max 50 frames), strict cursor monotonicity, canonical-store
   identity verification per intervening event, `outage.not_committed`
   explicitly rejected, unexpected frame types fail, mandatory
   `log.error(event_store_unavailable)` cannot be skipped, close 1011
   unchanged. C3 independently reproduced the defect this fixes: 2 of 50
   baseline runs failed with `'log.event' != 'log.error'`, the same failure as
   GitHub Actions run `34135266167`.

2. **The hang fix.** The already-degraded new-connection check moves out of the
   combined sequence into its own test,
   `test_new_log_stream_reports_degraded_store_and_closes`, with its own app
   and TestClient lifecycle. It establishes the degraded state through the same
   real failure mechanism and **asserts** the precondition
   (`assertFalse(events.store_available())`) before connecting. A deterministic
   barrier — `service.ready_thread.join(timeout=30)` plus
   `assertFalse(is_alive())` — removes the startup-emit race. That is a join on
   the exact background thread the evidence implicates: no sleep, no increased
   timeout, no retry, no relaxed assertion.

Coverage is preserved. Both contracts remain asserted, now independently. Test
count 54 → 55.

## Validation results

| Requirement | Result |
|---|---|
| Ubuntu, ordering scenario, 100 consecutive | **100/100 PASS**, 0 hangs |
| Ubuntu, degraded-new-connection, 100 consecutive | **100/100 PASS**, 0 hangs |
| Ubuntu, affected file, 10 consecutive complete | **10/10 PASS**, each `55 passed, 6 subtests` |
| Ubuntu, `pytest -q tests/unit`, 2 consecutive | **2/2 PASS**: `1709 passed, 14 skipped, 985 subtests`, both runs |
| Windows, ordering scenario | PASS, `1 passed in 4.06s` |
| Windows, degraded-new-connection | PASS, `1 passed in 2.27s` |
| Windows, affected file | PASS, `55 passed, 6 subtests passed in 48.50s` |
| `git diff --check` | PASS, clean |

210 fresh stress processes, each under `timeout --signal=ABRT` with
faulthandler enabled: **zero hangs**.

### Count change vs. the C1 baseline

C1 baseline: `1708 passed, 14 skipped, 985 subtests`. C3: `1709 passed, 14
skipped, 985 subtests`. The difference is exactly `+1 passed` — the one test
this correction adds. No test was removed, skipped or renamed away; skipped and
subtest counts are unchanged.

## Gates

**32 of 32 mandatory gates PASS. 0 FAIL. 0 N/A.** See `05_GATE_INDEX.md`.

Literal gate semantics were applied per prompt Section 4:
- W5C4-G04: `02_PLAN.md` existed before the first tracked edit, with
  `git status --porcelain` and `git diff --stat` both proven empty at that
  moment. No tracked file was edited and reverted at any point.
- W5C4-G29: exactly one local commit, not N/A.
- W5C4-G30: `git status --porcelain` is literally empty.

## Deviations

`Keine bekannten W5-R02-C3-Abweichungen.` Two diagnostic findings (C2's
faulthandler interpretation; `faulthandler.dump_traceback_later(exit=True)`
exiting with status 0 on this build) are documented in `06_DEVIATIONS.md`
because they matter for later runs. Neither affects a reported result.

## C2 workspace

`...\workspaces\ap-srv-070-w5-r02-c2` was used read-only. Verified after this
run: still at `7f1ad1f…`, still carrying exactly its one uncommitted
modification (`tests/unit/test_fastapi_server_multi_user.py`, sha256
`96560d84…`, unchanged). Nothing was edited or committed there. Its diff is
archived verbatim in this run's evidence.

## Secret boundary

`P:\GithubRepos\marcosudau-vps\voice-stt-server\secrets\voice-stt.env` lies
outside every worktree, was not needed, and was not read, printed, copied,
hashed or loaded at any point.

## Publication state

Not pushed. No tag, no GitHub Release, no PyPI, no GHCR, no Docker Hub, no
canonical branch, no main. No amend after evidence binding, no rebase, no
merge, no force-push. Remote Distributed verified unchanged at `7f1ad1f…`
after the commit.

## Next step

External Root review of commit `d60936c509d7b95e406c671fd3f91cc5f2af5add`.
Only after Root PASS: push that exact commit, let real GitHub Actions run on
it, and expect Windows PASS and Ubuntu PASS before freezing it as W5-RC2.
