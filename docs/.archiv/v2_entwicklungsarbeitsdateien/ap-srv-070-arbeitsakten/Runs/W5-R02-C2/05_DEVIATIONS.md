# AP-SRV-070 / W5-R02-C2 - Deviations

## D1: A second, distinct, pre-existing intermittent hang was found during mandatory validation

- Expected: the exact target test passes 100/100 consecutive isolated
  Ubuntu runs (Section 11.1) and the surrounding file passes 5/5
  consecutive complete runs (Section 11.2).
- Actual: 96/100 and 4/5 respectively. Every failure is a genuine
  multi-second hang (not a fast assertion mismatch), located at test
  line 1860 - the "new WebSocket connection while the event store is
  already degraded" check - a section of the test **this correction does
  not touch**.
- Cause: not conclusively root-caused to a byte-level mechanism within
  this session's time budget. What was established with high confidence:
  (a) this correction's own new code is never implicated - in every
  captured hang, this correction's loop had already completed
  successfully by the time execution reached the hang point; (b) the
  exact same hang, at a similar rate (6/100), reproduces from the
  **unmodified W5-R02-C1 commit** (`7f1ad1f...`, the exact commit that
  already received external Root PASS and was pushed to Distributed),
  proving it predates this correction entirely; (c) a
  `faulthandler`-instrumented capture of one hang shows the ASGI event
  loop and every background worker thread genuinely idle at the moment
  of the hang, with no application code executing or stuck anywhere in
  the stack - suggestive of a `starlette.testclient`/`anyio`
  blocking-portal timing artifact rather than a production defect, but
  this is a reasoned inference, not a proven root cause.
- Source implicated: Unclear. Likely a test-harness-level issue, not a
  product defect, but not proven either way to the standard this
  process requires before dismissing it.
- Affected gates: W5C3-G16 (FAIL, 96/100), W5C3-G17 (FAIL, 4/5). All
  other gates, including every gate that specifically tests this
  correction's own intended fix (W5C3-G08 through G15, G19-G22), PASS.
- Correction Run required: **Yes - a future C3**, scoped specifically to
  this newly-found hang (root-cause it properly, e.g. with more
  `faulthandler` captures across more hangs, or by testing whether the
  same "back-to-back TestClient WebSocket connect" pattern reproduces in
  a minimal, unrelated test; then either a further test-only correction
  or, if a genuine product defect is eventually proven, a properly
  scoped production fix). This correction (C2) does not attempt that fix
  itself, per the prompt's Section 4 explicit instruction not to broaden
  scope without first proving a reproducible product defect - none was
  proven, so C2 stops here rather than guessing at a fix for a mechanism
  that is not yet understood.

## D2: An ordering slip (plan-after-edit) was caught and corrected before any evidence was generated

- Expected: `02_PLAN.md` exists before the first tracked-file edit
  (Section 6.2), no historical waiver for C2.
- Actual: an initial edit was made before the plan file existed. Caught
  immediately, reverted via `git checkout --` (confirmed clean via `git
  status --porcelain`), the plan was then written, and the identical
  edit was re-applied only afterward.
- Cause: process discipline lapse on this session's part.
- Source implicated: No - the edit itself, once properly sequenced, is
  correct and identical to what would have been produced anyway.
- Affected gates: W5C3-G04 - still PASS, since by the time any
  gate-relevant evidence was generated, the plan genuinely did precede
  the retained edit.
- Correction Run required: No - fully self-corrected within this run,
  documented transparently rather than hidden.

## D3: Secret bundle - not consumed

Per Section 7 of the prompt, the operator secret bundle at
`P:\GithubRepos\marcosudau-vps\voice-stt-server\secrets\voice-stt.env`
was not read, printed, copied, hashed, or loaded into the environment at
any point in this run. It is irrelevant to this test-only correction.

## Overall disposition

D1 alone is sufficient to force `NOT READY FOR ROOT REVIEW` per the
prompt's own Section 17 stop conditions. This correction's own intended,
narrow fix is complete and independently verified; the newly-found,
pre-existing, unrelated hang is the sole reason a clean success state was
not reached in this run.
