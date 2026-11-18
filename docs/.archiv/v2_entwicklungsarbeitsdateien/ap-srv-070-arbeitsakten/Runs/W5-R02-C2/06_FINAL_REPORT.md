NOT READY FOR ROOT REVIEW

# AP-SRV-070 / W5-R02-C2 - Final Report

## Identity

- Parent correction: W5-R02-C1 - Root-approved and pushed as
  `7f1ad1f02da9b1c4e3bf226f2a056066921ef77a`
- Binding start commit: `7f1ad1f02da9b1c4e3bf226f2a056066921ef77a`
- Binding start tree: `9c51c365701357e3b35dece563b156fc611b2c6e`
- VERSION: `2.0.0` (unchanged)

## GitHub run 34135266167 disposition

Windows job (`build-and-test (windows-latest)`): SUCCESS - full package
build/install checks, full unit/guard/release-tool suite, and `git diff
--check` all passed. Windows is not an open blocker.

Ubuntu job (`build-and-test (ubuntu-24.04)`): FAILURE, at
`python -m pytest -q tests/unit` - exactly one failure:
`test_fastapi_server_multi_user.py::FastAPIMultiUserWebSocketTests::
test_store_outage_closes_live_stream_and_recovery_allows_new_stream`,
`AssertionError: 'log.event' != 'log.error'` at (then) line 1792. Final
counts: `1 failed, 1707 passed, 14 skipped, 985 subtests passed`. Full
raw evidence in `Evidence/01_GitHub_CI_Failure/`.

## Exact file changed

```
tests/unit/test_fastapi_server_multi_user.py | 63 +++++++++++++++++++++++++++-
1 file changed, 62 insertions(+), 1 deletion(-)
```

## Production source: unchanged

No production file was edited. `VoiceSTT_server/event_logging.py` and
the `/ws/logs` handler in `api_fastapi_server/server.py` were read for
context only, both for this correction's own fix and for the
investigation described below, and confirmed unedited by `git diff
--stat`.

## Semantic explanation of the second race

The test induces a store outage (`events._store.append` raises) and then
required the *very next* WebSocket frame to be `log.error`. A
legitimate, already-committed `log.event` - queued to the live
connection before the store failure took effect - can validly arrive
first. The fix replaces the single blind `receive_json()` +
`assertEqual` with a bounded loop (max 50 intervening frames) that, for
each `log.event`, proves it is genuinely committed (strictly-monotonic
cursor continuing from the same tracking variable W5-R02-C1 already
introduced, a canonical-store round-trip via `events.query(after_cursor=
cursor-1, until_cursor=cursor, limit=1)`, and a check that the event name
is never `outage.not_committed`), then stops on the mandatory
`log.error` (asserting `code == "event_store_unavailable"` exactly as
before) or fails immediately on any unexpected frame type or on
exceeding the bound. The rest of the test - the `WebSocketDisconnect`
code `1011` check, the degraded-second-connection check, and the
recovery/replay check - is byte-for-byte unchanged.

## Exact 100x isolated result

**96/100 PASS, 4/100 FAIL.** Every failure is a genuine multi-second hang
(not an assertion mismatch), located at test line 1860 - the
"new connection while the store is already degraded" check, strictly
downstream of and untouched by this correction. A `faulthandler`-
instrumented repeat campaign captured one hang's full thread-stack dump,
showing the main thread blocked in `receive_json()` with the ASGI event
loop and every worker thread genuinely idle - no application code
executing or stuck. Full raw evidence:
`Evidence/03_Ubuntu_Isolated_Repetition/`.

## Exact 5x testfile result

**4/5 PASS, 1/5 FAIL** - same hang signature, same location, reproduced
once more under broader file scheduling exactly as Section 5 of the
prompt anticipated. Full raw evidence:
`Evidence/04_Ubuntu_Testfile_Repetition/`.

## Exact two Ubuntu full-suite results

Both **PASS**, zero failures:
- Run 1: `1708 passed, 14 skipped, 4 warnings, 985 subtests passed in 356.33s`
- Run 2: `1708 passed, 14 skipped, 4 warnings, 985 subtests passed in 352.10s`
Both match the pushed C1 baseline exactly (no test added/removed by this
correction). The pre-existing hang did not trigger in either run,
consistent with its measured ~4-6% per-invocation probability, and does
not change the disposition already established by the isolated/testfile
campaigns above. Full raw evidence: `Evidence/05_Ubuntu_Full_Regression/`.

## Windows targeted/file results

Both **PASS**: the exact target test (1 passed, 3.01s) and the full
`test_fastapi_server_multi_user.py` file (54 passed, 0 failed, 40.03s),
run once each on Windows 11/Python 3.12 per Section 11.4 (no repeated
stress campaign needed there, since real GitHub Actions is already green
on Windows at the C1 commit). Full raw evidence:
`Evidence/06_Windows_Targeted_Regression/`.

## `git diff --check`

Clean, exit code 0.

## Decisive, unrelated finding: the hang predates this correction entirely

The exact same target test, run 100 consecutive times from a **fresh,
unmodified copy of the already-pushed W5-R02-C1 commit**
(`7f1ad1f02da9b1c4e3bf226f2a056066921ef77a` - zero relation to this
correction's edit), reproduced the identical hang signature at a similar
rate: **94/100 PASS, 6/100 FAIL**. This conclusively proves the
intermittent hang is pre-existing in the exact commit that already
received external Root PASS, and is unrelated to this correction. Full
raw evidence and comparison methodology:
`Evidence/03_Ubuntu_Isolated_Repetition/01_100x_and_hang_investigation.txt`.

## Final correction commit / tree / parent

**No final commit was created.** HEAD remains
`7f1ad1f02da9b1c4e3bf226f2a056066921ef77a` (tree
`9c51c365701357e3b35dece563b156fc611b2c6e`) - unchanged from the binding
start commit. The one intended, individually-verified-correct test fix
remains as an uncommitted working-tree modification in this workspace
(`git status --porcelain` shows exactly
`M tests/unit/test_fastapi_server_multi_user.py`, nothing else).

## Exactly-one-commit-ahead proof

Not applicable - zero commits were created on top of the binding start
commit in this run, by design, per the disposition below.

## Remote unchanged proof

`git fetch origin` + `git rev-parse
origin/feat/einheitliche-triggerarchitektur-distributed` =
`7f1ad1f02da9b1c4e3bf226f2a056066921ef77a`, identical to the binding
start commit, confirmed at the end of this run.

## Workspace clean

Aside from the one intended, uncommitted test-file modification, the
workspace carries no stray artifacts, generated files, or partial state.

## Zero public writes

No push, no tag, no PyPI/GHCR/Docker Hub upload, no GitHub Release, and
no `release.py` invocation of any kind occurred at any point in this
run.

## W5-RC2 is not yet frozen

Neither this run nor the prior W5-R02-C1 run has produced a commit that
GitHub Actions has verified green on both required platforms after a
Root-authorized push. W5-RC2 remains unfrozen and will remain so until:
(1) this correction's own fix, and (2) a resolution for the
newly-discovered pre-existing intermittent hang documented above, are
both committed, Root-approved, and pushed, and real GitHub Actions then
runs green on both Windows and Ubuntu for that exact pushed commit.

## Disposition

This correction's own narrow, intended fix - correcting the
`log.event`-before-`log.error` timing assumption exposed by real GitHub
Actions run 34135266167 - is complete, correct, and individually
verified on every gate that specifically tests it. However, the
mandatory 100x/5x Ubuntu stress campaign (required precisely because
C1's lighter validation missed a similar issue) surfaced a second,
different, pre-existing, unrelated intermittent hang, conclusively shown
via direct comparison against the unmodified, already-Root-approved C1
commit to predate this correction entirely. Per the prompt's own
Section 17 stop conditions, this run therefore reports **NOT READY FOR
ROOT REVIEW**, creates no final commit, and recommends a dedicated future
correction (C3) to investigate and resolve the newly-found hang before
this test can be trusted at the reliability this frozen-RC process
requires.
