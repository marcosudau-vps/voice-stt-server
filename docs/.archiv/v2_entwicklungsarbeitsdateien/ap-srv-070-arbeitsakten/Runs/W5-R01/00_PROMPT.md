# AP-SRV-070 / W5 — Release Candidate Preparation
## W5-R01 — Release Infrastructure, CI, Qualification Harness
### Model: Sonnet 5

---

# 0. Run identity

- **Project:** AP-SRV-070
- **Phase:** W5 — Release Candidate Qualification
- **Run:** W5-R01
- **Purpose:** RC Preparation / Release Infrastructure
- **Model:** Anthropic Sonnet 5
- **Session:** NEW SESSION
- **Repository:** `marcosudau-vps/voice-stt-server`
- **Target integration branch:** `feat/einheitliche-triggerarchitektur-distributed`
- **Binding start commit:** `e5f76bf1e4fd28e68624f30140fcf8ec6876db96`
- **Binding start tree:** `f3eb03728dd1d0a4d57855a6154430b7142c8995`
- **Session start folder:** `P:\GithubRepos\marcosudau-vps\voice-stt-server`
- **Dedicated worktree:** `P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-070-w5-r01`
- **Prompt source:** `P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Prompts\2026-09-06_AP-SRV-070_W5_R01_SONNET5.md`
- **Run / evidence root:** `P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W5-R01\`

This run prepares the repository for an exact, frozen 2.0.0 release-candidate qualification.

It does **not** perform the final RC qualification itself and it performs **no public release**.

The next planned run is W5-R02. W5-R02 will start only after this run has passed external Root Review and its one approved commit has been fast-forwarded to Distributed. W5-R02 will freeze that exact commit as the RC and perform qualification without source changes.

---

# 1. Critical governance

## 1.1 No push before external Root PASS

During W5-R01:

- create exactly one final local W5-R01 source commit;
- **DO NOT push it to `feat/einheitliche-triggerarchitektur-distributed`;**
- DO NOT force-push;
- DO NOT modify canonical `feat/einheitliche-triggerarchitektur`;
- DO NOT modify `main`;
- DO NOT create or push tags;
- DO NOT create a GitHub Release;
- DO NOT publish to PyPI;
- DO NOT publish to GHCR;
- DO NOT publish to Docker Hub.

The coordinator performs external Root Review first.

Only after an explicit separate push authorization may the approved commit be fast-forwarded to Distributed.

## 1.2 Product version

The AP-SRV-070 public release target is:

`2.0.0`

`VERSION` is already `2.0.0`.

**W5-R01 must not bump the product version.**

Internal qualification candidates may later be named W5-RC1, W5-RC2, etc. These are workflow identities only and must not become public package versions such as `2.0.0rc1`.

## 1.3 No wasted public version numbers

The release system must be designed around this invariant:

> A partial publication failure never causes an automatic new product version. The same release version is resumed until all publication steps complete or an explicit human decision aborts the release before publication begins.

For AP-SRV-070:

- W5 publishes nothing.
- W6 will publish 2.0.0.
- If W6 succeeds on one registry and fails later, a rerun resumes **2.0.0**, never automatically switches to 2.0.1.

## 1.4 Fixed W6 publication order

The release tooling prepared in W5 must encode or enforce this order:

```text
PRECHECK / QUALIFIED RELEASE INPUT
→ PyPI
→ GHCR
→ Docker Hub
→ external verification of published package/images
→ Git tag
→ GitHub Release
→ final verification
→ COMPLETE
```

The Git tag is deliberately late.

The tool must never create the version tag before the preceding package/container publication steps have succeeded and the externally retrievable artifacts have been verified.

---

# 2. Prepare run file and worktree

Create:

`P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W5-R01`

with:

```text
W5-R01\
├── 00_PROMPT.md
├── 01_RUN_CONTEXT.md
├── 02_IMPLEMENTATION_REPORT.md
├── 03_GATE_INDEX.md
├── 04_DEVIATIONS.md
├── 05_FINAL_REPORT.md
└── Evidence\
    ├── 00_Preflight\
    ├── 01_Release_Tooling\
    ├── 02_Release_State_Safety\
    ├── 03_Version_Release_Notes\
    ├── 04_GitHub_Actions\
    ├── 05_Package_Qualification\
    ├── 06_RC_Harness\
    ├── 07_Tests\
    ├── 08_Dry_Run\
    └── 09_Git_Final\
```

Copy the prompt byte-identically from the prompt source to:

`W5-R01\00_PROMPT.md`

Record SHA256 of source and copy.

Fetch origin and verify:

`origin/feat/einheitliche-triggerarchitektur-distributed`

is exactly:

`e5f76bf1e4fd28e68624f30140fcf8ec6876db96`

and tree exactly:

`f3eb03728dd1d0a4d57855a6154430b7142c8995`

Mismatch = STOP.

Create the dedicated worktree from exactly this commit, with a local branch such as:

`work/ap-srv-070-w5-r01`

If the intended worktree path already exists, do not delete blindly. Reuse only if identity, HEAD, branch and cleanliness unambiguously match this run; otherwise STOP.

Record:

- git status
- branch
- HEAD
- tree
- worktree list
- Python
- Git
- Docker
- Docker Compose
- host OS

Implementation happens only in the dedicated W5-R01 worktree.

---

# 3. Read binding authorities before implementation

At minimum:

- `AGENTS.md`
- applicable nested `AGENTS.md`
- `build/BUILD.md`
- `docs/.archiv/README.md`
- existing AP-SRV-070 archive documents
- `VERSION`
- `VoiceSTT/_version.py`
- `setup.py`
- `MANIFEST.in`
- `requirements.txt`
- `requirements-dev.txt`
- `README.md`
- `RELEASE_NOTES.md`
- `docs/testing.md`
- `tools/build_production.py`
- `Dockerfile`
- `docker-compose.yml`
- Kroko artifact/fingerprint implementation and tests
- W4C public Docker/Compose contracts
- package/version tests
- existing test helpers relevant to installed-distribution checks

Do not use private VPS/selfhost deployment material as public release authority.

`build/vps/*` is out of W5 public release scope.

---

# 4. W5 structure to preserve

W5 is intentionally split:

```text
W5-R01  RC Preparation / Release Infrastructure
         ↓ external Root Review
         ↓ approved single commit fast-forwarded to Distributed
W5-R02  RC Freeze + Qualification
         ↓ no source changes
         ↓ exact RC manifest + complete evidence
         ↓ external Root Review
W6       resumable publication of exactly the qualified 2.0.0 release
```

W5-R01 must prepare everything W5-R02 needs.

Do not execute W5-R02 in this run.

---

# 5. W5-R01 source-change scope

Allowed:

- release orchestration tooling;
- release preflight / dry-run / resumable state logic;
- GitHub Actions CI;
- qualification helpers/harnesses;
- tests for the new release/CI logic;
- final 2.0.0 release notes preparation;
- public release/build/testing documentation;
- required AP-SRV-070 W5 archive plan and implementation comparison.

Not allowed without a concrete blocker:

- trigger redesign;
- protocol redesign;
- settings redesign;
- wake-word redesign;
- STT model-management redesign;
- Kroko artifact/fingerprint redesign;
- W4C Docker architecture redesign;
- client redesign;
- new product feature work;
- private VPS/selfhost changes.

If W5-R01 discovers a genuine unrelated product bug, document it. Do not opportunistically expand scope.

---

# 6. Implement the release orchestrator

Create the repository-level release entry point anticipated by `build/BUILD.md`.

The intended public operator surface is a repository-root:

`release.py`

Exact internal module structure may be factored cleanly if needed, but there must be one obvious canonical entry point and no competing release authority.

## 6.1 Responsibilities

The release system must be capable of:

1. resolving current product version from the existing single version authority;
2. resolving exact Git commit/tree;
3. requiring a clean eligible source state for a release;
4. consuming an RC/release manifest with immutable artifact identities;
5. validating package and container artifact identities before publication;
6. performing read-only release preflight;
7. performing a **true no-publish dry-run**;
8. maintaining non-secret resumable release state;
9. enforcing fixed publication order;
10. resuming the same version after partial success;
11. refusing conflicting/mismatched pre-existing remote release artifacts;
12. preventing Git tag creation before external artifact verification;
13. preventing GitHub Release creation before the Git tag step;
14. emitting concise, redacted, machine-readable/useful operator output;
15. failing closed on ambiguity.

Actual public write operations must exist only if they can be implemented safely and testably now; W5 executes none of them.

Do not invent a second version authority.

## 6.2 Current release target vs future bumps

Current AP-SRV-070 target is already `2.0.0`.

W5-R01 must not transform it into 2.0.1.

If the existing `build/BUILD.md` concept of:

- `python release.py` = future patch preparation
- `--minor`
- `--major`

is retained, clearly separate **future version preparation** from **publishing the already-prepared current version**.

The publish/preflight/dry-run path for AP-SRV-070 must operate on current `VERSION=2.0.0` without incrementing it.

Avoid a CLI where merely running a preflight or dry-run can mutate `VERSION`, release notes, Git, registries or state in a misleading way.

---

# 7. Resumable release-state contract

The release state is not Git authority and must not contain secrets.

Use a gitignored runtime/output location appropriate to the repository.

At minimum model states equivalent to:

```text
PREPARED
PYPI_PUBLISHED
GHCR_PUBLISHED
DOCKERHUB_PUBLISHED
EXTERNAL_VERIFIED
TAGGED
GITHUB_RELEASED
FINAL_VERIFIED
COMPLETE
```

The implementation may use a richer representation.

Required properties:

- version is fixed once publication begins;
- exact source commit/tree recorded;
- exact wheel/sdist hashes recorded;
- exact Free/Pro image identities recorded;
- state transitions are monotonic;
- rerun resumes from the last verified state;
- already completed remote steps are verified, not blindly repeated;
- mismatch between expected and remote existing artifact = hard STOP;
- no automatic new version after a partial failure;
- state can be reconstructed/validated safely enough to avoid accidental double publication;
- no credentials/tokens/secret values in the state file;
- no secrets in tracebacks or normal logs.

A failed step must leave a state that can safely resume the **same version**.

---

# 8. Publication safety contracts

## 8.1 PyPI

The W6 implementation path must treat a version already present on PyPI as immutable.

If expected release files already exist remotely:

- verify identity as far as the official remote interface permits;
- if they correspond to expected release artifacts, mark/retain the step as complete;
- if they conflict, STOP;
- never silently choose a new version.

## 8.2 GHCR / Docker Hub

Immutable version-tag identity is authoritative for the release.

If a release version tag already exists:

- verify its manifest/digest against expected release identity;
- identical = safe resume;
- mismatch = STOP;
- no silent overwrite of conflicting release identity.

Mutable convenience tags, if supported later, must never replace the immutable version identity as release authority.

## 8.3 Git tag

Tag creation is forbidden until:

- PyPI complete;
- GHCR complete;
- Docker Hub complete;
- external verification complete.

Existing tag with same name but wrong commit = STOP.

The release tooling must make this ordering impossible to bypass accidentally through normal use.

## 8.4 GitHub Release

GitHub Release is after tag creation.

It is the last public publication surface in the fixed W6 order.

---

# 9. Preflight and dry-run

W5 needs a release process that is heavily tested before any version is consumed publicly.

Implement explicit safe modes equivalent to:

- preflight
- dry-run

The exact CLI spelling may follow a clean design.

## Preflight

Read-only checks should cover as much as practical without publication, including:

- VERSION valid and expected;
- release notes prepared;
- Git eligibility;
- clean tree;
- exact commit/tree;
- release artifact manifest complete;
- wheel/sdist identities;
- Free/Pro image identities;
- tag absence or compatible state;
- tool availability;
- registry/repository identifiers;
- credential presence/auth status where safely checkable without exposing values;
- remote version/tag availability where safely read-only;
- no state conflict.

Preflight must not publish, tag, commit, bump version or rewrite release state as though a publish succeeded.

## Dry-run

Dry-run must walk the full planned release state machine and report the exact operations/order that would occur.

It must not:

- upload packages;
- push images;
- mutate registry tags;
- create Git tags;
- push Git refs;
- create GitHub Releases;
- mutate VERSION;
- leak secrets.

Tests must prove the dry-run is side-effect-free for public systems.

---

# 10. GitHub Actions CI

GitHub Actions is mandatory in W5.

Add a public CI workflow under `.github/workflows/`.

It must be suitable for an open-source/public repository and require no private runtime secrets for ordinary CI.

## 10.1 Required triggers

At minimum sensible combinations of:

- pull request;
- push to relevant development/release branches;
- `workflow_dispatch`.

Do not create public release/publish triggers in W5-R01.

## 10.2 Required platforms

Mandatory fresh-install/CI coverage:

- Windows
- Ubuntu 24.04

Use Python 3.12 as the mandatory release qualification interpreter on both platforms.

Additional low-cost Python compatibility coverage may be added if it follows the declared project support without making the workflow unreasonably heavy, but it must not replace the mandatory Windows + Ubuntu 24.04 / Python 3.12 path.

## 10.3 CI responsibilities

At minimum, CI must exercise appropriate combinations of:

- checkout;
- clean Python environment;
- required OS prerequisites;
- package build;
- wheel + sdist metadata validation;
- `twine check`;
- installation from the built wheel, **not editable checkout**;
- `pip check`;
- import/version checks from installed distribution;
- console-script availability;
- installed package assets;
- unit/guard tests appropriate to the platform;
- packaging-specific tests;
- release-tool unit tests.

CI must not:

- publish to PyPI;
- publish to GHCR;
- publish to Docker Hub;
- create/push tags;
- create GitHub Releases;
- require Kroko Pro runtime secret;
- perform a full native Kroko production build merely to make ordinary CI green.

W5-R02 will later require the workflow for the exact RC commit to be green.

Because the workflow does not exist remotely before W5-R01 is approved and pushed, W5-R01 only needs strong static/local validation of the workflow plus equivalent local test execution where possible. Do not fake a GitHub Actions run.

---

# 11. Package qualification helpers

Prepare reusable helpers/tests so W5-R02 can prove:

```text
exact RC source
→ wheel + sdist
→ twine check
→ fresh install
→ import/version
→ console scripts
→ package assets
→ no checkout dependency
```

The release package is `voicestt`.

Current important console scripts include:

- `stt-server`
- `stt-server-legacy`
- `stt`
- `stt-install-kroko`

Do not weaken current package-data authorities.

The W5-R02 installed-distribution checks must work on both Windows and Ubuntu.

---

# 12. RC manifest / qualification harness

Prepare one canonical machine-readable RC manifest format for W5-R02.

It must be able to bind at minimum:

- internal candidate ID, e.g. `W5-RC1`;
- product version;
- source commit;
- source tree;
- wheel filename + SHA256;
- sdist filename + SHA256;
- Kroko Free fingerprint + artifact SHA256;
- Kroko Pro fingerprint + artifact SHA256;
- Free production image tag + image ID/digest;
- Pro production image tag + image ID/digest;
- OCI version;
- OCI revision;
- qualification timestamp/context;
- reference to qualification evidence/gates;
- release readiness status.

Do not store secrets.

The manifest must be precise enough that W6 can refuse to publish artifacts that differ from the W5-qualified identities.

Do not make W6 rebuild different source unknowingly.

If W6 must rebuild a transport-specific artifact, the release system must re-establish identity from the same frozen source and contracts; preferably it should consume the already-qualified artifacts/identities.

---

# 13. Finalize 2.0.0 release notes

`RELEASE_NOTES.md` currently has the AP-SRV-070 work under `Unreleased`.

Prepare the final 2.0.0 release-note section now, before RC freeze.

Requirements:

- version identity = 2.0.0;
- consolidate the existing Unreleased material without losing material AP-SRV-070 changes;
- no invented claims;
- no need for another source mutation merely to publish W6;
- do not guess a future public publication date if it would become inaccurate;
- preserve a clean future `Unreleased` section if consistent with repository conventions.

The actual GitHub Release publication timestamp belongs to W6 and must not force a source change after W5 qualification.

---

# 14. Documentation and archive

Follow `docs/.archiv/README.md`.

Before implementation, create a dated W5-R01 plan in the existing AP-SRV-070 archive.

After implementation, create the corresponding Soll/Ist implementation comparison and document material deviations separately where required.

Update public authorities so they accurately describe:

- W5/W6 split;
- `release.py`;
- no-wasted-version invariant;
- resumable same-version publication;
- fixed W6 order;
- late Git tag;
- GitHub Actions;
- Windows + Ubuntu qualification;
- RC manifest / immutable artifact identity.

Do not rewrite historical archive documents to pretend old plans said this.

Do not add private VPS/selfhost release details to public documentation.

---

# 15. Future W5-R02 qualification contracts

Do not execute these in W5-R01, but design the tooling so the following W5-R02 phase can execute them without source modification.

W5-R02 will require:

## Source / CI
- exact RC commit/tree freeze;
- clean source;
- complete unit/guard suite;
- GitHub Actions green on exact RC;
- no unexpected skips/failures.

## Python distribution
- final wheel + sdist;
- hashes;
- twine check;
- clean Windows fresh install;
- clean Ubuntu 24.04 fresh install;
- no editable/source dependency;
- imports/version/scripts/assets/pip check.

## Kroko
- Free artifact identity/fingerprint;
- Pro artifact identity/fingerprint;
- verified reuse;
- no unexpected native rebuild;
- runtime key not build identity.

## Production images
- exact RC Free image;
- exact RC Pro image;
- Ubuntu 24.04 / linux-amd64;
- correct OCI version/revision;
- non-root;
- no source checkout;
- no secrets;
- no large STT models;
- health/NOT_READY;
- persistence/recreate;
- graceful SIGTERM.

## Mandatory live E2E engine matrix

W5-R02 must run real audio through:

1. **Faster-Whisper**
2. **Kroko Free**
3. **Kroko Pro**

For each:

```text
real audio
→ Protocol-v2 session
→ engine processing
→ final transcription
→ expected event/log path
→ clean session completion
```

Use a controlled audio fixture with known speech/content and document the expected acceptance policy. Do not require byte-identical transcript wording if that is not a valid ASR contract; define a meaningful deterministic/plausible transcript acceptance criterion.

Kroko Pro secret is runtime-only and must never appear in evidence.

## Model management
- positive model discovery;
- managed-store semantics;
- read-only custom path semantics where applicable;
- explicit refresh/provisioning path;
- persistence;
- no surprise startup downloads.

## Negative/security
- bad/missing API auth;
- admin vs normal-key boundary;
- malformed protocol input;
- invalid settings/model requests;
- Free/Pro mismatch;
- Pro runtime without required secret;
- log/event redaction;
- no secret leakage in artifacts/images/evidence;
- no unexpected downloads.

## Release process qualification
- `release.py` preflight PASS;
- `release.py` dry-run PASS;
- exact operation order;
- same-version resume simulation;
- tag blocked before external verification;
- conflict simulation fails closed.

---

# 16. W5-R01 gates

Use these exact gate IDs in `03_GATE_INDEX.md`.

## Context / governance

- **W5P-G01** Remote start SHA/tree exactly match W4C Root-PASS state.
- **W5P-G02** Dedicated clean worktree established.
- **W5P-G03** W5-R01 archive plan created before implementation.
- **W5P-G04** VERSION remains exactly `2.0.0`.
- **W5P-G05** No public publish/tag/release operation executed.

## Release tool

- **W5P-G06** Canonical `release.py` entry point exists and has usable help/CLI.
- **W5P-G07** Current-version preflight operates on 2.0.0 without version bump.
- **W5P-G08** Dry-run is demonstrably no-publish/no-tag/no-version-mutation.
- **W5P-G09** Fixed publication order is encoded/enforced.
- **W5P-G10** Git tag step cannot precede external artifact verification.
- **W5P-G11** Partial publication state resumes the same product version.
- **W5P-G12** Conflicting pre-existing remote artifact identity fails closed.
- **W5P-G13** Release state binds exact source/package/image identities.
- **W5P-G14** Release state and logs contain no secret values.
- **W5P-G15** State transitions are validated/monotonic/idempotent enough for safe resume.

## GitHub Actions / package

- **W5P-G16** Public GitHub Actions CI workflow exists.
- **W5P-G17** Mandatory Windows + Ubuntu 24.04 / Python 3.12 coverage exists.
- **W5P-G18** CI builds wheel/sdist and validates them with `twine check`.
- **W5P-G19** CI fresh-installs from built wheel, not editable checkout.
- **W5P-G20** CI validates pip dependencies, import/version, console scripts and package assets.
- **W5P-G21** CI exercises relevant unit/guard/release tests.
- **W5P-G22** CI contains no public release/publish action and requires no release secret.

## RC tooling / metadata

- **W5P-G23** Canonical RC manifest format/helper implemented and tested.
- **W5P-G24** RC manifest binds all required immutable identities without secrets.
- **W5P-G25** 2.0.0 release notes finalized without requiring a later W6 source mutation.
- **W5P-G26** Public build/release/testing documentation reflects final W5/W6 contracts.
- **W5P-G27** W5-R01 Soll/Ist archive comparison completed.

## Validation

- **W5P-G28** Targeted release-tool tests PASS.
- **W5P-G29** Package build + `twine check` PASS locally in an appropriate isolated environment.
- **W5P-G30** Local installed-wheel smoke PASS without editable/source rescue.
- **W5P-G31** Full `python -m pytest -q tests/unit` PASS.
- **W5P-G32** `git diff --check` PASS.
- **W5P-G33** Final diff review finds no scope leakage/private infrastructure/publication side effect.
- **W5P-G34** Exactly one local final W5-R01 source commit produced, workspace clean, no push performed.

Every gate must be PASS/FAIL/BLOCKED/N/A with concrete evidence. N/A requires a real justification and is not acceptable for a mandatory contract merely because it is difficult.

---

# 17. Test expectations

Add targeted unit/integration-with-mocks tests for release tooling.

At minimum test:

- current VERSION used unchanged by preflight/dry-run;
- release ordering;
- state transition validation;
- resume after each partial state;
- mismatched version/state rejection;
- mismatched source commit/tree rejection;
- mismatched wheel/sdist identity rejection;
- mismatched image identity rejection;
- remote conflict handling;
- Git tag barrier;
- GitHub Release barrier;
- dry-run no side effects;
- secret redaction;
- corrupted/incomplete state handling;
- repeat invocation/idempotent behavior.

Do not use real public publishing as a test.

Also run:

`python -m pytest -q tests/unit`

and:

`git diff --check`

Record exact counts and exit codes.

---

# 18. Evidence requirements

Every raw evidence text file starts with:

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

No secrets.

## `01_RUN_CONTEXT.md`

Include:

- Run ID/model/session
- start time
- repo/worktree
- expected/actual start commit and tree
- local branch
- remote branch state
- tool versions
- binding W5 decisions
- prompt source/copy SHA256

## `02_IMPLEMENTATION_REPORT.md`

Table:

| Area | Files | Before | Change | Why | Gate |
|---|---|---|---|---|---|

Then concise architecture explanations:

- release CLI
- state/resume model
- version preservation
- publication ordering
- CI
- package fresh-install strategy
- RC manifest
- release notes
- future W5-R02 handoff
- deliberate non-changes

## `03_GATE_INDEX.md`

| Gate | Status | Short proof | Evidence | Command/Test | Result |
|---|---|---|---|---|---|

Exactly W5P-G01 through W5P-G34.

## `04_DEVIATIONS.md`

If none:

`Keine bekannten W5-R01-Abweichungen.`

Otherwise document Soll/Ist/cause/impact/decision/gate effect.

## `05_FINAL_REPORT.md`

Must say:

`READY FOR ROOT REVIEW`

or:

`NOT READY FOR ROOT REVIEW`

Never self-award Root PASS.

---

# 19. Final Git handling

Before final commit:

- full tests complete;
- diff review;
- `git diff --check`;
- confirm no generated release state, credentials, artifacts, logs or caches staged.

Create **exactly one** local final W5-R01 source commit.

Suggested message:

`AP-SRV-070 W5: prepare release candidate qualification`

Then:

- record final commit SHA;
- record final tree SHA;
- verify clean workspace;
- fetch origin again;
- verify Distributed is still `e5f76bf1e4fd28e68624f30140fcf8ec6876db96`;
- **DO NOT PUSH**.

If remote changed, STOP and report.

The coordinator will perform Root Review from the submitted run archive and local-commit evidence. Push is separately authorized only after Root PASS.

---

# 20. Stop conditions

STOP rather than broadening architecture if:

- start SHA/tree mismatch;
- worktree cannot be safely established;
- requirement would require redesign of a closed product authority;
- safe same-version resume cannot be implemented without materially changing the agreed release model;
- a real public write is required to prove a W5-R01 gate;
- secret value would need to be stored/exposed;
- a product bug outside W5-R01 release-infrastructure scope is found;
- remote Distributed changes before finalization.

On STOP:

- no speculative redesign;
- document blocker/evidence;
- `NOT READY FOR ROOT REVIEW`.

---

# 21. Success state

W5-R01 succeeds when:

```text
W4C approved source
→ release.py implemented
→ same-version resumable state machine
→ late-tag publication safety
→ GitHub Actions Windows + Ubuntu
→ package fresh-install qualification path
→ RC manifest authority
→ final 2.0.0 release notes
→ release docs
→ targeted + full tests PASS
→ exactly one local source commit
→ no public release
→ no push
→ READY FOR ROOT REVIEW
```

W5-R01 must leave the project ready for a separate, frozen, source-immutable W5-R02 RC qualification.
