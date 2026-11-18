# AP-SRV-070 / W5 — Frozen-RC Correction
## W5-R02-C2 — Remaining Ubuntu WebSocket Outage-Race
### Model: Sonnet 5

---

# 0. Run identity

- **Project:** AP-SRV-070
- **Phase:** W5 — Release Candidate Qualification
- **Parent correction:** W5-R02-C1
- **Correction run:** W5-R02-C2
- **Purpose:** Correct the one remaining race-sensitive assertion exposed by real GitHub Actions after C1
- **Model:** Anthropic Sonnet 5
- **Session:** CONTINUE EXISTING W5-R02-C1 SESSION
- **Repository:** `marcosudau-vps/voice-stt-server`
- **Local project root / session start folder:** `P:\GithubRepos\marcosudau-vps\voice-stt-server`
- **Distributed branch:** `feat/einheitliche-triggerarchitektur-distributed`
- **Binding start commit:** `7f1ad1f02da9b1c4e3bf226f2a056066921ef77a`
- **Binding start tree:** `9c51c365701357e3b35dece563b156fc611b2c6e`
- **Direct parent of binding start commit:** `bb7a4bb7cc27897aeb257aa5a5b9f3b550b8f602`
- **Product version:** `2.0.0` — MUST remain unchanged
- **NEW correction workspace:** `P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-070-w5-r02-c2`
- **Prompt source:** `P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Prompts\2026-09-07_AP-SRV-070_W5_R02_C2_SONNET5.md`
- **Correction run/evidence root:** `P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W5-R02-C2\`
- **Parent C1 evidence:** `P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W5-R02-C1\`
- **Original frozen qualification evidence:** `P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W5-R02\`

This is an **extremely narrow test-correction run**.

No release publication, no new RC freeze, and no push are allowed during this run.

If this C2 commit later receives external Root PASS and is pushed exactly as approved, GitHub Actions on that exact pushed commit must be green on both required platforms before it may become the source basis for internal `W5-RC2`.

---

# 1. Binding post-C1 GitHub Actions evidence

C1 was Root-approved and pushed exactly as:

`7f1ad1f02da9b1c4e3bf226f2a056066921ef77a`

Real GitHub Actions then ran on exactly that commit.

## Workflow run

- **Run ID:** `34135266167`

## Windows job

`build-and-test (windows-latest)`

Result:

`SUCCESS`

All package build/install checks, full unit/guard/release-tool suite, and `git diff --check` passed.

Therefore **Windows is not an open blocker in this correction**.

## Ubuntu job

`build-and-test (ubuntu-24.04)`

Result:

`FAILURE`

All steps through:

- checkout
- Python 3.12
- Linux audio prerequisites
- package build
- `twine check`
- fresh wheel install
- `pip check`
- installed distribution import/version
- console scripts
- installed assets
- development/test dependency installation

passed.

The single failure was in:

`python -m pytest -q tests/unit`

Exact final result:

```text
1 failed, 1707 passed, 14 skipped, 985 subtests passed
```

Exact failing test:

`tests/unit/test_fastapi_server_multi_user.py::FastAPIMultiUserWebSocketTests::test_store_outage_closes_live_stream_and_recovery_allows_new_stream`

The assertion failed after the store outage was intentionally induced:

```text
expected: log.error
actual:   log.event
```

The store failure itself occurred exactly as intended:

`OSError("simulated outage")`

and the canonical event store was logged as failed/degraded.

This means C1 fixed the **first** timing assumption before `log.replay_completed`, but a **second equivalent timing assumption** remained later in the same test.

---

# 2. Root-cause constraint

Do not treat this as evidence that production outage behavior is broken.

The observed sequence is compatible with the existing asynchronous live-stream design:

1. earlier events are successfully committed to the canonical event store;
2. one or more of those committed events may already be queued/in flight to `/ws/logs`;
3. the test replaces the store's append operation with a deliberate failure;
4. `events.emit("system", "outage.not_committed")` fails to commit and correctly returns `None`;
5. the live WebSocket can still deliver an already-committed `log.event` that was queued earlier;
6. only then does the connection deliver `log.error / event_store_unavailable` and close.

Therefore this line is still too strict:

```python
error = logs.receive_json()
self.assertEqual(error["type"], "log.error")
```

The test must validate the **semantic boundary**, not assume zero queued committed events.

---

# 3. Required end state

The corrected test must allow:

```text
zero or more legitimate already-committed log.event frames
→ mandatory log.error(code=event_store_unavailable)
→ mandatory WebSocket close code 1011
```

while remaining strict enough to prove all of the following:

- the deliberately failed event `outage.not_committed` is never exposed as a committed `log.event`;
- any `log.event` received before the error is genuinely canonical/committed, not invented or accepted after failed persistence;
- event cursors remain strictly monotonic;
- the test cannot spin forever;
- unexpected frame types still fail;
- the expected `log.error` is mandatory;
- the error code remains exactly `event_store_unavailable`;
- the WebSocket still closes with code `1011`;
- a new connection while the store is degraded still receives the correct error/close behavior;
- restoring the store still allows recovery/new stream behavior;
- `outage.not_committed` remains absent from canonical query results.

No weakening of outage semantics is acceptable.

---

# 4. Preferred correction shape

Prefer a **test-only correction** in:

`tests/unit/test_fastapi_server_multi_user.py`

Production source is protected for this run.

Do not modify:

- `VoiceSTT_server/event_logging.py`
- `/ws/logs` production implementation
- event-store state transitions
- scheduler behavior
- WebSocket protocol
- replay protocol
- model code
- release tooling

unless you first produce a new, minimal, reproducible product defect showing that the current production behavior violates a documented contract.

If such a real product defect appears, STOP and report `NOT READY FOR ROOT REVIEW` instead of broadening C2.

## Semantic validation for intervening log.event frames

The implementation should not merely "skip all log.event until error".

For each intervening event, prove enough to establish that it is a legitimate committed event. Suitable evidence/assertions may include:

- valid positive/monotonic canonical cursor;
- cursor strictly advances from the last consumed replay/live cursor;
- event/cursor exists in the canonical store or can otherwise be shown to have been committed;
- event name is not `outage.not_committed`.

Choose the most robust contract-level assertion available in the current event-store API.

Do not use arbitrary sleeps.

Do not add timing delays intended merely to make the race disappear.

## Bounded receive

The wait for `log.error` must be bounded by a clear maximum number of intervening frames and/or existing receive timeout behavior.

An infinite drain loop is not acceptable.

If the bound is reached without `log.error`, fail with a useful message.

---

# 5. Why stronger repetition is required this time

C1 obtained:

`20/20 PASS`

for the targeted Ubuntu test and a locally green Ubuntu full suite.

Real GitHub Actions still exposed the second race-sensitive assertion.

Therefore C2 must not use "one targeted pass + one full-suite pass" as sufficient confidence.

The validation below intentionally exercises both isolated and broader suite contexts.

---

# 6. Governance / workspace

## 6.1 New workspace

Continue the existing Agent session for context, but create a **new** worktree:

`P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-070-w5-r02-c2`

Do not modify C1 or W5-R02 frozen workspaces.

Suggested local branch:

`work/ap-srv-070-w5-r02-c2`

Start exactly from:

`7f1ad1f02da9b1c4e3bf226f2a056066921ef77a`

## 6.2 Plan before implementation

Before editing any tracked source/test/doc file:

1. fetch origin;
2. verify exact start SHA/tree;
3. create the run archive;
4. copy this prompt byte-identically;
5. create the correction plan;
6. create any repository-required dated AP-SRV-070 archive plan;
7. only then make the test edit.

No historical waiver is allowed for C2.

## 6.3 No push before external Root PASS

During C2:

- exactly one final local correction commit;
- no push;
- no tag;
- no GitHub Release;
- no PyPI;
- no GHCR;
- no Docker Hub;
- no canonical branch;
- no `main`;
- no force operation.

---

# 7. Secret boundary

The local operator secret bundle exists outside all Git worktrees as a sibling of `main`/worktrees under the local project root:

`P:\GithubRepos\marcosudau-vps\voice-stt-server\secrets\voice-stt.env`

C2 does **not** need it.

Do not read it.
Do not print it.
Do not copy it.
Do not hash its contents.
Do not load it into the environment.
Do not put it into Evidence.

The file is irrelevant to this test-only correction.

---

# 8. Run archive

Create:

`P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W5-R02-C2\`

with:

```text
W5-R02-C2\
├── 00_PROMPT.md
├── 01_CORRECTION_CONTEXT.md
├── 02_PLAN.md
├── 03_CORRECTION_REPORT.md
├── 04_GATE_INDEX.md
├── 05_DEVIATIONS.md
├── 06_FINAL_REPORT.md
└── Evidence\
    ├── 00_Preflight\
    ├── 01_GitHub_CI_Failure\
    ├── 02_Test_Semantics\
    ├── 03_Ubuntu_Isolated_Repetition\
    ├── 04_Ubuntu_Testfile_Repetition\
    ├── 05_Ubuntu_Full_Regression\
    ├── 06_Windows_Targeted_Regression\
    └── 07_Final_Git_State\
```

Copy the prompt byte-identically into:

`00_PROMPT.md`

Record source/copy SHA256.

Evidence must never contain secret values.

---

# 9. Preflight evidence

Record:

- `git fetch origin`
- remote Distributed SHA
- local new-worktree SHA
- tree SHA
- direct parent
- branch
- `git status --porcelain`
- `git worktree list`
- Python version
- OS/platform details
- Ubuntu 24.04/Python 3.12 environment used for qualification

Binding requirements:

```text
origin/feat/einheitliche-triggerarchitektur-distributed
= 7f1ad1f02da9b1c4e3bf226f2a056066921ef77a

tree
= 9c51c365701357e3b35dece563b156fc611b2c6e
```

Mismatch = STOP.

Also record the relevant GitHub Actions run/job failure evidence for run `34135266167` if accessible through `gh`; otherwise document the exact supplied run/job identity and failure excerpt without inventing evidence.

---

# 10. Implementation requirements

Correct only the remaining race-sensitive section of:

`test_store_outage_closes_live_stream_and_recovery_allows_new_stream`

The correction should conceptually behave like:

```text
induce store outage
→ verify attempted event did not commit
→ consume bounded sequence:
     if log.event:
         prove it was already committed
         prove monotonic cursor
         prove it is not outage.not_committed
         continue
     if log.error:
         require event_store_unavailable
         stop consuming
     otherwise:
         fail
→ require error was observed
→ require close 1011
```

Do not copy this pseudocode blindly if the repository exposes a cleaner helper/contract.

Keep the rest of the outage/recovery test semantically intact.

If a tiny local test helper makes the assertion clearer and remains private to this test module/class, that is acceptable.

Avoid general-purpose production helpers or architecture changes.

---

# 11. Mandatory validation

## 11.1 Ubuntu isolated stress

On Ubuntu 24.04 / Python 3.12 run the exact formerly failing test:

**100 consecutive executions, all PASS.**

Do not use sleeps between runs to mask scheduling.

Record every exit status or a reliable loop summary proving all 100 succeeded.

If any of the 100 fails, C2 is not complete.

## 11.2 Ubuntu surrounding-file stress

Run:

`tests/unit/test_fastapi_server_multi_user.py`

**5 consecutive complete executions, all PASS.**

This is important because the race was exposed under broader suite scheduling, not merely isolated execution.

Record counts and exit codes for all five.

## 11.3 Ubuntu full regression

Run:

`python -m pytest -q tests/unit`

**2 consecutive complete executions, both PASS** in a stable Ubuntu 24.04/Python 3.12 environment.

Expected count should be explainable against the pushed C1 baseline:

```text
1708-ish PASS / 14 skipped / 985 subtests
```

Exact pass count may change only if C2 adds/removes a test case; explain any difference.

There must be zero failures in both runs.

## 11.4 Windows targeted regression

Because current real GitHub Actions is already green on Windows at the C1 commit, do not waste time on repeated full Windows suites before Root Review.

However, run on Windows 11/Python 3.12:

- the exact changed test once;
- the full `tests/unit/test_fastapi_server_multi_user.py` once.

Both must PASS.

The authoritative cross-platform check for the **new C2 commit** will be GitHub Actions only after Root PASS + authorized push.

## 11.5 Static Git validation

Run:

`git diff --check`

PASS required.

Perform an adversarial diff review confirming:

- no production source modified;
- no workflow modified;
- no unrelated tests changed;
- no version changed;
- no generated artifacts committed.

---

# 12. Do not rerun unrelated heavy W5 qualification

C2 must NOT rebuild:

- Kroko Free native artifact
- Kroko Pro native artifact
- Production Docker Free/Pro images
- Faster-Whisper live E2E
- Kroko Free live E2E
- Kroko Pro live E2E
- RC manifest
- release dry-run

unless a source dependency unexpectedly requires it, in which case document why before running.

These belong to the future frozen W5-RC2 qualification.

The purpose of C2 is only to reach a CI-stable source candidate.

---

# 13. C2 gates

Use exactly these IDs in `04_GATE_INDEX.md`.

## Governance / identity

- **W5C3-G01** Start remote commit equals `7f1ad1f02da9b1c4e3bf226f2a056066921ef77a`.
- **W5C3-G02** Start tree equals `9c51c365701357e3b35dece563b156fc611b2c6e`.
- **W5C3-G03** New clean C2 worktree created; prior worktrees untouched.
- **W5C3-G04** C2 plan/archive plan exists before first tracked edit.
- **W5C3-G05** VERSION remains exactly `2.0.0`.
- **W5C3-G06** No push/tag/release/publication performed.

## Root-cause / implementation

- **W5C3-G07** GitHub Actions run `34135266167` failure is accurately recorded as one Ubuntu failure with Windows green.
- **W5C3-G08** Production event-store/WebSocket code remains unchanged.
- **W5C3-G09** Test now permits only legitimate already-committed `log.event` frames before mandatory outage `log.error`.
- **W5C3-G10** Intervening event cursors are strictly monotonic and validated as committed by a robust canonical-store contract.
- **W5C3-G11** `outage.not_committed` cannot be accepted as an intervening committed event.
- **W5C3-G12** Receive/drain logic is bounded and fails on unexpected frame types.
- **W5C3-G13** `log.error` with exact code `event_store_unavailable` remains mandatory.
- **W5C3-G14** WebSocket close code `1011` remains mandatory.
- **W5C3-G15** Degraded-new-connection and post-restore recovery assertions remain intact.

## Validation

- **W5C3-G16** Exact Ubuntu target test passes 100 consecutive executions.
- **W5C3-G17** Ubuntu `test_fastapi_server_multi_user.py` passes 5 consecutive complete executions.
- **W5C3-G18** Ubuntu full unit suite passes twice consecutively.
- **W5C3-G19** Windows exact target test PASS.
- **W5C3-G20** Windows full `test_fastapi_server_multi_user.py` PASS.
- **W5C3-G21** `git diff --check` PASS.
- **W5C3-G22** Adversarial diff review confirms test-only/narrow scope.

## Final Git state

- **W5C3-G23** Exactly one local C2 commit ahead of Distributed.
- **W5C3-G24** Final workspace clean.
- **W5C3-G25** Remote Distributed still equals `7f1ad1f02da9b1c4e3bf226f2a056066921ef77a`; no push occurred.

All 25 mandatory gates must PASS for:

`READY FOR ROOT REVIEW`

---

# 14. Evidence format

Each raw evidence file must begin with:

```text
Evidence-ID:
Gate(s):
Timestamp UTC:
Host:
Working Directory:
Command / Probe:
Expected:
Exit Code:
Result:
```

For repetition/stress runs, preserve enough raw output or machine-readable summaries to establish:

- number attempted;
- number passed;
- zero failures;
- exit status.

Do not replace raw proof with narrative claims only.

---

# 15. Final commit

After all validation:

1. review the complete diff;
2. ensure only intended tracked files/archive docs are staged;
3. create exactly one local correction commit on top of `7f1ad1f...`;
4. suggested commit message:

`AP-SRV-070 W5: stabilize outage WebSocket test`

5. record full commit SHA;
6. record tree SHA;
7. record direct parent;
8. verify exactly one commit ahead of Distributed;
9. verify workspace clean;
10. fetch origin;
11. verify remote Distributed remains exactly `7f1ad1f...`;
12. **DO NOT PUSH**.

No amend/rebase after evidence is bound to the final commit unless all commit/tree-bound evidence is regenerated.

---

# 16. Final report

`06_FINAL_REPORT.md` must begin exactly with either:

`READY FOR ROOT REVIEW`

or:

`NOT READY FOR ROOT REVIEW`

Do not claim Root PASS yourself.

Include:

- start commit/tree;
- GitHub run `34135266167` disposition;
- exact file(s) changed;
- statement whether any production source changed;
- semantic explanation of the second race;
- exact 100x isolated result;
- exact 5x testfile result;
- exact two Ubuntu full-suite results;
- Windows targeted/file results;
- `git diff --check`;
- final correction commit/tree/parent;
- exactly-one-commit-ahead proof;
- remote unchanged proof;
- workspace clean;
- zero public writes;
- explicit statement that W5-RC2 is **not yet frozen** and requires post-push GitHub Actions green on both platforms.

---

# 17. Stop conditions

STOP and report `NOT READY FOR ROOT REVIEW` if:

- Distributed changed before finalization;
- product source appears to require modification;
- the race cannot be fixed without weakening outage guarantees;
- `outage.not_committed` can appear as a committed event;
- canonical event identity cannot distinguish queued committed events from failed/uncommitted events;
- any of the 100 isolated Ubuntu runs fails;
- any of the 5 Ubuntu testfile runs fails;
- either Ubuntu full-suite run fails;
- Windows targeted regression fails;
- new unrelated blocker appears;
- secrets would need to be read;
- push/publication would be required.

---

# 18. Success state

C2 succeeds only when:

```text
pushed C1 commit 7f1ad1f...
→ real GitHub Windows CI PASS
→ real GitHub Ubuntu CI exposes one remaining race assertion
→ test-only semantic correction
→ no production behavior change
→ 100/100 isolated Ubuntu PASS
→ 5/5 Ubuntu surrounding-file PASS
→ 2/2 Ubuntu full suite PASS
→ Windows targeted/file PASS
→ exactly one local C2 commit
→ Distributed unchanged
→ READY FOR ROOT REVIEW
```

After external Root PASS:

```text
authorized exact C2 push
→ real GitHub Actions on exact C2 commit
→ Windows PASS
→ Ubuntu PASS
→ only then freeze that exact commit/tree as W5-RC2
→ run remaining frozen RC qualification
```
