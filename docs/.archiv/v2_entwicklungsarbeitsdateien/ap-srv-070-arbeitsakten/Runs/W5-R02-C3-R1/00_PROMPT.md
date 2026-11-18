# AP-SRV-070 / W5 — Root Review Correction
## W5-R02-C3-R1 — Canonical Event-Store Recovery Semantics
### Model: Opus 5

---

# 0. Purpose

W5-R02-C3 produced a strong root-cause analysis for the intermittent
`/ws/logs` test hang and prepared an unpushed local commit.

External Root Review does **not** accept C3 yet.

The blocker is narrower than the original hang:

> C3 proved that a successful `EventHub.query()` can change the shared
> canonical-store state from `degraded` to `ready` while the write path
> (`_store.append`) is still persistently failing. C3 treated that transition
> as legitimate product recovery, but the release contract does not yet prove
> that interpretation.

This correction must settle that semantic boundary first and then produce one
Root-PASS-capable final commit.

Do not merely make the tests deterministic.
Do not merely defend the C3 conclusion.
Re-evaluate the store recovery contract from authority + observable behaviour.

---

# 1. Run identity

- **Project:** AP-SRV-070
- **Phase:** W5 — Release Candidate Qualification
- **Run:** W5-R02-C3-R1
- **Model:** Anthropic Opus 5
- **Session:** CONTINUE EXISTING W5-R02-C3 OPUS SESSION
- **Repository:** `marcosudau-vps/voice-stt-server`
- **Local project/session start folder:** `P:\GithubRepos\marcosudau-vps\voice-stt-server`
- **Remote Distributed branch:** `feat/einheitliche-triggerarchitektur-distributed`
- **Binding remote start commit:** `7f1ad1f02da9b1c4e3bf226f2a056066921ef77a`
- **Binding remote start tree:** `9c51c365701357e3b35dece563b156fc611b2c6e`
- **Rejected/unpushed C3 reference commit:** `d60936c509d7b95e406c671fd3f91cc5f2af5add`
- **Rejected/unpushed C3 reference tree:** `71da4a1ab4d75844825c90a28c91644d18f01d3e`
- **C3 reference workspace, READ ONLY:** `P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-070-w5-r02-c3`
- **NEW correction workspace:** `P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-070-w5-r02-c3-r1`
- **Suggested local branch:** `work/ap-srv-070-w5-r02-c3-r1`
- **Prompt source:** `P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Prompts\2026-09-07_AP-SRV-070_W5_R02_C3_R1_OPUS5.md`
- **Run/evidence root:** `P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W5-R02-C3-R1\`
- **Version:** `2.0.0` — MUST remain unchanged

The final correction commit must be **one commit directly on the remote binding
commit `7f1ad1f...`**, not a second commit on top of the rejected C3 commit.

The C3 workspace/commit are reference material only and must not be pushed.

---

# 2. External Root Review finding

C3 correctly established several important facts:

1. The original combined test could reach its second `/ws/logs` connection
   with `store_available()==True`.
2. When that happened, the connection correctly entered the normal subscribe
   path and the test blocked because it never sent `subscribe`.
3. With a genuinely degraded precondition, the fast path
   `log.error(event_store_unavailable) -> close 1011` was stable in TestClient
   and in a real Uvicorn/WebSocket loopback probe.
4. The C3 test restructuring eliminated the intermittent hang under the
   requested stress campaigns.

Those findings remain useful.

However, C3 then made an additional claim that Root Review does not accept
without further proof:

> a successful canonical read is entitled to re-mark the whole canonical
> store `ready` even when canonical writes are still failing.

Current source behaviour at the binding commit is:

```python
# EventHub.emit
try:
    cursor = self._store.append(payload)
except Exception:
    self._set_store_state("degraded", ...)
    return None
...
self._set_store_state("ready")
```

and independently:

```python
# EventHub.query
try:
    result = self._store.query(...)
except Exception:
    self._set_store_state("degraded", ...)
    raise
self._set_store_state("ready")
return result
```

Therefore one successful read can erase the state produced by a persistent
write failure.

The public structured-logging contract says, in substance:

- SQLite is the canonical source for structured events;
- append/commit/cursor assignment happen before live delivery;
- if append fails, the attempted event receives no cursor and is not delivered
  as a normal committed event;
- when the canonical store is unavailable, live access is unavailable;
- `/ws/logs` sends `event_store_unavailable` and closes 1011 on store failure;
- live streams repeatedly rescan canonical SQLite rather than using an
  in-memory payload queue as authority.

The authority does **not** currently establish an operation-independent rule
that "any successful store operation means the whole store is recovered."

That semantic gap is the C3-R1 blocker.

---

# 3. Additional Root Review concern in the unpushed C3 test diff

The C3 ordering correction validates an intervening live event with:

```python
canonical = events.query(...)
```

But `events.query()` itself calls `_set_store_state("ready")` on success.

So the test that is exercising a write outage also performs a state-mutating
read that can clear the same degraded state.

Even if the existing product semantics are eventually judged intentional, a
test should not accidentally change the state under test merely to verify
canonical identity when a non-state-mutating proof is available.

C3-R1 must explicitly address this.

---

# 4. Required question

Before tracked edits, answer this:

> If `_store.append` is persistently failing but `_store.query` still succeeds,
> should `EventHub.store_available()` / canonical live-log availability be
> `ready` or `degraded`?

Do not answer from current implementation alone.

Use, in priority order:

1. current authoritative docs/contracts;
2. existing tests that encode intended recovery semantics;
3. architecture invariants;
4. observable end-to-end behaviour;
5. only then implementation details.

Distinguish:
- READ capability,
- WRITE/persistence capability,
- overall canonical-store/live-log availability.

---

# 5. Strong architectural invariant to test

This is a hypothesis to verify, not a command to blindly implement:

> Because every generated structured event must persist successfully before
> receiving a cursor or becoming a `log.event`, overall canonical live-log
> readiness should not claim recovery from a write failure until write
> capability has actually been demonstrated again.

A successful `SELECT` proves read capability.
It does not by itself prove that `INSERT/COMMIT` works.

If authority/evidence contradicts this hypothesis, document the contradiction
precisely.

---

# 6. Workspace / governance

Create a **new** worktree from exact remote Distributed:

`P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-070-w5-r02-c3-r1`

from:

`7f1ad1f02da9b1c4e3bf226f2a056066921ef77a`

Do not base the branch on `d60936c...`.

The rejected C3 workspace is read-only.

Before any tracked edit:

1. `git fetch origin`;
2. verify remote SHA/tree;
3. create correction workspace;
4. create run archive;
5. copy this prompt byte-identically;
6. read authorities and C3 evidence;
7. write `02_PLAN.md`;
8. capture empty `git status --porcelain` and `git diff`;
9. only then edit tracked files.

No edit/revert workaround is acceptable.

---

# 7. Secret boundary

The operator secret file remains:

`P:\GithubRepos\marcosudau-vps\voice-stt-server\secrets\voice-stt.env`

outside all worktrees.

This run does not need it.

Do not read, print, copy, hash, load, or archive it.

---

# 8. Evidence archive

Create:

`P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W5-R02-C3-R1\`

with:

```text
W5-R02-C3-R1\
├── 00_PROMPT.md
├── 01_CONTEXT.md
├── 02_PLAN.md
├── 03_SEMANTIC_AUTHORITY_REVIEW.md
├── 04_REPRODUCTION_REPORT.md
├── 05_IMPLEMENTATION_REPORT.md
├── 06_GATE_INDEX.md
├── 07_DEVIATIONS.md
├── 08_FINAL_REPORT.md
└── Evidence\
    ├── 00_Preflight\
    ├── 01_Authority\
    ├── 02_C3_Reference\
    ├── 03_Mixed_Capability_Reproduction\
    ├── 04_Recovery_Proof\
    ├── 05_Final_Diff\
    ├── 06_Ubuntu_Stress\
    ├── 07_Ubuntu_Full_Regression\
    ├── 08_Windows_Regression\
    └── 09_Final_Git_State\
```

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

---

# 9. Authority review — mandatory before implementation

Read at minimum:

- `AGENTS.md`
- relevant nested `AGENTS.md`
- `docs/.archiv/README.md`
- `docs/structured-logging.md`
- any current documentation that defines:
  - canonical SQLite authority,
  - live log availability,
  - health/store state,
  - store failure,
  - recovery semantics
- relevant existing unit tests around:
  - `StructuredEventHub`
  - store failure/recovery
  - history API
  - `/ws/logs`
- `VoiceSTT_server/event_logging.py`
- relevant `/ws/logs` and log-access/status code in
  `api_fastapi_server/server.py`
- C3:
  - `03_ROOT_CAUSE_REPORT.md`
  - `04_IMPLEMENTATION_REPORT.md`
  - full final diff
  - control-matrix evidence
  - state-flip trace
  - real network probe

Write `03_SEMANTIC_AUTHORITY_REVIEW.md`.

It must include a table:

| Question | Authority/evidence | Conclusion |
|---|---|---|
| What makes an event canonical? | ... | ... |
| What does `store_available()` represent? | ... | ... |
| What constitutes recovery from read failure? | ... | ... |
| What constitutes recovery from write failure? | ... | ... |
| May successful read clear persistent write failure? | ... | ... |
| What should `/ws/logs` advertise/do in mixed read-ok/write-broken state? | ... | ... |

Never call an implementation behaviour "documented" unless a current authority
actually states it.

---

# 10. Mixed-capability reproduction — mandatory

Before choosing the final fix, create an untracked diagnostic using the real
EventHub/store.

Establish this exact condition:

```text
READ:  works
WRITE: persistently fails
```

Do not merely toggle `_store_state` directly.

Use the same persistent write-failure mechanism as the existing tests where
appropriate, but keep it active for the whole observation window.

Then prove and record:

1. a generated event cannot be committed;
2. the attempted event gets no canonical cursor / is absent from canonical
   history;
3. `store_available()` immediately after the write failure;
4. a canonical `query()` succeeds;
5. `store_available()` immediately after that successful query;
6. a second generated event still cannot be committed;
7. state after that second write failure;
8. `/ws/logs` behaviour in the mixed-capability window;
9. any health/log-access response that exposes the same state, if applicable.

Run the diagnostic with both:
- in-process API/TestClient where useful;
- a real local Uvicorn/network probe for the user-visible `/ws/logs` contract.

This is not a stress test yet; it is semantic reproduction.

---

# 11. Decision branches

## Branch A — current behaviour is truly intended

Use only if current authority or a stronger existing architectural contract
unambiguously supports:

> a successful read is sufficient to mark the canonical store globally ready
> despite continuing write failure.

If so:

1. document that authority precisely;
2. preserve product source;
3. carry forward C3's test restructuring;
4. **remove state-mutating `events.query()` from the ordering assertion** unless
   you prove it cannot alter the semantic precondition being tested;
5. verify intervening committed-event identity through a non-state-mutating
   mechanism, for example:
   - snapshot of committed event IDs/cursors before inducing outage,
   - direct raw-store read specifically isolated from EventHub state mutation,
   - or another contract-safe approach;
6. add/retain a dedicated regression test that makes the intended mixed
   read-ok/write-broken semantics explicit so this is no longer accidental.

Do not select Branch A merely because that is what the current code happens to
do.

## Branch B — persistent write failure must remain degraded

Use if authority/invariants show that overall canonical-store/live-log
availability cannot be `ready` while writes still fail.

Implement the smallest robust state-model correction.

Requirements:

- a successful read may recover a **read failure**;
- it must not erase an unresolved **write failure**;
- successful write must provide real evidence that write capability recovered;
- avoid one "last operation won" bit if that cannot represent mixed capability;
- do not create a broad logging architecture redesign;
- preserve existing public API shapes unless a change is required for
  correctness;
- preserve SQLite-first semantics;
- preserve live/error/close contracts.

A small operation-aware state/capability model is acceptable if needed.

Do not hard-code special behaviour only for the test's monkeypatch.

## Branch C — semantics remain inconclusive

STOP:

`NOT READY FOR ROOT REVIEW`

Do not guess.

---

# 12. Carry forward valid C1/C2/C3 fixes

The final Root-PASS-capable commit must preserve all previously valid pieces:

## Windows C1
Kroko path tests compare semantic file identity.
No resolver regression.

## Manifest C1
Canonical `wheelSha256` integration and fail-closed compatibility remain.

These are already in binding `7f1ad1f...`; do not touch them.

## Ubuntu ordering C2/C3
Carry forward the correction for:

```text
already committed log.event(s)
→ log.error(event_store_unavailable)
→ close 1011
```

But revise the canonical-identity proof so it does not accidentally mutate the
state under test.

Required:
- bounded frame count;
- strictly increasing cursor;
- `outage.not_committed` forbidden;
- exact committed identity proof;
- unexpected frame fails;
- mandatory exact error code;
- mandatory 1011 close.

## Degraded new-connection coverage
Preserve explicit coverage of:

```text
store actually degraded
→ new /ws/logs connection
→ log.error(event_store_unavailable)
→ close 1011
```

Do not remove it.

If Branch B changes recovery semantics, this test may no longer need the C3
startup-thread workaround in the same shape; choose the least artificial test
that reflects real runtime.

---

# 13. Required targeted semantic tests

Regardless of final branch, add/adjust tests so these cases are explicit.

## T1 — write failure

```text
append fails
→ store reports degraded/unavailable as required by chosen authority
→ failed event not canonical
```

## T2 — successful read after write failure

Prove the intended state outcome explicitly.

This is the central regression test.

## T3 — second write while first write failure unresolved

```text
read may succeed
→ second append still fails
→ no false canonical delivery
```

## T4 — real write recovery

Restore write capability and perform a successful canonical append.

Prove the state transitions to the intended recovered state.

## T5 — read failure and read recovery

If the final implementation distinguishes read vs write health, prove that a
successful read can clear a read-side failure when no unresolved write failure
exists.

## T6 — mixed capability + `/ws/logs`

In the read-ok/write-broken state, verify the exact chosen public behaviour
from authority.

Use a real network probe at least once for the final semantics.

---

# 14. Stress validation

After final implementation:

## Ubuntu 24.04 / Python 3.12

1. ordering outage scenario:
   **100/100 PASS**
2. degraded-new-connection scenario:
   **100/100 PASS**
3. central mixed-capability/recovery regression:
   **100/100 PASS**
4. `tests/unit/test_fastapi_server_multi_user.py`:
   **10/10 complete PASS**
5. directly relevant EventHub/event-logging test file(s):
   **10/10 complete PASS**
6. full:
   `python -m pytest -q tests/unit`
   **2/2 complete PASS**

Zero hangs/failures in every mandatory campaign.

Use hard timeout protection for stress loops.

## Windows 11 / Python 3.12

Run:
- ordering scenario;
- degraded-new-connection scenario;
- mixed-capability/recovery targeted tests;
- full affected FastAPI multi-user file;
- relevant EventHub/event-logging test file(s).

All PASS.

The authoritative cross-platform matrix for the final commit will still be
GitHub Actions only after Root PASS + authorized push.

---

# 15. Real-network final probe

Run the real app under local Uvicorn and use an actual WebSocket client.

Exercise the final chosen mixed-capability semantics, not merely a forced
`_store_state`.

The probe must establish the underlying read/write capability condition through
real EventHub/store operations and verify the externally visible `/ws/logs`
behaviour.

At least **50 consecutive PASS** if inexpensive.

No new runtime/project dependency solely for the probe.

---

# 16. Diff / scope

If Branch A:
preferred tracked diff remains test-only.

If Branch B:
allowed tracked scope is limited to:
- `VoiceSTT_server/event_logging.py`
- directly relevant tests
- current documentation only if semantics need clarification

Do not change:
- protocol-v2
- activation
- trigger
- wake word
- model management
- Kroko runtime
- packaging
- release tooling
- Docker
- GitHub Actions
- dependencies
- VERSION

unless a new reproducible blocker strictly requires it; otherwise STOP.

Run:
`git diff --check`

Archive exact full diff and an adversarial scope review.

---

# 17. Required documentation update if Branch B

If product semantics change from the current implementation, update current
structured-logging documentation narrowly to state:

- what "store available/ready" means;
- read vs write failure/recovery behaviour;
- live-log behaviour when canonical writes are unavailable.

Do not rewrite historical archive documents.

---

# 18. Gates

Use exactly these IDs in `06_GATE_INDEX.md`.

## Governance

- **W5C5-G01** Remote Distributed start exactly `7f1ad1f02da9b1c4e3bf226f2a056066921ef77a`.
- **W5C5-G02** Start tree exactly `9c51c365701357e3b35dece563b156fc611b2c6e`.
- **W5C5-G03** New clean R1 workspace directly from binding commit.
- **W5C5-G04** Plan exists before first tracked edit, with literal clean proof.
- **W5C5-G05** Rejected C3 workspace remains read-only/unmodified.
- **W5C5-G06** VERSION remains exactly `2.0.0`.
- **W5C5-G07** No push/tag/release/publication.

## Authority / semantics

- **W5C5-G08** Current structured-logging authority reviewed and quoted/paraphrased accurately.
- **W5C5-G09** Existing tests for store failure/recovery semantics inventoried.
- **W5C5-G10** Read capability, write capability, and global/live availability explicitly distinguished.
- **W5C5-G11** Mixed read-ok/write-broken state reproduced from real operations.
- **W5C5-G12** First failed append proven non-canonical.
- **W5C5-G13** Successful read-after-write-failure state transition measured.
- **W5C5-G14** Persistent second write failure measured after the successful read.
- **W5C5-G15** User-visible `/ws/logs` behaviour in mixed capability measured with real network.
- **W5C5-G16** Final semantic decision Branch A or B supported by authority/evidence, not implementation circularity.

## Implementation correctness

- **W5C5-G17** Valid C2/C3 ordering fix carried forward without state-mutating canonical verification.
- **W5C5-G18** Intervening committed events retain strict cursor/identity proof.
- **W5C5-G19** `outage.not_committed` cannot be accepted/delivered as canonical.
- **W5C5-G20** `log.error(event_store_unavailable)` and close 1011 contract preserved where store is unavailable.
- **W5C5-G21** Successful read-after-write-failure behaviour has a direct regression test.
- **W5C5-G22** Successful real write recovery has a direct regression test.
- **W5C5-G23** Read-failure/read-recovery behaviour remains correct and directly tested.
- **W5C5-G24** No arbitrary sleeps/blind retries/timeout masking.
- **W5C5-G25** Scope is minimal for selected branch.

## Validation

- **W5C5-G26** Ubuntu ordering scenario 100/100 PASS.
- **W5C5-G27** Ubuntu degraded-new-connection scenario 100/100 PASS.
- **W5C5-G28** Ubuntu mixed-capability/recovery scenario 100/100 PASS.
- **W5C5-G29** Ubuntu affected FastAPI file 10/10 PASS.
- **W5C5-G30** Ubuntu relevant EventHub/event-logging file(s) 10/10 PASS.
- **W5C5-G31** Ubuntu full suite 2/2 PASS.
- **W5C5-G32** Windows targeted + affected files PASS.
- **W5C5-G33** Final real-network mixed-capability probe >=50 consecutive PASS.
- **W5C5-G34** `git diff --check` PASS.
- **W5C5-G35** Exact full diff archived; adversarial scope review PASS.

## Final Git

- **W5C5-G36** Exactly one local final commit directly on `7f1ad1f...`.
- **W5C5-G37** Final workspace literally clean.
- **W5C5-G38** Remote Distributed still exactly `7f1ad1f...`; no push.
- **W5C5-G39** Final commit/tree/parent identities recorded and consistent.

All 39 mandatory gates must PASS for:

`READY FOR ROOT REVIEW`

No mandatory success gate may be marked N/A.

---

# 19. Final commit

Only after all gates pass.

Exactly one local commit directly on:

`7f1ad1f02da9b1c4e3bf226f2a056066921ef77a`

Suggested message if Branch A:

`AP-SRV-070 W5: stabilize canonical log-store qualification`

Suggested message if Branch B:

`AP-SRV-070 W5: correct canonical log-store recovery semantics`

Record:
- full commit SHA;
- tree SHA;
- direct parent;
- files changed;
- exact commits ahead;
- clean status;
- remote unchanged.

DO NOT PUSH.

The old C3 local commit `d60936c...` remains rejected/unpublished reference
material and must not be merged/cherry-picked as an extra durable commit.

---

# 20. Final report

`08_FINAL_REPORT.md` begins exactly:

`READY FOR ROOT REVIEW`

or:

`NOT READY FOR ROOT REVIEW`

Include:

- selected semantic branch A/B/C;
- authority basis;
- mixed-capability reproduction;
- exact before/after state semantics;
- final tracked files;
- production source changed yes/no and why;
- ordering correction proof;
- 100x/10x/2x validation summaries;
- real-network final probe;
- VERSION;
- final commit/tree/parent;
- exactly-one-commit-ahead;
- remote unchanged;
- clean workspace;
- no public writes;
- explicit statement that W5-RC2 is still **not frozen** until external Root
  PASS, exact authorized push, and green GitHub Actions on both Windows and
  Ubuntu.

---

# 21. Stop conditions

STOP with `NOT READY FOR ROOT REVIEW` if:

- semantic authority remains genuinely ambiguous after the required review;
- mixed read-ok/write-broken state cannot be reproduced;
- product claims ready while writes fail and no narrow correct state model can
  be implemented;
- final fix requires broad logging redesign;
- canonical SQLite-first guarantees would be weakened;
- failed events could be exposed as committed;
- any mandatory stress campaign fails/hangs;
- either Ubuntu full suite fails;
- Windows targeted regressions fail;
- real-network final probe fails;
- plan-before-edit is violated;
- rejected C3 workspace is modified;
- secrets would need to be consumed;
- Distributed changes unexpectedly.

---

# 22. Success chain

```text
remote binding 7f1ad1f...
→ authority review
→ reproduce read-ok / write-broken state
→ decide recovery semantics from contract, not current code
→ carry forward valid C2/C3 ordering correction without mutating state under test
→ if necessary, narrow operation-aware store-health fix
→ targeted semantic recovery tests
→ 100/100 + 100/100 + 100/100 Ubuntu stress
→ affected files 10/10
→ Ubuntu full suite 2/2
→ Windows targeted PASS
→ real-network final mixed-capability probe >=50/50
→ exactly one local commit on 7f1ad1f...
→ clean workspace
→ remote unchanged
→ READY FOR ROOT REVIEW
```

Only after external Root PASS:

```text
authorize exact final commit push
→ verify exact remote SHA/tree/parent
→ GitHub Actions exact commit
→ Windows PASS + Ubuntu PASS
→ freeze exact commit/tree as W5-RC2
→ resume remaining frozen RC qualification
```
