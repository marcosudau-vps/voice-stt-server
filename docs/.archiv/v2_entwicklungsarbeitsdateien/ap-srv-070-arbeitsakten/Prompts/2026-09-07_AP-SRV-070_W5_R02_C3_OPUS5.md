# AP-SRV-070 / W5 — CI-Stability Correction
## W5-R02-C3 — Degraded WebSocket Connection Hang Root Cause + Final Test Stabilization
### Model: Opus 5

---

# 0. Run identity

- **Project:** AP-SRV-070
- **Phase:** W5 — Release Candidate Qualification
- **Parent runs:** W5-R02 → W5-R02-C1 → W5-R02-C2
- **Correction run:** W5-R02-C3
- **Model:** Anthropic Opus 5
- **Session:** NEW SESSION
- **Reason for fresh session:** independent concurrency/root-cause analysis; do not inherit the prior Agent's TestClient hypothesis as a conclusion
- **Repository:** `marcosudau-vps/voice-stt-server`
- **Local project/session start folder:** `P:\GithubRepos\marcosudau-vps\voice-stt-server`
- **Distributed branch:** `feat/einheitliche-triggerarchitektur-distributed`
- **Binding start commit:** `7f1ad1f02da9b1c4e3bf226f2a056066921ef77a`
- **Binding start tree:** `9c51c365701357e3b35dece563b156fc611b2c6e`
- **Product version:** `2.0.0` — MUST remain unchanged
- **NEW workspace:** `P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-070-w5-r02-c3`
- **Existing C2 workspace, READ-ONLY reference only:** `P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-070-w5-r02-c2`
- **Prompt source:** `P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Prompts\2026-09-07_AP-SRV-070_W5_R02_C3_OPUS5.md`
- **Run/evidence root:** `P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W5-R02-C3\`
- **C2 evidence root:** `P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W5-R02-C2\`

This is a **root-cause-first correction run**.

Do not assume the newly found hang is a product bug.
Do not assume it is a Starlette/TestClient bug.
Prove the boundary first.

---

# 1. Current state

W5-R02-C1 was Root-approved and pushed as:

`7f1ad1f02da9b1c4e3bf226f2a056066921ef77a`

Real GitHub Actions run:

`34135266167`

on that exact commit produced:

- Windows: **PASS**
- Ubuntu 24.04: one failure in
  `test_store_outage_closes_live_stream_and_recovery_allows_new_stream`

The GitHub failure was:

```text
expected: log.error
actual:   log.event
```

after a deliberate canonical event-store outage.

W5-R02-C2 implemented a narrow **test-only** correction for that specific ordering assumption:

```text
zero or more already-committed log.event
→ mandatory log.error(event_store_unavailable)
→ mandatory close 1011
```

with:

- bounded receive loop;
- strict cursor monotonicity;
- canonical-store verification of intervening events;
- explicit rejection of `outage.not_committed`;
- unexpected-frame failure.

That C2 correction was not committed because C2's mandatory stress campaign found a separate intermittent hang.

---

# 2. Binding C2 finding

## 2.1 Observed hang

On Ubuntu 24.04 / Python 3.12, after the C2 ordering fix:

- isolated target test: **96/100 PASS, 4/100 timeout/hang**
- full test file: **4/5 PASS, 1/5 timeout/hang**
- full unit suite: **2/2 PASS**
  - each: `1708 passed, 14 skipped, 985 subtests, 0 failed`
- Windows:
  - target PASS
  - full affected file PASS

The intermittent hang occurs downstream of the C2 ordering fix at the block:

```python
with client.websocket_connect("/ws/logs") as unavailable:
    error = unavailable.receive_json()
```

while the canonical event store is already in `degraded` state.

## 2.2 Baseline comparison

The same target test was run 100 times from a fresh, unmodified copy of the binding C1 commit:

`7f1ad1f02da9b1c4e3bf226f2a056066921ef77a`

Result:

**94/100 PASS, 6/100 timeout/hang**

Therefore the hang clearly **predates the uncommitted C2 ordering correction**.

This proves C2 did not introduce it.

It does **not by itself prove** whether the pre-existing problem is:

- production behavior,
- Starlette/TestClient/AnyIO lifecycle behavior,
- test construction,
- or an interaction between them.

C3 must determine that.

## 2.3 Faulthandler evidence

A captured hang showed:

Main test thread blocked in approximately:

```text
starlette.testclient.WebSocketTestSession.receive_json
→ receive
→ anyio.from_thread.BlockingPortal.call
→ Future.result
```

at the second `/ws/logs` connection.

The ASGI event-loop thread was idle in `select()`.
Structured-event worker threads were idle waiting on queues.
No `/ws/logs` application-handler frame was visible in the captured stack.

This strongly suggests a test-harness/lifecycle issue, but is **evidence, not yet a final root cause**.

---

# 3. Relevant production contract

At binding commit `7f1ad1f...`, the `/ws/logs` handler's already-degraded fast path is conceptually:

```python
await websocket.accept()

if not service.events.store_available():
    await websocket.send_text({
        "type": "log.error",
        "code": "event_store_unavailable",
        ...
    })
    await websocket.close(code=1011)
    return
```

This path is intentionally simple and should remain unchanged unless C3 proves it misbehaves outside TestClient.

The product contract to preserve is:

> A new `/ws/logs` connection while the canonical store is unavailable/degraded must receive `log.error` with code `event_store_unavailable`, then close with WebSocket code `1011`, without hanging.

---

# 4. Important Root Review corrections to the C2 bookkeeping

Do not copy C2's gate accounting blindly.

The coordinator determined:

1. C2's plan gate was **not actually PASS**:
   - the first tracked edit occurred before the plan;
   - reverting and re-applying later did not change that historical fact.
2. C2's "exactly one local commit" gate was **not N/A**:
   - it was simply not met because no commit was created.
3. C2's final-workspace-clean gate was **not PASS**:
   - `git status --porcelain` contained the intended uncommitted test modification.

These points do not change C2's correct overall `NOT READY FOR ROOT REVIEW`, but C3 must use literal gate semantics.

For C3:

**Plan must exist before the very first tracked edit. No edit/revert workaround is accepted.**

---

# 5. C3 objectives

C3 has two deliverables.

## Objective A — Root-cause the intermittent second-connection hang

Determine with evidence whether the hang is:

### A1. Production defect

The real `/ws/logs` degraded fast path can itself hang or fail to send/close.

### A2. TestClient / AnyIO / in-process harness lifecycle issue

Production behavior is correct, but the same `TestClient` with sequential WebSocket sessions can intermittently lose/stall the second WebSocket interaction.

### A3. Test-structure defect

The test combines too many lifecycle scenarios into one TestClient/websocket sequence and thereby creates an artificial synchronization hazard.

### A4. Other

If evidence points elsewhere, document it precisely.

## Objective B — Produce one final narrow correction commit

The final commit must include:

1. the already-validated C2 ordering correction for legitimate committed `log.event` frames before `log.error`; and
2. the minimal correction needed to eliminate the newly discovered intermittent hang while preserving the production contract.

No unrelated source work.

---

# 6. Strong preference / protected areas

Protected unless independently proven defective:

- `VoiceSTT_server/event_logging.py`
- `/ws/logs` production handler in `api_fastapi_server/server.py`
- event-store state machine
- protocol-v2 behavior
- scheduler
- model management
- Kroko
- release tooling
- packaging
- Docker
- CI workflow
- dependency versions

Do **not** "fix" this by:

- adding arbitrary `sleep()`;
- increasing timeouts;
- blindly retrying `receive_json()`;
- swallowing a timeout and marking PASS;
- changing WebSocket close/error semantics;
- weakening assertions;
- globally serializing unrelated event delivery;
- changing FastAPI/Starlette/AnyIO/httpx versions merely on suspicion;
- adding a broad concurrency refactor.

If a dependency bug is proven, prefer restructuring the test around the stable public behavior over introducing a release-wide dependency change, unless no reasonable stable test boundary exists.

---

# 7. Session/workspace governance

## 7.1 NEW SESSION

Use a new Opus 5 session.

Reason:
C2 already formed a hypothesis that this is TestClient/AnyIO related.
C3 must independently test that hypothesis rather than merely confirm it.

## 7.2 NEW workspace

Create:

`P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-070-w5-r02-c3`

from exact Distributed commit:

`7f1ad1f02da9b1c4e3bf226f2a056066921ef77a`

Suggested local branch:

`work/ap-srv-070-w5-r02-c3`

The C2 workspace is READ-ONLY reference material.
Do not continue editing it.
Do not commit from it.

## 7.3 No push before external Root PASS

C3 ends with exactly one local correction commit if successful.

Do not push.

No:

- amend after evidence binding;
- rebase;
- merge;
- force-push;
- tag;
- GitHub Release;
- PyPI;
- GHCR;
- Docker Hub;
- canonical branch;
- main.

---

# 8. Secret boundary

The operator secret file is:

`P:\GithubRepos\marcosudau-vps\voice-stt-server\secrets\voice-stt.env`

It lies outside the Git worktrees.

C3 does not need it.

Do not:

- read it;
- print it;
- copy it;
- hash its contents;
- load it;
- mention secret values in Evidence.

---

# 9. Run archive

Create before any tracked edit:

`P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W5-R02-C3\`

with:

```text
W5-R02-C3\
├── 00_PROMPT.md
├── 01_CONTEXT.md
├── 02_PLAN.md
├── 03_ROOT_CAUSE_REPORT.md
├── 04_IMPLEMENTATION_REPORT.md
├── 05_GATE_INDEX.md
├── 06_DEVIATIONS.md
├── 07_FINAL_REPORT.md
└── Evidence\
    ├── 00_Preflight\
    ├── 01_C2_Evidence_Review\
    ├── 02_Baseline_Reproduction\
    ├── 03_Harness_Control_Matrix\
    ├── 04_Real_ASGI_Network_Probe\
    ├── 05_Final_Diff\
    ├── 06_Ubuntu_Stress\
    ├── 07_Ubuntu_Full_Regression\
    ├── 08_Windows_Regression\
    └── 09_Final_Git_State\
```

Copy this prompt byte-identically to `00_PROMPT.md`.
Record prompt source/copy SHA256.

---

# 10. Plan-before-edit rule

Before touching any tracked repository file:

1. fetch origin;
2. create new worktree;
3. verify exact start SHA/tree;
4. read authorities/source/C2 evidence;
5. write `02_PLAN.md`;
6. only then begin tracked edits.

Diagnostic scripts placed under the external Run/Evidence directory are allowed before product/test edits because they are not tracked repository changes.

Do not perform any temporary tracked edit before the plan.

---

# 11. Preflight

Require:

```text
origin/feat/einheitliche-triggerarchitektur-distributed
= 7f1ad1f02da9b1c4e3bf226f2a056066921ef77a

HEAD
= 7f1ad1f02da9b1c4e3bf226f2a056066921ef77a

TREE
= 9c51c365701357e3b35dece563b156fc611b2c6e

workspace
= clean
```

Record:

- `git fetch origin`
- HEAD
- tree
- parent
- branch
- `git status --porcelain`
- `git worktree list`
- Python versions
- Windows version
- Ubuntu 24.04 version
- installed FastAPI / Starlette / AnyIO / httpx versions in the actual Ubuntu test environment

Do not change dependency versions during diagnostics.

---

# 12. Read binding material

At minimum read:

- `AGENTS.md`
- relevant nested `AGENTS.md`
- `docs/.archiv/README.md`
- C2:
  - `02_PLAN.md`
  - `03_CORRECTION_REPORT.md`
  - `04_GATE_INDEX.md`
  - `05_DEVIATIONS.md`
  - `06_FINAL_REPORT.md`
  - all Evidence under `03_Ubuntu_Isolated_Repetition`
- current:
  - `tests/unit/test_fastapi_server_multi_user.py`
  - `api_fastapi_server/server.py` `/ws/logs`
  - `VoiceSTT_server/event_logging.py`
  - relevant TestClient/application setup helpers

Also inspect the uncommitted C2 diff from the old C2 workspace **read-only**:

```text
P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-070-w5-r02-c2
```

Record the exact C2 diff in C3 Evidence before reproducing it later.

Do not modify C2 workspace.

---

# 13. Root-cause control matrix — before final implementation

The purpose is not to run arbitrary experiments.
Each control must distinguish a concrete hypothesis.

## Control 1 — Baseline combined test

From clean binding source, reproduce the existing C1-style target test enough to confirm the known intermittent hang.

Use hard per-process timeout and faulthandler.

Because C2 already provides 100-run evidence, **30–50 fresh runs are sufficient here** if the hang reproduces.

If no hang reproduces, do not conclude it vanished; retain C2 evidence as binding history and continue controls.

## Control 2 — Isolated degraded-connection scenario

Create a temporary diagnostic test/script outside tracked source that:

1. creates the real VoiceSTT app;
2. enters a TestClient lifecycle;
3. puts the real canonical event hub into degraded state through the same failure mechanism;
4. opens **only one** `/ws/logs` websocket in the already-degraded state;
5. expects:
   - `log.error`
   - `code=event_store_unavailable`
   - close 1011.

Run this repeatedly, target **100/100**.

This distinguishes:
"degraded fast path itself is unstable"
from:
"back-to-back WebSocket lifecycle is unstable".

## Control 3 — Sequential WebSockets without store outage

Using the same real app/TestClient, repeatedly exercise two sequential `/ws/logs` websocket connections without the degraded transition.

Design the temporary diagnostic so each connection has a complete legitimate lifecycle.

This tests whether sequential TestClient websocket sessions alone can trigger the stall.

Use enough repetitions to detect the observed ~4–6% failure rate; target 100 attempts if inexpensive.

## Control 4 — Split lifecycle using fresh TestClient context

Exercise the degraded-connection scenario using a fresh TestClient/application lifecycle boundary rather than immediately after the first websocket session.

The product state required for the degraded scenario must still be established legitimately.

Target 100/100 if inexpensive.

## Control 5 — Non-TestClient / real ASGI network probe

This is highly important before blaming production.

Using only already-available dependencies, create an **external diagnostic script under Evidence**, not repository source, that runs the real app through an actual local loopback ASGI server (for example Uvicorn on an ephemeral localhost port) and connects with an actual WebSocket client.

Establish degraded event-store state in the same process/app instance, then open `/ws/logs`.

Verify:

```text
connect
→ log.error(event_store_unavailable)
→ close 1011
```

Run enough repetitions to establish reliability; target at least **30 consecutive PASS**, preferably 50 if inexpensive.

Do not add a new project dependency just for this probe.

If a real-network probe cannot be executed with existing dependencies, document exactly why and provide the strongest alternative ASGI-level control available.

---

# 14. Root-cause decision

Write `03_ROOT_CAUSE_REPORT.md` before finalizing the implementation.

It must compare all controls in a table:

| Control | Same TestClient? | Sequential sockets? | Store degraded? | Real network? | Attempts | Hangs | Result |
|---|---:|---:|---:|---:|---:|---:|---|

Then state one of:

## RC-A — Harness/test-structure confirmed

Use this only if:

- isolated real degraded fast path is stable;
- real-network probe is stable;
- the intermittent hang is tied to the combined/sequential in-process TestClient lifecycle.

Then a test-only restructuring is appropriate.

## RC-B — Product defect confirmed

Use this only if the degraded behavior itself reproducibly hangs/fails outside TestClient or through the real-network probe.

Then production code is implicated.

Before editing production code, document:
- exact reproducible product failure;
- violated contract;
- minimal intended production fix.

A narrow product fix is allowed in C3 only if it remains localized to the event-store/WebSocket fast path and requires no architecture redesign.

If broader redesign is required: STOP.

## RC-C — Inconclusive

If controls do not establish the boundary:
STOP and report `NOT READY FOR ROOT REVIEW`.
Do not guess.

---

# 15. Carry forward the validated C2 ordering correction

C2 never created a commit, so its correct ordering fix must not be lost.

After the C3 plan exists, reproduce the C2 ordering correction in the new C3 workspace.

Required semantics:

After deliberate store failure on the existing live logs socket:

```text
zero or more legitimate already-committed log.event
→ mandatory log.error(event_store_unavailable)
→ mandatory close 1011
```

For each intervening event:

- cursor strictly monotonic;
- canonical-store identity verified;
- `outage.not_committed` forbidden;
- unexpected frame type fails;
- bounded receive count;
- mandatory error cannot be skipped.

Do not blindly copy text if inspection finds a correctness problem.
If you alter the C2 shape, explain why.

Capture the exact resulting diff.

---

# 16. Preferred implementation if RC-A is proven

If harness/test-structure is confirmed, prefer **separating independent lifecycle contracts** rather than adding sleeps/retries.

A likely good shape is:

## Test A — live stream outage + committed-event drain + close + recovery

Keep the existing test focused on:

- subscribed live stream;
- store failure;
- already-committed live event drain;
- mandatory `log.error`;
- close 1011;
- restore store;
- recovery/replay.

## Test B — new connection while store is already degraded

Create a separate focused test with its own clean app/TestClient lifecycle:

1. create app/client;
2. force canonical store into degraded state using the same real failure mechanism;
3. open one `/ws/logs` connection;
4. assert:
   - `log.error`
   - `event_store_unavailable`
   - close 1011;
5. no indefinite receive.

This should preserve the product contract while avoiding an artificial dependency on back-to-back TestClient WebSocket lifecycle.

Do not remove coverage.
Do not merely skip the second-connection contract.

If a different test-only structure is better supported by the control matrix, use it and explain.

---

# 17. Implementation scope

Preferred successful RC-A scope:

`tests/unit/test_fastapi_server_multi_user.py`

only.

Potential small local helper inside that same test module/class is allowed.

No production edit under RC-A.

Under proven RC-B:
a narrow production edit plus directly relevant tests is allowed, but nothing broader.

No workflow/dependency/version changes unless separately proven unavoidable.

---

# 18. Mandatory post-fix validation

## 18.1 Ubuntu — C2 ordering scenario

The corrected live-outage/order scenario must pass:

**100 consecutive runs**

with hard timeout protection.
Zero hangs.
Zero failures.

## 18.2 Ubuntu — degraded-new-connection scenario

The focused degraded-new-connection test must pass:

**100 consecutive runs**

with hard timeout protection.
Zero hangs.
Zero failures.

## 18.3 Ubuntu — affected file stress

Run:

`tests/unit/test_fastapi_server_multi_user.py`

**10 consecutive complete executions**

All 10 PASS.
No timeout.
No hang.

## 18.4 Ubuntu full regression

Run:

`python -m pytest -q tests/unit`

**2 consecutive full executions**

Both PASS.
Zero failures.

Explain count change from C1 baseline if a test is split/added.

## 18.5 Windows regression

On Windows 11 / Python 3.12 run:

- C2 ordering scenario once;
- degraded-new-connection scenario once;
- full `test_fastapi_server_multi_user.py` once.

All PASS.

The authoritative new-commit Windows/Ubuntu matrix will still be real GitHub Actions after Root PASS + push.

## 18.6 Static/diff

- `git diff --check` PASS.
- exact full `git diff` stored in Evidence.
- adversarial scope review.
- no production change if RC-A.
- no dependency/workflow/version changes.

---

# 19. C3 gates

Use exactly these IDs.

## Identity / governance

- **W5C4-G01** Remote Distributed exactly `7f1ad1f02da9b1c4e3bf226f2a056066921ef77a`.
- **W5C4-G02** Start tree exactly `9c51c365701357e3b35dece563b156fc611b2c6e`.
- **W5C4-G03** New C3 worktree created clean from binding commit.
- **W5C4-G04** `02_PLAN.md` existed before the first tracked edit, with no prior edit/revert exception.
- **W5C4-G05** VERSION remains `2.0.0`.
- **W5C4-G06** No push/tag/publication.

## Root-cause evidence

- **W5C4-G07** C2 hang evidence independently reviewed and accurately represented.
- **W5C4-G08** Baseline combined-test behavior characterized with bounded/fault-handler diagnostics.
- **W5C4-G09** Isolated already-degraded single-connection TestClient control executed repeatedly.
- **W5C4-G10** Sequential-socket non-degraded control executed repeatedly.
- **W5C4-G11** Fresh-TestClient/lifecycle degraded control executed repeatedly.
- **W5C4-G12** Real local ASGI/network degraded-connection probe executed successfully, or strongest justified non-TestClient alternative.
- **W5C4-G13** Root cause classified RC-A or RC-B with evidence; not speculation.

## Correctness / implementation

- **W5C4-G14** Validated C2 committed-event-before-error semantics carried forward.
- **W5C4-G15** `outage.not_committed` can never be accepted as committed.
- **W5C4-G16** Mandatory `log.error(event_store_unavailable)` preserved.
- **W5C4-G17** Mandatory close 1011 preserved.
- **W5C4-G18** New degraded-connection contract remains explicitly covered.
- **W5C4-G19** No sleeps/blind retries/assertion weakening.
- **W5C4-G20** Production source unchanged if RC-A; if RC-B, any production diff is strictly evidence-justified and localized.

## Stress / regression

- **W5C4-G21** Ubuntu C2 ordering scenario 100/100 PASS.
- **W5C4-G22** Ubuntu degraded-new-connection scenario 100/100 PASS.
- **W5C4-G23** Ubuntu affected file 10/10 complete PASS.
- **W5C4-G24** Ubuntu full suite 2/2 PASS.
- **W5C4-G25** Windows targeted scenarios PASS.
- **W5C4-G26** Windows affected file PASS.
- **W5C4-G27** `git diff --check` PASS.
- **W5C4-G28** Exact full diff archived and adversarial scope review PASS.

## Final Git

- **W5C4-G29** Exactly one local final C3 commit directly on `7f1ad1f...`.
- **W5C4-G30** Final workspace genuinely clean (`git status --porcelain` empty).
- **W5C4-G31** Remote Distributed still exactly `7f1ad1f...`; no push.
- **W5C4-G32** Final commit/tree/parent identities recorded and internally consistent.

All 32 mandatory gates must PASS for:

`READY FOR ROOT REVIEW`

No N/A for mandatory success-path gates.

---

# 20. Evidence format

Every raw evidence file begins with:

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

For stress loops preserve machine-readable/raw summaries proving exact attempt counts.

For timeout/hang diagnostics preserve faulthandler stacks.

For root-cause controls, record exact environment/package versions.

---

# 21. Documentation/reporting

## `03_ROOT_CAUSE_REPORT.md`

Must distinguish:

- observed fact;
- evidence-supported inference;
- proven conclusion.

Do not use "conclusive" for claims not directly established.

## `04_IMPLEMENTATION_REPORT.md`

Soll/Ist:

- planned files;
- actual files;
- why each changed;
- C2 carry-forward;
- hang fix;
- no-go areas untouched.

## `06_DEVIATIONS.md`

If none:

`Keine bekannten W5-R02-C3-Abweichungen.`

If diagnostics reveal an unexpected condition, document it.

## `07_FINAL_REPORT.md`

Must begin exactly:

`READY FOR ROOT REVIEW`

or:

`NOT READY FOR ROOT REVIEW`

Never claim Root PASS.

---

# 22. Final commit

Only after every validation gate passes:

Create exactly one local commit.

Suggested message:

`AP-SRV-070 W5: stabilize degraded log WebSocket qualification`

Required:

- direct parent =
  `7f1ad1f02da9b1c4e3bf226f2a056066921ef77a`
- VERSION = `2.0.0`
- exact commit SHA recorded
- exact tree SHA recorded
- workspace clean
- exactly one commit ahead
- remote unchanged
- DO NOT PUSH.

If any mandatory gate fails:
do not create a success-path final commit.

---

# 23. Stop conditions

STOP with `NOT READY FOR ROOT REVIEW` if:

- root cause remains inconclusive;
- real-network degraded fast path hangs/fails and a narrow product fix cannot be proven;
- fix requires architecture redesign;
- fix requires weakening error/close semantics;
- any 100x stress campaign has a failure/hang;
- any of the 10 affected-file runs fails/hangs;
- either Ubuntu full suite fails;
- Windows regression fails;
- dependency upgrade becomes the only apparent "fix" without proof;
- plan-before-first-edit is violated;
- secrets would need to be consumed;
- Distributed changes unexpectedly.

---

# 24. Success chain

```text
Distributed 7f1ad1f...
→ fresh Opus root-cause analysis
→ determine product vs TestClient/test-structure boundary
→ carry forward valid C2 ordering fix
→ minimally resolve degraded-second-connection hang
→ 100/100 ordering scenario
→ 100/100 degraded-connection scenario
→ 10/10 affected-file runs
→ 2/2 Ubuntu full suite
→ Windows targeted/file PASS
→ exactly one local commit
→ clean workspace
→ no push
→ READY FOR ROOT REVIEW
```

After external Root PASS:

```text
exact authorized C3 commit push
→ real GitHub Actions on exact commit
→ Windows PASS
→ Ubuntu PASS
→ freeze exact commit/tree as W5-RC2
→ resume remaining W5 frozen-RC qualification
```
