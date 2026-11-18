# AP-SRV-070 / W5 — Narrow Correction Run
## W5-R01-C1 — Complete and qualify real publication execution paths
### Model: Sonnet 5

---

# 0. Run identity

- **Project:** AP-SRV-070
- **Phase:** W5 — Release Candidate Qualification
- **Parent Run:** W5-R01
- **Correction Run:** W5-R01-C1
- **Model:** Anthropic Sonnet 5
- **Session:** CONTINUE EXISTING W5-R01 SESSION
- **Existing workspace:** `P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-070-w5-r01`
- **Existing W5-R01 run file:** `P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W5-R01`
- **New correction run file:** `P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W5-R01-C1`
- **Prompt source:** `P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Prompts\2026-09-06_AP-SRV-070_W5_R01_C1_SONNET5.md`
- **Distributed branch:** `feat/einheitliche-triggerarchitektur-distributed`
- **Distributed must remain unchanged during this run at:** `e5f76bf1e4fd28e68624f30140fcf8ec6876db96`

This is a **narrow correction run**, not a new W5 implementation run.

Its only substantive purpose is to close the W5-R01 Root Review blocker:

> The real publication execution paths for PyPI, GHCR, Docker Hub, external verification, Git tag and GitHub Release must already exist in W5 and be fully testable/simulatable before W5-R02 freezes the RC. W6 must execute already-qualified release logic, not implement new critical publication behavior after RC qualification.

No public release is allowed in this run.

---

# 1. Root Review disposition from W5-R01

The coordinator made two findings.

## 1.1 Blocking finding — MUST FIX

Current `release.py publish` is intentionally a non-implemented stub and exits without real publication execution logic.

This is a Root blocker because W5 must qualify the actual release engine before W6.

This correction run must implement the real execution paths while keeping every test and dry-run fully non-public.

## 1.2 Historical process finding — ALREADY WAIVED

W5P-G03 ("archive plan before implementation") was violated in W5-R01.

The coordinator explicitly accepts this as:

`AW-01 — Coordinator Waiver`

Do **not** rewrite history.
Do **not** fake an earlier plan timestamp.
Do **not** attempt to make W5P-G03 retrospectively PASS.

Record AW-01 in the correction report as an accepted historical process deviation with no remaining product/release blocker.

---

# 2. Critical governance

## 2.1 No public writes

This run must perform **zero** real publication writes.

Forbidden:

- PyPI upload;
- GHCR push;
- Docker Hub push;
- mutable or immutable registry tag changes;
- Git tag creation;
- Git tag push;
- GitHub Release creation;
- release branch publication;
- any other external release mutation.

Real remote read-only checks are allowed only where already part of safe preflight behavior and only if they do not expose secrets.

## 2.2 No push before external Root PASS

`feat/einheitliche-triggerarchitektur-distributed` must remain unchanged during W5-R01-C1.

Do not push the corrected W5-R01 state.

Do not touch:

- `feat/einheitliche-triggerarchitektur`
- `main`

## 2.3 Product version stays fixed

`VERSION` must remain exactly:

`2.0.0`

No `2.0.1`.
No `2.0.0rc1`.
No automatic bump.

## 2.4 One durable W5-R01 commit only

W5-R01 already produced one local final commit relative to Distributed.

The corrected W5-R01 result must still be represented as **exactly one local final commit ahead of Distributed**, not as an additional second durable W5 commit.

Therefore:

- implement and test the correction in the existing local W5-R01 workspace;
- once complete, rewrite/squash/amend the local unpushed W5-R01 commit as necessary so the final history is exactly:

```text
e5f76bf...   # current Distributed / W4C Root-PASS state
    ↓
<one corrected W5-R01 final commit>
```

This is permitted because the W5-R01 commit has not been pushed.

No force-push is involved because nothing is published.

Record both:
- previous local W5-R01 commit SHA;
- corrected final W5-R01 commit SHA.

---

# 3. Create the correction run file

Create:

`P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W5-R01-C1`

Minimal structure:

```text
W5-R01-C1\
├── 00_PROMPT.md
├── 01_CORRECTION_CONTEXT.md
├── 02_CORRECTION_REPORT.md
├── 03_GATE_STATUS.md
├── 04_DEVIATIONS_AND_WAIVERS.md
├── 05_FINAL_REPORT.md
└── Evidence\
    ├── 00_Preflight\
    ├── 01_Publish_Engine\
    ├── 02_State_Resume\
    ├── 03_Remote_Conflict\
    ├── 04_Dry_Run_Safety\
    ├── 05_Ordering_Barriers\
    ├── 06_Secret_Redaction\
    ├── 07_Tests\
    └── 08_Git_Final\
```

Copy this prompt byte-identically to:

`W5-R01-C1\00_PROMPT.md`

Record SHA256 of prompt source and copy.

Do not duplicate the entire W5-R01 evidence set. Reference the original W5-R01 run file for already-accepted evidence.

---

# 4. Verify starting state

In the existing workspace:

`P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-070-w5-r01`

record:

```text
git status --porcelain
git branch --show-current
git rev-parse HEAD
git rev-parse HEAD^{tree}
git log --oneline --decorate -3
git fetch origin
git rev-parse origin/feat/einheitliche-triggerarchitektur-distributed
```

Expected:

- workspace corresponds to W5-R01;
- local W5-R01 commit exists and is not pushed;
- remote Distributed remains exactly:
  `e5f76bf1e4fd28e68624f30140fcf8ec6876db96`

If remote Distributed changed, STOP.

If workspace contains unrelated uncommitted changes, STOP rather than overwriting them.

Record the prior local W5-R01 final commit SHA and tree before correction.

---

# 5. Correction scope

Allowed source changes are limited to what is required to complete and qualify the real publication engine, including:

- `release.py`;
- release support modules;
- publication adapters/clients/runners;
- release state logic;
- verification helpers;
- targeted tests;
- public release documentation directly affected by the final execution model;
- W5-R01 implementation comparison/deviation documentation if needed to accurately reflect the corrected implementation.

Do not redesign:

- version authority;
- Kroko artifact authority;
- Docker build architecture;
- package build architecture;
- Model Management;
- Protocol v2;
- Trigger/Activation;
- Settings;
- Wake Word;
- client behavior;
- other product features.

---

# 6. Required publication engine

Implement actual executable publication operations for the fixed W6 sequence:

```text
PRECHECK / QUALIFIED RELEASE INPUT
→ PyPI
→ GHCR
→ Docker Hub
→ external verification
→ Git tag
→ GitHub Release
→ final verification
→ COMPLETE
```

The engine must be capable of performing these operations in W6 with real credentials, but W5-R01-C1 must invoke them only through controlled fakes/mocks/test doubles or no-write dry-run paths.

## 6.1 PyPI publication adapter

Implement the real W6-capable operation to publish the already-qualified wheel/sdist.

Requirements:

- consume exact RC manifest identities;
- refuse missing or mismatched local artifacts;
- no version bump;
- no blind overwrite behavior;
- support safe resume if 2.0.0 already exists remotely;
- verify remote state sufficiently to distinguish matching completed publish from conflict;
- conflicting remote identity = STOP;
- credentials never printed or stored in state/evidence.

Use an established safe publication mechanism (for example Twine) rather than inventing a custom upload protocol unless existing project architecture clearly requires otherwise.

## 6.2 GHCR publication adapter

Implement real W6-capable image publication for the qualified Free and Pro image identities.

Requirements:

- exact immutable release version tag;
- expected image identity/digest binding;
- already-existing matching remote identity = resume;
- mismatching remote identity = STOP;
- no silent overwrite of conflicting immutable release identity;
- credentials secret-safe.

## 6.3 Docker Hub publication adapter

Same release identity and conflict rules as GHCR.

Do not allow a convenience/mutable tag to become the immutable release authority.

## 6.4 External verification

After PyPI/GHCR/Docker Hub publication, implement external verification logic capable in W6 of proving the public artifacts are retrievable and match the qualified release identity as far as each official remote interface permits.

The state may advance to external verification complete only when all required public package/container artifacts pass verification.

## 6.5 Git tag operation

Implement real W6-capable Git tag creation/push.

Hard barrier:

- impossible through normal release flow before external verification is complete.

Requirements:

- exact release commit from RC manifest/state;
- expected tag name derived from fixed version authority;
- existing same-name/same-commit tag = safe resume;
- same-name/different-commit tag = STOP;
- no automatic replacement;
- no force-push.

## 6.6 GitHub Release operation

Implement real W6-capable GitHub Release creation.

Hard barrier:

- impossible before TAGGED state.

Requirements:

- correct tag;
- release notes from qualified source;
- existing matching release = safe resume;
- conflicting release identity = STOP;
- no release publication before tag requirement is satisfied.

## 6.7 Final verification

Implement a final read-only verification phase that can confirm the completed release surfaces before state becomes COMPLETE.

---

# 7. One operation model for real run and dry-run

A key Root Review requirement:

> Dry-run must exercise the same operation graph and ordering logic as real publication, not a separate hand-written list of intended steps.

Design the release engine so that:

- real execution and dry-run share the same operation definitions/state machine;
- dry-run swaps execution side effects for a no-write runner/adapter;
- tests can inject deterministic fake adapters;
- ordering/barriers are shared;
- artifact/state validation is shared.

Do not maintain one implementation for `--dry-run` and a different unrelated implementation for `publish`.

---

# 8. Resume semantics

The release engine must safely resume the same `2.0.0` release after partial success.

Required tested scenarios include at minimum:

## 8.1 Failure after PyPI

```text
PyPI succeeds
GHCR fails
```

Rerun must:

- verify expected PyPI identity;
- not create a new version;
- not blindly re-upload;
- resume at GHCR.

## 8.2 Failure after GHCR

```text
PyPI complete
GHCR complete
Docker Hub fails
```

Rerun verifies first two remote identities and resumes at Docker Hub.

## 8.3 Failure after Docker Hub

Rerun starts from external verification.

## 8.4 Failure after external verification

Rerun may proceed to tag only after re-validating state/identity as required.

## 8.5 Failure after tag

Rerun must verify existing correct tag and continue to GitHub Release.

## 8.6 Failure after GitHub Release

Rerun must verify existing release and continue final verification.

## 8.7 Crash window / stale local state

Test at least representative cases where an external operation succeeded but local state did not advance due to interruption.

On resume:

- remote matching identity may repair/reconcile the state safely;
- remote mismatch must STOP;
- never duplicate or replace a conflicting immutable artifact.

---

# 9. Conflict/fail-closed tests

Add explicit tests for:

- PyPI version/files exist but do not match expected identity;
- GHCR release tag exists but digest mismatches;
- Docker Hub release tag exists but digest mismatches;
- Git tag exists on wrong commit;
- GitHub Release exists with incompatible tag/version identity;
- RC manifest source commit/tree mismatch;
- package hash mismatch;
- image identity mismatch;
- release state belongs to another version;
- corrupted/incomplete state;
- illegal state jump;
- attempting tag before EXTERNAL_VERIFIED;
- attempting GitHub Release before TAGGED.

Every conflict must fail closed.

---

# 10. Secret handling

No real secret values are required in W5-R01-C1.

Tests must use obvious synthetic sentinel secrets and prove they do not appear in:

- stdout;
- stderr;
- exception strings where controllable;
- state files;
- release manifests;
- evidence;
- generated commands that would be logged.

Prefer mechanisms that do not place long-lived credentials directly in process command-line arguments where avoidable.

Document credential sources by environment-variable/standard-tool contract only, never concrete values.

---

# 11. Dry-run requirements

The corrected dry-run must now prove the actual release engine.

It must show the exact operation sequence that would be executed for W6 while doing zero public writes.

Evidence must demonstrate:

- same operation objects/state machine as real publish;
- PyPI step planned;
- GHCR step planned;
- Docker Hub step planned;
- external verification planned;
- Git tag planned only after verification;
- GitHub Release planned only after tag;
- final verification planned;
- state/version remains 2.0.0;
- VERSION file unchanged;
- Git refs unchanged;
- no registry mutation;
- no GitHub Release mutation.

---

# 12. Tests

Run focused tests first, then the full suite.

At minimum, targeted tests must cover:

- real publication adapters are wired into release engine;
- dry-run uses same operation graph;
- PyPI success/failure/resume;
- GHCR success/failure/resume;
- Docker Hub success/failure/resume;
- external verification barrier;
- tag barrier;
- GitHub Release barrier;
- final verification;
- stale-state reconciliation;
- all conflict cases in section 9;
- same-version resume;
- no automatic version bump;
- secret redaction;
- no-write dry-run.

Then run:

```text
python -m pytest -q tests/unit
git diff --check
```

No weakening or deleting existing W5-R01 tests merely to obtain PASS.

---

# 13. Documentation

Update only documentation materially affected by the corrected implementation.

Must clearly state:

- W5 qualifies the actual publication engine;
- W6 executes the already-qualified engine;
- fixed publication order;
- late tag;
- same-version resume after partial release;
- no automatic new version;
- conflict = STOP;
- dry-run and real execution share the same operation model.

Do not add private VPS/selfhost details.

Record AW-01 honestly as an accepted historical process waiver.

---

# 14. Correction gates

Use exactly these gates in `03_GATE_STATUS.md`.

## Publication implementation

- **W5C1-G01** PyPI real publication adapter/path implemented.
- **W5C1-G02** GHCR real publication adapter/path implemented.
- **W5C1-G03** Docker Hub real publication adapter/path implemented.
- **W5C1-G04** External published-artifact verification path implemented.
- **W5C1-G05** Git tag create/push path implemented with late-tag barrier.
- **W5C1-G06** GitHub Release path implemented with TAGGED barrier.
- **W5C1-G07** Final verification path implemented.

## Shared execution model

- **W5C1-G08** Real publish and dry-run use the same operation graph/state machine.
- **W5C1-G09** Dry-run performs zero public writes.
- **W5C1-G10** Product version remains exactly 2.0.0.
- **W5C1-G11** No publication/tag/release occurred during C1.

## Resume / conflict safety

- **W5C1-G12** Resume after PyPI partial success tested.
- **W5C1-G13** Resume after GHCR partial success tested.
- **W5C1-G14** Resume after Docker Hub partial success tested.
- **W5C1-G15** Resume after tag/GitHub Release partial success tested.
- **W5C1-G16** Stale local state after successful remote operation reconciles safely.
- **W5C1-G17** PyPI conflicting identity fails closed.
- **W5C1-G18** GHCR conflicting identity fails closed.
- **W5C1-G19** Docker Hub conflicting identity fails closed.
- **W5C1-G20** Wrong Git tag commit fails closed.
- **W5C1-G21** Invalid GitHub Release state fails closed.
- **W5C1-G22** Illegal state/order transition fails closed.
- **W5C1-G23** No automatic new version after partial failure.

## Security / validation

- **W5C1-G24** Synthetic secret values are redacted/not persisted.
- **W5C1-G25** Targeted correction tests PASS.
- **W5C1-G26** Full unit suite PASS.
- **W5C1-G27** `git diff --check` PASS.
- **W5C1-G28** Public release documentation matches corrected execution model.

## Git / governance

- **W5C1-G29** Coordinator waiver AW-01 is recorded without falsifying history.
- **W5C1-G30** Corrected W5-R01 history is exactly one local commit ahead of Distributed.
- **W5C1-G31** Workspace clean at final state.
- **W5C1-G32** Remote Distributed remains unchanged at `e5f76bf...`; no push performed.

Every gate must be PASS/FAIL/BLOCKED/N/A with concrete evidence.

---

# 15. Evidence expectations

## `01_CORRECTION_CONTEXT.md`

Include:

- run ID/model;
- continued W5-R01 session;
- workspace;
- previous local W5-R01 commit SHA/tree;
- remote Distributed SHA/tree;
- VERSION before/after;
- prompt SHA256 source/copy;
- Root Review blocker summary;
- AW-01 status.

## `02_CORRECTION_REPORT.md`

Describe only correction deltas:

| Area | File(s) | W5-R01 state | C1 correction | Why | Gate |
|---|---|---|---|---|---|

Then concise sections:

- publication adapters;
- shared operation model;
- resume/reconciliation;
- conflict safety;
- tag/release barriers;
- secret handling;
- tests;
- documentation;
- deliberate non-changes.

## `03_GATE_STATUS.md`

Exactly W5C1-G01 through W5C1-G32.

## `04_DEVIATIONS_AND_WAIVERS.md`

Must include:

### AW-01
- Original finding: W5P-G03 plan created after implementation had already begun.
- Status: `ACCEPTED BY COORDINATOR`
- Action: no historical rewrite; process must be correct in W5-R02/W6.
- Remaining release blocker: none from AW-01.

Any new deviation must be documented separately.

## `05_FINAL_REPORT.md`

Status:

`READY FOR ROOT REVIEW`

or

`NOT READY FOR ROOT REVIEW`

Never `ROOT PASS`.

Include:

- previous W5-R01 local commit;
- corrected final local commit;
- corrected final tree;
- commit count ahead of Distributed;
- VERSION;
- targeted/full test summary;
- publication engine summary;
- dry-run result;
- resume/conflict summary;
- AW-01;
- remote Distributed unchanged;
- no public publication performed.

---

# 16. Final Git handling

After all implementation and tests:

1. review final diff adversarially;
2. ensure no release state, credentials, dist artifacts, images, logs or caches are staged unintentionally;
3. rewrite/amend/squash the existing unpushed W5-R01 local commit so the final branch contains exactly **one** W5-R01 commit on top of:
   `e5f76bf1e4fd28e68624f30140fcf8ec6876db96`;
4. recommended commit message remains:
   `AP-SRV-070 W5: prepare release candidate qualification`
5. record final commit/tree;
6. verify workspace clean;
7. fetch origin;
8. verify Distributed is still exactly:
   `e5f76bf1e4fd28e68624f30140fcf8ec6876db96`;
9. verify commit count:
   exactly one local commit ahead;
10. **DO NOT PUSH**.

The coordinator will perform another Root Review before any push authorization.

---

# 17. Stop conditions

STOP and report `NOT READY FOR ROOT REVIEW` if:

- remote Distributed changed;
- public write would be required to prove correctness;
- a safe adapter for a required release surface cannot be implemented without exposing secrets;
- same-version resume cannot fail closed;
- publication identity cannot be verified adequately enough to distinguish match vs conflict;
- implementation would require redesigning closed product architecture;
- the correction unexpectedly requires unrelated product changes.

Do not broaden scope.

---

# 18. Success state

W5-R01-C1 succeeds when:

```text
existing W5-R01 release preparation
→ real PyPI execution path
→ real GHCR execution path
→ real Docker Hub execution path
→ real external verification
→ real late Git-tag path
→ real GitHub Release path
→ real final verification
→ shared dry-run/real operation graph
→ tested same-version resume
→ tested conflict fail-closed behavior
→ no secrets
→ no public writes
→ VERSION 2.0.0 unchanged
→ full tests PASS
→ exactly one corrected local W5-R01 commit ahead of Distributed
→ no push
→ READY FOR ROOT REVIEW
```

W6 must then be able to execute this already-qualified publication engine rather than introducing new critical publication logic after W5 RC qualification.
