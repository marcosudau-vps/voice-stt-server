# AP-SRV-070 / W5-R02-C2 - Correction Plan

Written before any tracked file is edited (Section 6.2). (Process note:
an initial implementation attempt was made before this plan file existed
and was reverted via `git checkout --` before writing this plan, to
comply exactly with Section 6.2's ordering requirement and the explicit
"No historical waiver is allowed for C2" instruction - the workspace was
confirmed clean again before this plan was written.)

## Confirmed defect (from real GitHub Actions run 34135266167, re-verified directly)

`tests/unit/test_fastapi_server_multi_user.py::FastAPIMultiUserWebSocketTests::
test_store_outage_closes_live_stream_and_recovery_allows_new_stream`,
line 1792 in the C1-corrected source (`error = logs.receive_json();
self.assertEqual(error["type"], "log.error")`), assumes the *very next*
WebSocket frame after inducing a store outage is always `log.error`.
Confirmed via the real job log (`gh api .../jobs/101784620842/logs`):
`AssertionError: 'log.event' != 'log.error'` - a legitimate,
already-committed `log.event` (queued to the live `/ws/logs` connection
before `events._store.append` was monkey-patched to fail) arrived first.
The store failure itself is correct (`OSError("simulated outage")`
logged; the preceding `self.assertIsNone(events.emit(...))` already
passed, proving the deliberately-failed event correctly returned `None`
and was not committed).

This is the same *class* of premature-assumption bug W5-R02-C1 already
fixed once in this exact test, at the earlier replay boundary (before
`log.replay_completed`) - C1 did not touch this second, structurally
identical assumption at the live/outage boundary (before `log.error`),
because C1's own local 20x-repeat and full-suite runs did not happen to
expose it; real GitHub Actions did.

No product/production defect is implicated: the sequence
"already-queued committed event delivered, then failure delivered" is
exactly the behavior the asynchronous live-stream design promises (see
prompt Section 2). Confirmed by direct reading of
`VoiceSTT_server/event_logging.py` and the `/ws/logs` handler in
`api_fastapi_server/server.py` before any edit - neither needs to
change.

## Exact intended file

`tests/unit/test_fastapi_server_multi_user.py` only. Replace the single
`error = logs.receive_json(); self.assertEqual(error["type"], "log.error")`
line with a bounded consume-loop (max 50 intervening `log.event` frames,
matching the pattern already used - and already correctly bounded by
loop-exit-on-`log.replay_completed` - at the replay boundary just above
it in the same test) that, for each intervening `log.event`:
- asserts its cursor strictly advances past the last consumed cursor
  (continuing the same `replay_cursor` variable the C1 fix already
  threads through this scope - no new state needed);
- asserts its event name is not `outage.not_committed`;
- asserts, via `events.query(after_cursor=cursor-1, until_cursor=cursor,
  limit=1)` (the same canonical-store API the test already calls at its
  end for `outage.not_committed` absence), that this exact cursor/event
  genuinely exists in the canonical store - the strongest available
  contract-level proof, not merely trusting the live queue's echo;
and, on `log.error`, asserts `code == "event_store_unavailable"` exactly
as before and stops consuming. Any other frame type still fails the
test immediately (`self.fail(...)`), preserving "no arbitrary event
swallowing". The bound fails with a clear message if exceeded without
ever seeing `log.error`, so a genuine regression (or an actual infinite
stream of events) cannot hang the test.

Nothing else in the test changes: the `assertIsNone(events.emit(...))`
outage-trigger, the `WebSocketDisconnect` code `1011` check, the
degraded-second-connection block, the recovery block
(`outage.recovered`/`outage.not_committed` absence check), and the
post-recovery replay block are all left byte-for-byte as they are today.

## No production/other source touched

Per Section 4, none of the following are edited, and no plan exists to
edit them: `VoiceSTT_server/event_logging.py`, the `/ws/logs`
implementation, event-store state transitions, scheduler behavior,
WebSocket protocol, replay protocol, model code, release tooling, or any
other test file. If validation below surfaces a genuine, reproducible
product-contract violation (not merely test-timing sensitivity), this
plan is abandoned and the run reports `NOT READY FOR ROOT REVIEW`
instead of broadening scope - no such defect is expected or has been
found in the investigation so far.

## Test strategy

1. Apply the single test-file edit described above.
2. Ubuntu 24.04 / Python 3.12: run the exact target test **100
   consecutive times**, all must PASS (no sleeps between runs).
3. Ubuntu: run the full `tests/unit/test_fastapi_server_multi_user.py`
   file **5 consecutive complete times**, all must PASS.
4. Ubuntu: run `python -m pytest -q tests/unit` (full suite) **twice
   consecutively**, both must PASS, zero failures, counts reconciled
   against the pushed C1 baseline (1708 passed / 14 skipped / 985
   subtests - no test added or removed by this correction, so the same
   counts are expected exactly, not merely "explainable").
5. Windows 11 / Python 3.12: run the exact target test once, and the
   full test file once - both must PASS (GitHub Actions Windows is
   already green at the C1 commit, so this is a sanity check, not a
   stress campaign).
6. `git diff --check` PASS.
7. Adversarial diff review: exactly one file changed, no production
   source, no workflow, no unrelated tests, no VERSION change, no
   generated artifacts staged.
8. Exactly one local commit on top of `7f1ad1f02da9b1c4e3bf226f2a056066921ef77a`.
   No push.

## No-go scope

- Do not touch any file other than
  `tests/unit/test_fastapi_server_multi_user.py`.
- Do not rebuild Kroko Free/Pro artifacts, production Docker images, or
  run any live E2E (Faster-Whisper/Kroko Free/Kroko Pro) - out of scope
  per Section 12, these belong to the future frozen W5-RC2 qualification.
- Do not regenerate the RC manifest or run `release.py dry-run` - not
  needed for a test-only correction.
- Do not read, print, copy, or hash
  `P:\GithubRepos\marcosudau-vps\voice-stt-server\secrets\voice-stt.env` -
  irrelevant to this correction.
- Do not push, tag, or touch `main`/`feat/einheitliche-triggerarchitektur`
  (the non-distributed branch) at any point.

## AGENTS.md "Größere Änderungsaktion" assessment

This is a single-assertion test-timing fix in one already-partially-
corrected test method, with zero production behavior change - the same
category of change W5-R02-C1 already assessed as not triggering
`docs/.archiv/README.md`'s dated-action-folder process (architecture,
public protocol/API, persisted format, security boundary, deployment
structure, or cross-module behavior changes). This plan plus
`03_CORRECTION_REPORT.md`'s post-implementation Soll/Ist comparison
serve as this run's equivalent record, both filed under
`_workflow-tools/AP-SRV-070/Runs/W5-R02-C2/`.

## Expected single-commit outcome

Exactly one local commit on `work/ap-srv-070-w5-r02-c2`, directly on top
of `7f1ad1f02da9b1c4e3bf226f2a056066921ef77a`, touching exactly
`tests/unit/test_fastapi_server_multi_user.py`, plus this run's own
archive files under `_workflow-tools/AP-SRV-070/Runs/W5-R02-C2/` (outside
the repository, not part of the commit). `VERSION` remains `2.0.0`. No
tag, no push, no publish.
