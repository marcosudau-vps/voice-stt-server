# AP-SRV-070 / W5-R02-C2 - Correction Report (Soll/Ist)

Written 2026-09-07, after implementation and validation, against
`02_PLAN.md` (written before the retained edit).

## Process note: an ordering slip, corrected before it mattered

An initial implementation attempt was made (reading the GitHub Actions
evidence and the test source, then editing the test file) **before**
`02_PLAN.md` existed - a direct violation of Section 6.2's required
ordering and the explicit "No historical waiver is allowed for C2"
instruction. This was caught immediately: the edit was reverted via
`git checkout -- tests/unit/test_fastapi_server_multi_user.py` (verified
clean via `git status --porcelain`), `02_PLAN.md` was then written
describing exactly the same intended change, and only after that was the
identical edit re-applied. No evidence in this archive is bound to the
out-of-order attempt; all evidence reflects the properly-sequenced
re-implementation. See `02_PLAN.md`'s own opening note for the same
disclosure.

## D1-Ubuntu (second race): planned vs. actual

Planned: replace the single `error = logs.receive_json();
self.assertEqual(error["type"], "log.error")` line with a bounded
consume loop proving each intervening `log.event` is genuinely committed
(cursor monotonicity + canonical-store round-trip +
not-`outage.not_committed`), stopping on `log.error`, failing on
anything else or on exceeding 50 intervening events; touch no other
file.

Actual: implemented exactly as planned, on the first attempt (after the
plan existed), with no further changes needed. Confirmed via `git diff
--stat`: exactly one file, 62 insertions / 1 deletion. Every gate
directly testing this specific fix (W5C3-G08 through W5C3-G15, plus the
Windows targeted/file runs W5C3-G19/G20 and the adversarial review
W5C3-G22) passes cleanly - see `04_GATE_INDEX.md`.

## Unplanned finding: a second, different, pre-existing intermittent hang

The mandatory 100x isolated-repetition campaign (Section 11.1, exactly
the extra rigor Section 5 called for after C1's 20x proved insufficient)
surfaced 4/100 failures. Investigation (full method, raw evidence, and
root-cause reasoning in
`Evidence/03_Ubuntu_Isolated_Repetition/01_100x_and_hang_investigation.txt`)
established:

1. All four failures are genuine multi-second hangs (killed by a 30s
   per-run timeout, zero output ever flushed), not fast assertion
   failures.
2. A `faulthandler`-instrumented repeat campaign caught one such hang
   in the act: the main thread was blocked inside
   `unavailable.receive_json()` at test line 1860 - the "new connection
   while the store is already degraded" check, a section **strictly
   downstream of, and untouched by,** this correction's edit. By the
   time any hang reaches that line, this correction's own new loop has
   already completed successfully in every single captured instance.
3. Running the exact same test 100 times from the **unmodified,
   already-pushed C1 commit** (`7f1ad1f02da9b1c4e3bf226f2a056066921ef77a`,
   copied fresh, zero relation to this correction) reproduced the
   identical failure signature at a similar rate: 94/100 pass, 6/100
   fail. This conclusively proves the hang predates this correction
   entirely and is unrelated to it.

Per the plan's own "No production/other source touched" section and the
prompt's Section 4 instruction ("If such a real product defect appears,
STOP and report NOT READY FOR ROOT REVIEW instead of broadening C2"),
this finding was **not** used to justify any additional edit in this
run. The evidence leans toward a test-harness-level (starlette
`TestClient`/`anyio` blocking-portal) timing artifact rather than an
application defect (the captured stack shows the ASGI event loop and
every background worker thread genuinely idle at the moment of the
hang, with no application code executing or stuck), but this was not
chased to a byte-level root cause - that determination, and any fix, is
left to a dedicated future correction.

## Exact file changed

```
tests/unit/test_fastapi_server_multi_user.py | 63 +++++++++++++++++++++++++++-
1 file changed, 62 insertions(+), 1 deletion(-)
```

No other file was touched. `VoiceSTT_server/event_logging.py` and the
`/ws/logs` handler in `api_fastapi_server/server.py` were read for
context (both for this correction's own fix and for the hang
investigation) and confirmed unedited.

## W5-RC1 and the C1 correction remain exactly as they were

This run does not modify, supersede, or retroactively alter the frozen
W5-R02 qualification archive or the W5-R02-C1 correction archive/commit
in any way. No file under either archive was edited.

## Disposition: no commit, no push

Because the mandatory 100x/5x Ubuntu stress gates did not pass as
literally required (for reasons proven unrelated to this correction's
own code), this run does not proceed to the final-commit step. See
`06_FINAL_REPORT.md` for the full disposition and
`Evidence/07_Final_Git_State/` for the exact final git state. The
correction's own fix remains available, uncommitted, in this workspace.
