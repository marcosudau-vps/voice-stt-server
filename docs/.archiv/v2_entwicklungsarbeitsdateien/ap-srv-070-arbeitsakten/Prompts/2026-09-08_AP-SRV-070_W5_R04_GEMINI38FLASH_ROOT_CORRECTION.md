# AP-SRV-070 / W5-R04 — Root Review Correction B1–B4 + E1

## 0. Run mode

**Model:** Gemini 3.8 Flash
**Session:** CONTINUE THE EXISTING GEMINI SESSION
**Workspace:** continue the existing W5-R04 workspace; do not create a new workspace
**Task type:** narrow Root-Review correction of the already completed W5-R04 implementation

Workspace:

`P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-070-w5-r04`

Working branch:

`work/ap-srv-070-w5-r04`

Binding original W5-R04 parent:

`934e3be7c78aa9358f9b42b9fa4dc282bed54d6c`

Original parent tree:

`2936f70ca44b7a902e1e5c7c5ca69eacc3154fdb`

Current local commit that FAILED external Root Review:

`5a87ad837a9f078c59a37bd7a1e1134b59117a97`

Current local tree:

`8c69d0883ed9abb0498e83af1a746c34a7203370`

Current commit message:

`AP-SRV-070 W5: finalize GitHub-native release infrastructure`

Remote Distributed branch is still expected to be:

`934e3be7c78aa9358f9b42b9fa4dc282bed54d6c`

Evidence root:

`P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W5-R04\`

The previous completion report is:

`P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W5-R04\09_FINAL_REPORT.md`

The external Root Review rejected the local commit for exactly four concrete release blockers plus one evidence inconsistency. This correction run exists only to close those findings.

---

# 1. Critical governance

This is **not a new design run** and not an opportunity to improve unrelated code.

The following areas from W5-R04 are accepted and CLOSED unless one of the four blockers below objectively requires a narrowly connected change:

- canonical release state order;
- tag before first public write;
- Docker Hub before GHCR;
- same-manifest/digest promotion from Docker Hub to GHCR;
- aliases `2.0`, `2`, `latest`;
- GitHub Release last;
- Free/Pro product split;
- `voice-stt-server` and `voice-stt-server-pro`;
- canonical import `voice_stt_server`;
- canonical CLI `voice-stt-server`;
- no public separate Kroko PyPI packages;
- no sdist under the later binding packaging authority;
- embedded Kroko Free/Pro native runtime;
- README rewrite;
- engine documentation cleanup;
- source-derived build date;
- manifest digest as OCI image identity;
- remote MATCH / ABSENT / CONFLICT / UNKNOWN semantics;
- secret redaction;
- local empty-artifact-store proof;
- model management;
- Trigger/Activation/Wake/Settings/Protocol v2;
- all unrelated W4/W5 product functionality.

Do not add model-image functionality.

## No further widening

Only modify files necessary to close:

- B1 GitHub publish workflow permissions
- B2 missing Windows public-wheel candidate path
- B3 `NOT_QUALIFIED` candidate can reach publish
- B4 PyPI public write occurs before conflict precheck
- E1 contradictory staging evidence

If a test exposes another concrete release blocker directly caused by these corrections, fix it minimally and document it. Otherwise do not broaden.

---

# 2. Git handling for this correction

The current local commit `5a87ad837...` was:

- never pushed;
- never Root-approved;
- explicitly rejected by external Root Review.

Therefore it must **not** become durable Distributed history.

The corrected result must again be exactly **one local W5-R04 implementation commit directly parented to**:

`934e3be7c78aa9358f9b42b9fa4dc282bed54d6c`

You are explicitly authorized in this correction run to replace the failed-review local commit by amending it after the corrected final tree is fully tested.

Preferred procedure:

1. verify current HEAD is exactly `5a87ad837...` and parent exactly `934e3be7...`;
2. make only the approved corrections;
3. run all required verification against the final corrected worktree;
4. stage the complete corrected tree;
5. use exactly one:
   `git commit --amend --no-edit`
6. verify the new commit still has direct parent `934e3be7...`.

Do **not** create a second durable commit on top of `5a87ad837...`.

Do not push.

If the actual repository state differs from the expected identities, stop and report `NOT READY FOR ROOT REVIEW`.

---

# 3. First action — literal preflight

Before editing, capture:

```powershell
git status --porcelain=v1
git rev-parse HEAD
git rev-parse "HEAD^{tree}"
git rev-parse HEAD^
git log -1 --format="%H%n%T%n%P%n%s"
git branch --show-current
git rev-parse origin/feat/einheitliche-triggerarchitektur-distributed
```

Expected:

- clean workspace;
- HEAD `5a87ad837a9f078c59a37bd7a1e1134b59117a97`;
- tree `8c69d0883ed9abb0498e83af1a746c34a7203370`;
- parent `934e3be7c78aa9358f9b42b9fa4dc282bed54d6c`;
- remote Distributed still `934e3be7...`.

Record the failed-review commit/tree in the evidence as the superseded local attempt.

---

# 4. B1 — GitHub publish workflow permissions

## Root Review finding

The publish workflow downloads candidate artifacts from another workflow run using:

- `actions/download-artifact`
- `run-id: ${{ inputs.candidate_run_id }}`
- `github-token: ${{ secrets.GITHUB_TOKEN }}`

Jobs declare explicit `permissions:` blocks.

When a job declares explicit permissions, permissions not listed are effectively unavailable.

The current publish workflow therefore lacks permissions needed for:

1. cross-run Actions artifact download (`actions: read`);
2. checkout in jobs that only declare e.g. `id-token: write` but still run `actions/checkout` (`contents: read`).

This is a concrete release execution blocker.

## Required correction

Inspect `.github/workflows/release-publish.yml` and all jobs that:

- checkout repository contents;
- download candidate artifacts by `run-id`;
- create/push tag;
- publish PyPI;
- promote registries;
- finalize GitHub Release.

Give each job only the permissions actually required.

At minimum, any cross-run artifact consumer must have:

```yaml
actions: read
```

Any job using checkout must have:

```yaml
contents: read
```

unless it legitimately needs stronger `contents: write`.

The tag / GitHub Release job may require:

```yaml
contents: write
```

The PyPI Trusted Publishing job must keep:

```yaml
id-token: write
```

and also have only the other read permissions it actually uses.

GHCR write jobs may require:

```yaml
packages: write
```

Do not grant broad repository write permissions globally.

## Required tests

Extend/update workflow contract tests so this cannot regress.

Tests must assert:

- every cross-run artifact download job has `actions: read`;
- every checkout job has at least `contents: read`;
- `id-token: write` remains isolated to the PyPI OIDC job;
- `contents: write` / `packages: write` remain limited to jobs that need them;
- normal CI remains read-only and unable to publish.

---

# 5. B2 — GitHub-native Candidate must build both Linux and Windows public wheels

## Root Review finding

The later binding packaging authority requires complete public distributions for:

- CPython 3.12 / Linux x86_64
- CPython 3.12 / Windows AMD64

for both:

- `voice-stt-server`
- `voice-stt-server-pro`

Each final distribution embeds its corresponding native Kroko runtime.

The current GitHub candidate workflow is Linux-only and therefore only produces Linux public distribution wheels.

That would make:

`pip install voice-stt-server`

and:

`pip install voice-stt-server-pro`

incomplete/unavailable on supported Windows AMD64, despite the documented product contract.

This is a concrete packaging/release blocker.

## Required end state

The authoritative GitHub Candidate must produce, bind, persist and later publish all four platform/variant products from the same exact source commit/tree:

```text
voice-stt-server
├── CPython 3.12 / Linux x86_64 wheel with Kroko Free runtime
└── CPython 3.12 / Windows AMD64 wheel with Kroko Free runtime

voice-stt-server-pro
├── CPython 3.12 / Linux x86_64 wheel with Kroko Pro runtime
└── CPython 3.12 / Windows AMD64 wheel with Kroko Pro runtime
```

All four wheels must:

- originate from the exact same source commit/tree;
- use the existing Free/Pro Kroko build authority;
- require no local developer-machine artifact;
- be produced on GitHub-hosted runners;
- have correct native wheel tags;
- be SHA256-bound by the candidate manifest;
- be persisted as exact candidate artifacts;
- be published without rebuild.

## Preferred architecture

Do not redesign the whole release engine.

Use the smallest workflow/build adjustment consistent with the existing design. A likely shape is:

```text
GitHub Candidate Workflow
├── Linux candidate job
│   ├── build Kroko Free Linux
│   ├── build Kroko Pro Linux
│   ├── assemble Free Linux distribution wheel
│   ├── assemble Pro Linux distribution wheel
│   └── build Free/Pro OCI images
│
├── Windows candidate job
│   ├── build Kroko Free Windows
│   ├── build Kroko Pro Windows
│   ├── assemble Free Windows distribution wheel
│   └── assemble Pro Windows distribution wheel
│
└── candidate assembly / qualification job
    ├── collects exact wheels from both jobs
    ├── verifies hashes and identities
    ├── creates one candidate manifest
    └── persists exact candidate artifact set
```

The exact job breakdown may differ if a simpler existing mechanism already supports this.

Do not add macOS or other Python versions.

## Candidate manifest change

The manifest must no longer model each public distribution as if it had only one wheel.

It must bind the full required wheel set separately and unambiguously.

At minimum each published wheel identity must include enough authority to verify:

- distribution name;
- product version;
- filename;
- SHA256;
- Python/ABI/platform tag;
- Free/Pro variant;
- embedded Kroko artifact identity/fingerprint;
- source commit/tree.

Keep schema changes minimal and versioned correctly if schema semantics change.

Resume/identity comparison must compare the complete wheel set.

## Publication change

PyPI publication must publish the exact complete candidate wheel set:

- Free Linux
- Free Windows
- Pro Linux
- Pro Windows

without rebuild.

Same-version resume must work if some exact files already MATCH and others are ABSENT.

Any conflicting same-version file must fail closed.

## Required tests

Add/update tests for at least:

- manifest accepts/binds both Linux and Windows wheels for both distributions;
- missing one required platform wheel fails candidate completeness;
- duplicate/conflicting platform identity fails;
- Free and Pro runtime identities cannot cross;
- Windows wheel tag is correct;
- Linux wheel tag is correct;
- publish artifact selection includes all required wheels;
- workflow contains GitHub-hosted Windows candidate build;
- no local artifact-store dependency is introduced.

Do not claim a real GitHub-hosted Windows candidate build has already occurred locally. That authoritative proof comes after Root-approved push.

---

# 6. B3 — `NOT_QUALIFIED` candidate must be impossible to publish

## Root Review finding

The candidate manifest currently supports readiness values such as:

- `NOT_QUALIFIED`
- `QUALIFIED`
- `REJECTED`

The normal candidate path produces a `NOT_QUALIFIED` manifest.

The real publish preflight validates manifest structure but does not require the candidate to be `QUALIFIED`.

Therefore a syntactically valid but explicitly non-qualified candidate can reach the real publication path.

This violates the release invariant:

> No public write may occur for an unqualified candidate.

## Required correction

Implement one clear fail-closed qualification authority.

Do not invent a second release system.

The existing single release engine/state model must remain authoritative.

A valid approach may be either:

### Option A — qualified manifest

Qualification produces a controlled, immutable candidate manifest/manifest successor whose:

```text
releaseReadiness == QUALIFIED
```

and whose identity remains bound to the exact candidate artifacts.

Real publish requires `QUALIFIED`.

or:

### Option B — qualification attestation

Keep candidate manifest artifact identity immutable and create a separate qualification attestation/state object that is cryptographically/identity-bound at minimum to:

- candidate manifest SHA256;
- source commit;
- source tree;
- candidate run ID;
- exact artifact identities.

Real publish requires a valid PASS attestation.

Whichever option best fits the existing code with fewer moving parts is preferred.

## Mandatory semantics

Real publish must refuse before any public write if:

- readiness is `NOT_QUALIFIED`;
- readiness is `REJECTED`;
- qualification evidence is missing;
- qualification identity refers to another manifest/run/tree;
- qualification state is unverifiable.

UNKNOWN/unverifiable must fail closed.

A manual GitHub Environment approval is **not by itself** a substitute for technical candidate qualification.

The environment remains an operator/publication approval boundary, not the artifact qualification fact.

## Required tests

Tests must prove:

- `NOT_QUALIFIED` cannot enter real publication;
- `REJECTED` cannot enter real publication;
- valid `QUALIFIED` exact identity can publish;
- mismatched qualification identity hard-stops;
- dry-run remains non-destructive;
- qualification transition does not rebuild candidate artifacts.

---

# 7. B4 — PyPI remote conflict precheck must occur before OIDC public write

## Root Review finding

The desired PyPI semantics are:

```text
ABSENT   -> publish
MATCH    -> resume
CONFLICT -> STOP
UNKNOWN  -> STOP
```

The workflow currently invokes Trusted Publishing first and lets the release engine verify PyPI afterward.

This means public PyPI state can be modified before the engine has established that the existing same-version state is safe.

`skip-existing` does not solve conflict semantics.

## Required correction

Keep Trusted Publishing/OIDC.

Do not reintroduce a long-lived PyPI token.

Before the `pypa/gh-action-pypi-publish` write, run an explicit read-only candidate-vs-PyPI precheck using the canonical release tooling/remote-check semantics.

The precheck must evaluate both distributions and the complete required wheel set.

Allowed outcomes:

### ABSENT
Expected file does not exist and no conflicting same-version state exists:
→ public write may proceed.

### MATCH
Expected file already exists with the exact expected identity:
→ resume; do not need to re-upload that file.

### CONFLICT
Same version/project contains a conflicting identity:
→ hard STOP before public write.

### UNKNOWN
PyPI state cannot be reliably inspected:
→ hard STOP before public write.

Then:

```text
read-only PyPI precheck
        ↓
only ABSENT/MATCH accepted
        ↓
Trusted Publishing/OIDC write of missing exact artifacts
        ↓
post-write exact PyPI verification
        ↓
PYPI_PUBLISHED
```

If the existing PyPI publish action cannot selectively publish only missing files safely, implement the smallest safe artifact-selection step before the action. Do not rebuild wheels.

## Required tests

Tests must demonstrate:

- conflict detected before writer invocation;
- unknown detected before writer invocation;
- full MATCH causes safe resume/no destructive republish;
- partial MATCH + ABSENT publishes only missing exact files if supported;
- post-write verification still occurs;
- Free and Pro projects are checked separately;
- all Linux/Windows candidate wheels participate in the check.

---

# 8. E1 — correct contradictory staging evidence

## Root Review finding

The previous gate index says in G17 that candidate images were pushed to private staging GHCR.

The same evidence set and final report correctly state:

- zero staging pushes occurred;
- zero public/mutative writes occurred.

The local W5-R04 run did **not** perform a staging push.

## Required correction

Correct the evidence wording.

The truthful distinction is:

```text
Local W5-R04 implementation/evidence:
- proves staging architecture and candidate-persistence mechanism structurally;
- may include local build artifacts/tests;
- performs zero staging registry writes.

Post-Root-PASS GitHub Candidate run:
- will perform the actual private staging persistence;
- will provide authoritative clean-runner/staging evidence.
```

Do not falsely claim a staging push occurred.

Update:

- `07_GATE_INDEX.md`
- `09_FINAL_REPORT.md`
- any other current W5-R04 evidence document that makes the same false statement.

G75 can only PASS if the final evidence set is internally consistent.

Historical raw evidence should not be silently altered unless it is explicitly a generated current report intended to be corrected.

---

# 9. Verification strategy

Because this is a narrow correction to release infrastructure, do not repeat expensive unrelated E2E/product qualification.

Required verification is:

## 9.1 Targeted

Run all affected tests, including at minimum:

- release workflow tests;
- release candidate tests;
- RC manifest tests;
- release preflight tests;
- release engine/state tests;
- remote check tests;
- release adapter/PyPI tests;
- build distribution tests;
- Kroko fingerprint/artifact authority tests affected by Windows candidate generation;
- docs/evidence guards if modified.

Add tests needed for B1–B4.

## 9.2 Full regression

After all tracked corrections are frozen, re-run:

### Windows

```powershell
python -m pytest -q --basetemp=<fresh-unique-dir> tests/unit
```

### Ubuntu 24.04 / WSL2 native ext4

Refresh the native source copy from the corrected final worktree and run:

```bash
python -m pytest -q tests/unit
```

Both must PASS.

Do not make tracked edits after these successful final-tree runs unless a real defect is found; if tracked edits occur, repeat affected final verification.

## 9.3 Static/security

Run:

```powershell
git diff --check
```

Review:

- no secret;
- no unintended binary;
- no generated wheel/model/archive committed;
- no scope widening;
- GitHub Actions permissions remain least-privilege;
- no release credential enters untrusted jobs.

---

# 10. Evidence updates

Update the existing W5-R04 evidence set rather than creating a new broad run.

At minimum update:

- `05_CHANGED_FILES.md`
- `06_TEST_MATRIX.md`
- `07_GATE_INDEX.md`
- `08_DEVIATIONS.md`
- `09_FINAL_REPORT.md`

Create a short explicit Root Review correction section recording:

```text
External Root Review result on superseded local commit:
FAIL

Superseded commit:
5a87ad837a9f078c59a37bd7a1e1134b59117a97

Findings corrected:
B1
B2
B3
B4
E1
```

Archive the corrected final pre-commit diff and SHA256.

Do not erase the fact that `5a87ad837...` failed review.

---

# 11. Final commit

Only after all corrected final-tree tests pass:

1. stage the complete corrected tracked tree;
2. confirm only W5-R04 scope is staged;
3. amend the failed-review local commit:

```powershell
git commit --amend --no-edit
```

This amend is explicitly authorized because the previous commit:

- failed external Root Review;
- was never pushed;
- must not become durable history.

The new final commit must:

- have direct parent exactly `934e3be7c78aa9358f9b42b9fa4dc282bed54d6c`;
- retain commit subject:
  `AP-SRV-070 W5: finalize GitHub-native release infrastructure`;
- be the only W5-R04 commit above the binding parent;
- contain all accepted W5-R04 work plus B1–B4 corrections;
- leave the workspace literally clean.

After amend capture:

```powershell
git rev-parse HEAD
git rev-parse "HEAD^{tree}"
git rev-parse HEAD^
git log -1 --format="%H%n%T%n%P%n%s"
git status --porcelain=v1
git rev-parse origin/feat/einheitliche-triggerarchitektur-distributed
```

Remote Distributed must still be `934e3be7...`.

---

# 12. Absolute prohibitions

Do NOT:

- push any branch;
- create/push any tag;
- upload to PyPI/TestPyPI;
- push Docker Hub;
- push public GHCR;
- push private staging GHCR;
- create GitHub Release;
- touch canonical or main;
- force-push;
- create a second correction commit;
- broaden product functionality;
- add model-image support;
- redesign the accepted state ordering;
- rebuild/rework closed product areas without a concrete test blocker.

This remains a local Source-Implementation correction only.

The authoritative GitHub Candidate build occurs only after external Root PASS and exact push authorization.

---

# 13. Final report

If and only if all blockers are closed and all mandatory tests pass, `09_FINAL_REPORT.md` must begin:

`READY FOR ROOT REVIEW`

It must explicitly summarize:

- superseded failed-review commit `5a87ad837...`;
- new corrected commit SHA/tree/parent;
- B1 correction;
- B2 Windows + Linux candidate wheel matrix;
- complete manifest wheel identities;
- B3 qualification publication barrier;
- B4 PyPI pre-write conflict check;
- E1 evidence correction;
- targeted tests;
- Windows full regression;
- Ubuntu full regression;
- clean final status;
- unchanged remote;
- zero push/tag/PyPI/DockerHub/GHCR/staging/GitHub Release writes.

Never claim Root PASS.

If any blocker remains:

`NOT READY FOR ROOT REVIEW`

and list the exact unresolved condition.

---

# 14. Acceptance criteria for the next external Root Review

The corrected run is ready only if all of the following are demonstrably true:

### B1
- every cross-run candidate-artifact consumer has `actions: read`;
- every checkout job has adequate `contents` permission;
- OIDC/write permissions remain least-privilege.

### B2
- GitHub Candidate architecture builds both Linux x86_64 and Windows AMD64 native Free/Pro distribution wheels;
- all required wheels are bound in one candidate authority;
- all are persisted and later published without rebuild;
- no local developer artifact is required.

### B3
- real publish is impossible for NOT_QUALIFIED/REJECTED/unverifiable candidate qualification;
- qualification binds the exact candidate identity;
- operator environment approval is not misused as qualification fact.

### B4
- PyPI read-only conflict/unknown check happens before Trusted Publishing public write;
- MATCH/ABSENT semantics are safe and resumable;
- post-write exact verification remains.

### E1
- evidence no longer falsely claims a private staging push occurred locally.

### Git
- exactly one corrected local implementation commit;
- direct parent exact `934e3be7...`;
- clean worktree;
- remote still unchanged;
- zero remote/public/staging writes.

Do exactly this and stop.
