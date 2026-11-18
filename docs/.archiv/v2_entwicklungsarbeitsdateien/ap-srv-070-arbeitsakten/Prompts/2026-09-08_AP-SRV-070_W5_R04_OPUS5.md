# AP-SRV-070 / W5 — Final Release-Infrastructure Rebaseline
## W5-R04 — GitHub-Native Build, Qualification & Publication + Documentation Rebaseline
### Model: Claude Opus 5

---

# 0. Run identity

- **Project:** AP-SRV-070
- **Phase:** W5 — Release Infrastructure / Final Release Candidate Preparation
- **Run:** W5-R04
- **Model:** Claude Opus 5
- **Session:** NEW SESSION
- **Repository:** `marcosudau-vps/voice-stt-server`
- **Session/project start folder:** `P:\GithubRepos\marcosudau-vps\voice-stt-server`
- **Binding remote source branch:** `feat/einheitliche-triggerarchitektur-distributed`
- **Binding start commit:** `934e3be7c78aa9358f9b42b9fa4dc282bed54d6c`
- **Binding start tree:** `2936f70ca44b7a902e1e5c7c5ca69eacc3154fdb`
- **Direct parent of start commit:** `7f1ad1f02da9b1c4e3bf226f2a056066921ef77a`
- **Product version:** `2.0.0`
- **Suggested NEW workspace:** `P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-070-w5-r04`
- **Suggested local branch:** `work/ap-srv-070-w5-r04`
- **Prompt source:** `P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Prompts\2026-09-08_AP-SRV-070_W5_R04_OPUS5.md`
- **Run/evidence root:** `P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W5-R04\`
- **Push:** FORBIDDEN until external Root Review explicitly grants ROOT PASS.
- **Tag / GitHub Release / PyPI / Docker Hub / public GHCR:** FORBIDDEN in this run.

This is one large, deliberate implementation run.

The goal is to finish the release infrastructure correctly in one pass, not to create an open-ended sequence of redesigns.

---

# 1. Why this run supersedes the previous W5-R03-E1 evidence-completion attempt

A Gemini W5-R03-E1 evidence-completion run was started after W5-R03 Root Review found three evidence/accounting gaps.

That run is now superseded by a more fundamental release-infrastructure decision:

> VoiceSTT releases must be buildable and orchestrated from GitHub without requiring prebuilt artifacts or a local operator machine as part of the release authority.

Therefore:

- do not depend on W5-R03-E1 as completion authority;
- do not ask the operator for the old E1 repo variables merely to satisfy that superseded preflight;
- do not merge any source changes from that Gemini run;
- prior W5-R03 evidence remains useful historical qualification evidence only;
- G30/G31/G50 from W5-R03 will be re-qualified after this new release infrastructure exists.

This run does **not** invalidate the technical findings already established for the frozen product behavior. It changes release infrastructure and documentation.

---

# 2. External decision — one-run objective

Implement, in one coherent source change:

1. a **GitHub-native release artifact build path**;
2. a **GitHub-native qualification/publish orchestration**;
3. no dependency on Marco's PC or a pre-populated local Kroko artifact store;
4. exact artifact identity preservation from qualification to publication;
5. Free + Pro production image support;
6. PyPI + Docker Hub + GHCR + GitHub Release publication with resumable/fail-closed semantics;
7. Git tag after all deterministic qualification gates but before the first irreversible public package/registry publication;
8. GitHub Release as the last public success marker;
9. robust immutable exact tags plus late-moving aliases;
10. preserve/improve the existing VoiceSTT release state machine rather than replacing it with ad-hoc workflow shell logic;
11. completely rewrite the project README from scratch;
12. remove obsolete/non-product engine documentation;
13. retain only Faster-Whisper and Kroko-ONNX engine guides and move them directly under `docs/`.

The implementation must be narrow to release/build/docs surfaces.

Do not reopen already-closed product architecture.

---

# 3. Reference implementation: admin_portal_workspaces

The existing repository:

`https://github.com/marcosudau-vps/admin_portal_workspaces`

is the reference for the **release philosophy**, not a source to copy blindly.

Its good properties include:

- CI on the exact release-candidate SHA;
- release tag only after deterministic tests/build/CI;
- GitHub Actions performs publishing;
- Docker Hub is mandatory;
- GHCR uses GitHub's `GITHUB_TOKEN`;
- exact Docker Hub image is published first;
- `docker buildx imagetools create` promotes the exact manifest to GHCR instead of rebuilding;
- digest equality is verified;
- movable aliases are created only after exact artifacts exist in both registries;
- GitHub Release is created last;
- incomplete releases resume under the same version;
- exact SemVer tags are never silently overwritten;
- third-party GitHub Actions are pinned to immutable commit SHAs.

VoiceSTT already has stronger properties that MUST NOT be lost:

- explicit RC manifest;
- exact source commit + tree identity;
- wheel/sdist SHA256 binding;
- Kroko Free/Pro fingerprint and artifact SHA256 authority;
- separate Free/Pro production image identities;
- explicit state machine;
- `MATCH / ABSENT / CONFLICT / UNKNOWN`-style fail-closed remote verification;
- verification before write and post-write verification;
- same-version resume;
- conflict = STOP, never overwrite;
- dry-run and real publication share the same operation graph;
- no public version bump just because a publication step failed.

The target is:

> admin_portal_workspaces publication strengths + VoiceSTT's stronger identity/state semantics.

---

# 4. Hard anti-loop boundary

This is intended to be the last release-infrastructure implementation pass.

Do not spend time on unrelated improvements.

After this run the expected path is:

```text
W5-R04 implementation
→ external Root Review
→ exact push if Root PASS
→ GitHub CI on exact commit
→ GitHub clean-runner qualification/build mode
→ external final qualification review
→ W5 COMPLETE
→ W6 publication
```

Do not manufacture follow-up work for:

- stylistic preferences;
- optional abstractions;
- speculative robustness;
- unrelated product architecture;
- historical docs cosmetics;
- source engines not requested here.

A follow-up coding run is justified only by a concrete reproducible release blocker.

---

# 5. Closed product areas — DO NOT reopen

Unless a direct, reproducible blocker in the release infrastructure forces a tiny compatibility correction, do not modify:

- Trigger / Activation architecture
- Commands / Timer
- Protocol-v2 semantics
- Settings architecture
- Wake Word architecture
- STT session architecture
- model-management semantics
- canonical structured-event store semantics
- client architecture
- FastAPI protocol shape
- unrelated server runtime behavior
- private VPS deployment
- `build/vps/*`

No feature redesign.

No broad source engine redesign.

No removal of transcription-engine implementation modules in this run merely because their public documentation is being removed.

---

# 6. Governance: plan before edit

Before the first tracked edit:

1. `git fetch origin`
2. prove remote Distributed:
   `934e3be7c78aa9358f9b42b9fa4dc282bed54d6c`
3. create the new worktree directly from that exact commit;
4. prove:
   - HEAD exact;
   - tree exact;
   - VERSION `2.0.0`;
   - workspace clean;
5. inventory current release/build/docs surfaces;
6. write:
   `02_IMPLEMENTATION_PLAN.md`
   under the external evidence root;
7. only then make tracked edits.

The evidence must contain literal pre-edit `git status --porcelain` output.

Editing before the plan is a mandatory-gate failure.

---

# 7. Current source facts you must preserve/understand

## 7.1 Production identities

The two product image names are authoritative:

```text
free -> voice-stt-server
pro  -> voice-stt-server-pro
```

Free/Pro is a build-time identity and MUST NOT be inferred from a runtime Kroko key.

## 7.2 Kroko build authority

The source-controlled Kroko build inputs already include:

- upstream repo:
  `https://github.com/kroko-ai/kroko-onnx.git`
- immutable upstream revision:
  `8657e655192623b98d7708e742a72987f953d3a2`
- source-controlled patch/build revisions;
- explicit Linux Free/Pro capability switch:
  `KROKO_LICENSE=OFF/ON`

Important:

> The Pro build does NOT require a runtime Pro license key.

The runtime secret is separate and is only required for Pro runtime qualification/use.

The existing standalone builder:

`build/kroko-builder.Dockerfile`

can build Linux/AMD64 Kroko from a fresh environment.

The existing production orchestrator:

`tools/build_production.py`

already follows the conceptual path:

```text
VoiceSTT source
→ VoiceSTT wheel
→ resolve Kroko fingerprint
→ REUSE verified artifact if available
→ otherwise BUILD ONCE
→ copy verified Kroko wheel into build context
→ build production image
→ write build manifest
```

A local artifact store is an optimization, not a release prerequisite.

## 7.3 Current release engine

The current state machine is source-controlled under `release_tooling/`.

Real publish and dry-run share the same graph.

Do not replace this with an unrelated second release implementation.

Refactor/extend it so GitHub Actions becomes the execution environment while the state machine remains the canonical release semantics.

---

# 8. New top-level release architecture

The exact workflow split is your implementation decision, but the following behavioral contract is mandatory.

A good implementation may use, for example:

- one workflow with separate qualification and protected publish jobs; OR
- a release-candidate workflow plus a publish workflow.

Choose the simplest design that satisfies all identity/resume requirements.

## Mandatory lifecycle

```text
SOURCE-CONTROLLED EXACT COMMIT
        ↓
clean GitHub-hosted runner
        ↓
build exact candidate artifacts once
        ↓
persist immutable candidate identities
        ↓
qualify those exact artifacts
        ↓
external/operator approval boundary
        ↓
Git tag v2.0.0
        ↓
PyPI exact wheel/sdist
        ↓
Docker Hub exact Free + Pro
        ↓
promote exact OCI manifests to GHCR
        ↓
external verification / digest / OCI identity
        ↓
movable aliases in both registries
        ↓
alias verification
        ↓
GitHub Release
        ↓
final verification
        ↓
COMPLETE
```

No public artifact may be built again after qualification.

Publication consumes the qualified bytes/manifests.

---

# 9. No local release dependencies

A fresh GitHub-hosted Linux runner with:

- repository checkout;
- Docker/buildx;
- normal network access to declared upstream sources;
- GitHub-provided credentials;
- explicitly configured GitHub secrets/variables;

must be able to produce the complete release candidate.

The release must NOT require:

- `P:\...` paths;
- Marco's local Kroko artifact store;
- a local prebuilt wheel;
- a local Docker image;
- local Docker credentials;
- local `voice-stt.env`;
- local model directories merely to build release artifacts;
- local unpublished release state.

Local development may still use those conveniences; release authority must not.

Add regression/guard tests that fail if workflow/build authority gains absolute Windows paths or operator-local dependencies.

---

# 10. Candidate artifacts built on GitHub

The GitHub-native build must create at least:

1. VoiceSTT wheel
2. VoiceSTT sdist
3. Kroko Free Linux/AMD64 wheel
4. Kroko Pro Linux/AMD64 wheel
5. Free production OCI image
6. Pro production OCI image
7. production build manifest(s)
8. canonical release-candidate manifest
9. SHA256 inventory / machine-readable identities

All must bind to:

```text
version = 2.0.0
source commit = exact candidate commit
source tree = exact candidate tree
```

The manifest must bind:

- wheel filename/SHA256;
- sdist filename/SHA256;
- Kroko Free fingerprint + artifact SHA256;
- Kroko Pro fingerprint + artifact SHA256;
- Free image identity/digest;
- Pro image identity/digest;
- source commit;
- source tree;
- CI/workflow run identity where available.

---

# 11. Kroko artifact reuse on GitHub

Do not recompile Kroko on every ordinary run if the fingerprint has not changed.

Implement a GitHub-native reuse mechanism.

Acceptable sources:

- GitHub Actions cache keyed by the full authoritative Kroko fingerprint;
- durable private candidate/staging artifact storage;
- a combination.

Rules:

1. cache is an optimization, never authority;
2. every reused Kroko wheel is revalidated against the existing fingerprint/artifact authority;
3. cache miss must build successfully from source on a fresh runner;
4. no operator-local artifact store;
5. Free and Pro caches/identities must never cross;
6. corrupt/wrong cache entry must be rejected and rebuilt/fail closed;
7. build-effective input changes invalidate reuse exactly as current W4A authority requires.

The first fresh-runner build must work with an empty cache.

---

# 12. Reproducibility hardening

Audit the Linux builder and production Docker bases for mutable/untracked build inputs.

At minimum:

- pin third-party GitHub Actions by full immutable commit SHA;
- pin important base-container identity by digest where practical;
- ensure any build-effective change to Kroko Linux builder authority changes the relevant fingerprint/revision according to existing W4A rules;
- do not silently introduce a builder change that reuses the old fingerprint;
- use a deterministic source-derived build timestamp where necessary to prevent needless image-identity drift on resume/rebuild, if compatible with the existing build contract.

Do not explode this into a months-long hermetic-build project.

The target is:

> a fresh GitHub runner can reproducibly produce/reuse a candidate under source-controlled authority without hidden local inputs.

If full bit-for-bit reproducibility of a native toolchain cannot reasonably be guaranteed, document the exact boundary honestly and ensure the qualified artifact itself becomes immutable publication authority.

---

# 13. Immutable candidate persistence

This is critical.

The candidate artifacts qualified before publication must remain available for publication without rebuilding.

Choose a robust implementation.

Preferred pattern for large OCI images:

```text
private GHCR staging package
identified by source commit + exact digest
```

for example conceptually:

```text
ghcr.io/marcosudau-vps/voice-stt-server-staging:<candidate-id>
ghcr.io/marcosudau-vps/voice-stt-server-pro-staging:<candidate-id>
```

Staging must remain private and must not be presented as a public release.

An OCI archive stored as GitHub Actions artifact is acceptable if size/reliability make it clearly better, but justify the choice.

For wheel/sdist/Kroko wheels, GitHub Actions artifacts are acceptable.

Candidate persistence requirements:

- exact SHA/digest recorded;
- candidate manifest itself persisted;
- publication can locate the exact qualified candidate;
- resume does not silently build a replacement candidate;
- ambiguity between multiple candidate runs fails closed;
- old candidate cannot be confused with current source commit/tree;
- artifact retention assumptions documented.

---

# 14. Approval boundary

There must be an explicit barrier between:

```text
build + qualification
```

and:

```text
first irreversible public publication
```

Preferred implementation:

- GitHub Environment with required approval for the publication job; OR
- separate publish dispatch that requires exact candidate run/manifest identity.

The workflow itself must make it impossible for a normal CI push to publish.

A pull request from an untrusted fork must never receive release secrets or package-write authority.

Document operator setup if GitHub UI configuration is required.

---

# 15. Tag timing — change current VoiceSTT order

The previous VoiceSTT graph intentionally created the Git tag after PyPI/registries.

That decision is superseded.

New rule:

> The Git tag is created only after every deterministic build/test/qualification/preflight gate has passed, but BEFORE the first irreversible public package/registry publication.

Rationale:

Once `2.0.0` exists on PyPI or a registry, the version is already publicly reserved. The immutable Git tag should exist as the source identity anchor during any partial publication.

Therefore target publication state sequence should conceptually become:

```text
PREPARED
→ TAGGED
→ PYPI_PUBLISHED
→ DOCKERHUB_PUBLISHED
→ GHCR_PUBLISHED
→ EXTERNAL_VERIFIED
→ ALIASES_PUBLISHED
→ GITHUB_RELEASED
→ FINAL_VERIFIED
→ COMPLETE
```

Exact state names may differ if a migration-compatible naming is cleaner, but semantics/order must match.

The tag itself must point to the exact qualified source commit.

No source modification after qualification and before tag.

---

# 16. Same-version resume

Retain and strengthen VoiceSTT's existing resume semantics.

Example:

```text
v2.0.0 created
PyPI succeeded
Docker Hub failed
```

Next attempt:

```text
verify v2.0.0 points to exact expected commit
verify PyPI exact wheel/sdist hashes
resume same 2.0.0
complete Docker Hub
complete GHCR
...
```

Never:

```text
2.0.0 partially failed
→ generate 2.0.1
```

Similarly:

- Docker Hub succeeded / GHCR failed → keep Docker Hub, resume GHCR;
- registries succeeded / GitHub Release failed → keep artifacts, create only missing Release after re-verification;
- exact remote artifact exists with wrong identity → `CONFLICT`, hard STOP;
- remote state cannot be verified reliably → `UNKNOWN`, hard STOP;
- do not delete/rewrite remote artifacts automatically;
- no force-push;
- no tag movement.

---

# 17. PyPI

VoiceSTT adds a release surface not present in the admin_portal_workspaces reference.

Prefer **PyPI Trusted Publishing / GitHub OIDC** over a long-lived PyPI API token.

Desired security model:

- dedicated release workflow;
- `id-token: write` only on the job that requires it;
- PyPI project trusts this exact GitHub repository/workflow/environment;
- no PyPI token stored in the repository;
- exact qualified wheel/sdist bytes are uploaded;
- pre-publish remote verification:
  - ABSENT -> publish;
  - exact matching files/hashes -> resume;
  - conflicting file/version -> STOP;
- post-publish verify exact filenames and SHA256.

If Trusted Publishing cannot be integrated without breaking the one-engine/state-machine authority, design a clean workflow adapter boundary that keeps the release state graph canonical.

Do not fall back to a permanent token merely because it is easier unless there is a concrete documented technical blocker.

---

# 18. Docker Hub

Official namespace:

```text
marcosudau
```

Final repositories:

```text
marcosudau/voice-stt-server
marcosudau/voice-stt-server-pro
```

The workflow should require:

```text
DOCKERHUB_USERNAME = marcosudau
DOCKERHUB_TOKEN     = secret
```

Prefer `DOCKERHUB_USERNAME` as a GitHub repository/environment variable, not a secret.

The PAT needs publish capability; do not require Delete.

The workflow must not print the token.

No Docker-Hub push in this implementation run.

---

# 19. GHCR

Final roots:

```text
ghcr.io/marcosudau-vps/voice-stt-server
ghcr.io/marcosudau-vps/voice-stt-server-pro
```

Use GitHub Actions' `GITHUB_TOKEN` when possible.

Use minimal job permissions:

```text
packages: write
contents: write   # only where tag/release requires it
```

Do not use a separate long-lived GHCR PAT unless a documented platform limitation makes it necessary.

Derive:

```text
ghcr.io/${{ github.repository_owner }}
```

where reasonable rather than requiring a redundant operator variable.

---

# 20. Registry exact-image promotion

For each variant:

```text
qualified exact OCI candidate
→ Docker Hub exact version tag
→ verify
→ copy/promote SAME manifest by digest to final GHCR
→ verify
→ compare digest/OCI identity
```

Do not run an independent second production build for GHCR.

For `2.0.0`:

```text
Docker Hub:
marcosudau/voice-stt-server:2.0.0
marcosudau/voice-stt-server-pro:2.0.0

GHCR:
ghcr.io/marcosudau-vps/voice-stt-server:2.0.0
ghcr.io/marcosudau-vps/voice-stt-server-pro:2.0.0
```

The exact version tags are immutable release identities.

If an exact tag exists and does not match:
STOP.

Never silently repoint it.

---

# 21. Movable container aliases

After all exact Free/Pro artifacts in both registries have been verified, publish movable aliases.

For version `2.0.0`:

```text
2.0
2
latest
```

for BOTH:

- Free image;
- Pro image;
- Docker Hub;
- GHCR.

Rules:

- exact `2.0.0` is immutable;
- aliases may move on future compatible releases;
- aliases are updated only after exact artifacts are verified in both registries;
- `latest` must never point to an RC, failed release or incomplete release;
- verify every alias digest after setting it;
- GitHub Release is created only after aliases are correct.

Implement generic SemVer behavior:

- `0.x.y`: exact + minor + latest, no broad `0` alias;
- `1.x.y` and above: exact + minor + major + latest.

---

# 22. GitHub Release

GitHub Release is the last public success marker.

Only create it after:

- tag exists and points to exact source;
- PyPI exact artifacts verified;
- Docker Hub Free/Pro exact artifacts verified;
- GHCR Free/Pro exact artifacts verified;
- registry digests/OCI metadata verified;
- movable aliases updated and verified.

Use generated notes or release notes according to current project authority.

The release must identify version `2.0.0` and tag `v2.0.0`.

No GitHub Release in this implementation run.

---

# 23. GitHub Actions security

Apply least privilege.

Requirements:

- CI jobs: read-only unless artifact/cache upload requires specific ordinary Actions capability;
- candidate/staging package job: `packages: write` only where required;
- tag/GitHub Release job: `contents: write` only where required;
- PyPI trusted publish: `id-token: write` only on PyPI publish job;
- no release secrets on PR jobs;
- no `pull_request_target` release path;
- no untrusted checkout followed by secret-bearing execution;
- pin third-party actions to full commit SHAs;
- concurrency prevents two release publications for the same version from racing;
- logs never echo secret values;
- shell uses strict failure mode where appropriate;
- no secret values in command-line arguments when avoidable.

---

# 24. GitHub UI/operator configuration document

Add/update release documentation with an exact setup checklist.

The final design should minimize required repository configuration.

Expected operator-side settings should be approximately:

## Repository variable

```text
DOCKERHUB_USERNAME=marcosudau
```

Any additional repo roots should be derived automatically when safe.

## Repository secret

```text
DOCKERHUB_TOKEN=<write-capable Docker Hub PAT>
```

## Optional/qualification secret

If GitHub-hosted Pro live qualification is implemented:

```text
VOICESTT_KROKO_ONNX_KEY=<runtime-only key>
```

This is NOT a build secret.

## PyPI

Document exact Trusted Publisher configuration:

- GitHub owner
- repository
- workflow filename
- optional protected environment name

## GitHub Environment

If using an approval environment, document:

- environment name;
- required reviewer/approval purpose;
- which secrets belong there;
- which job is gated.

Do not require the operator to set both a namespace variable and a redundant full registry-root variable if the workflow can derive the latter safely.

---

# 25. CI responsibilities

Existing public CI:

- Windows
- Ubuntu 24.04
- Python 3.12

must remain green.

Improve CI/release-workflow static tests where useful, but do not turn normal CI into an expensive full native Kroko rebuild on every push.

Normal CI must NOT publish.

Add release infrastructure guard tests for:

- workflow trigger safety;
- minimal permissions;
- pinned third-party actions;
- no public writes in qualification mode;
- correct state order;
- tag before public artifact publication;
- GitHub Release last;
- Docker Hub before GHCR manifest promotion;
- Free/Pro both mandatory;
- alias mapping;
- 0.x no broad `0` alias;
- exact SemVer tag immutability;
- same-version resume;
- conflict/unknown fail closed;
- no local absolute path dependency;
- candidate artifact identity binding.

---

# 26. GitHub-native qualification mode

The new infrastructure must support a no-publication qualification run on GitHub for an exact source commit.

It must be possible after this implementation is pushed to run GitHub Actions and prove:

```text
fresh runner
→ source checkout
→ build wheel/sdist
→ build/reuse Kroko Free/Pro using source authority
→ build Free/Pro production images
→ produce candidate manifest
→ package/image smoke
→ no public release/tag/PyPI/DockerHub/final GHCR writes
```

Private staging writes are acceptable only if they are explicitly qualification staging, access-controlled and not final/public release surfaces.

Qualification mode must emit enough artifacts/manifests for external Root Review.

A failed qualification must not consume version `2.0.0`.

---

# 27. README — COMPLETE REWRITE, not incremental editing

`README.md` must be rewritten from scratch.

Do not preserve the current prose structure and merely patch obsolete sentences.

The new README should accurately present the current project to a new user in a polished, concise, useful way.

It must be based on current source and authoritative docs, not historical claims.

At minimum cover:

1. what VoiceSTT is;
2. current release/status positioning;
3. supported production STT engines:
   - Faster-Whisper
   - Kroko-ONNX
4. concise Free vs Pro Kroko distinction;
5. installation paths;
6. minimal Python example;
7. external audio;
8. server use;
9. Protocol-v2/current server API at a useful high level;
10. model management / offline production model behavior;
11. Docker/production images;
12. Free/Pro image identities;
13. build/release model at a high level;
14. links to current docs;
15. development/testing pointers;
16. licensing/security notes where relevant.

Requirements:

- no claims that unsupported/removed engines are production-supported;
- no links into `docs/engines/`;
- no stale local-VPS-centric path as the public default;
- private VPS deployment may be linked only as private/server-specific documentation if appropriate;
- do not expose secrets;
- do not invent PyPI/Docker/Release URLs that are not yet actually public;
- no fake badges for unpublished surfaces;
- GitHub links must point to real repository paths;
- use understandable English unless current project authority clearly requires another language;
- README should stand on its own as the project's public front door.

The final diff should show the README as a substantive full rewrite.

---

# 28. Engine documentation cleanup

The public/current engine documentation surface is to be reduced to the two intended production STT engines.

## Keep and MOVE

```text
docs/engines/faster-whisper.md
→ docs/faster-whisper.md

docs/engines/kroko-onnx.md
→ docs/kroko-onnx.md
```

Preserve useful content, but update links/claims where needed.

## Remove current docs for other engine families

Delete the remaining files under:

`docs/engines/`

and remove the directory entirely after the two retained guides are moved.

This includes current docs such as:

- cohere
- funasr
- hf-transformers
- moonshine
- omnilingual-asr
- openai-whisper
- parakeet-nemo
- sherpa-onnx
- whisper-cpp
- any other non-Faster-Whisper/non-Kroko file present there

Do not move them elsewhere.

## Current documentation references

Search all maintained/current documentation and update/remove links and claims.

At minimum inspect:

- `README.md`
- `docs/README.md`
- `docs/transcription-engines.md`
- `docs/configuration.md`
- `docs/quick-start.md`
- `docs/fastapi-server.md`
- `docs/testing.md`
- `docs/troubleshooting.md`
- `docs/licenses.md`
- build docs
- package metadata/docs links

`docs/transcription-engines.md` may remain as a concise overview, but it must describe only the intended current supported production engines and link to:

```text
docs/faster-whisper.md
docs/kroko-onnx.md
```

## Historical archive

Do NOT rewrite historical references under:

`docs/.archiv/`

merely because they mention old engines.

Historical archive is historical evidence.

Only modify archive files if project process explicitly requires a NEW dated plan/Soll-Ist entry for this W5-R04 change.

---

# 29. Important source/docs distinction

The current source tree may still contain lazy-loaded legacy/experimental transcription-engine adapters in `VoiceSTT/transcription_engines/`.

This run's explicit user request is to clean the **current documentation/product surface**, not to perform a broad source-engine purge.

Therefore:

- do not delete engine implementation modules merely because docs are removed;
- do not rewrite the engine factory in a broad cleanup;
- do not create a large compatibility break unrelated to release infrastructure.

If source APIs still expose names beyond Faster-Whisper/Kroko, document the truth carefully:

- Faster-Whisper and Kroko-ONNX are the supported/qualified production engine surface;
- legacy/internal adapters need not be advertised in public current docs.

If existing tests/docs make that distinction impossible without a real contradiction, record the issue and make the smallest safe correction only if necessary.

---

# 30. Project-process documentation

Follow `AGENTS.md` and `docs/.archiv/README.md`.

This is a larger cross-cutting release/deployment/documentation change.

Before implementation, create the required dated AP-SRV-070 plan entry if the current process requires it.

After implementation, create the required dated Soll/Ist review.

Do not rewrite old archive records.

Material deviations from this prompt require a separate dated rationale.

Update current authoritative docs such as:

- `build/BUILD.md`
- relevant release/releasing documentation
- `docs/README.md`
- any new GitHub-native release guide

Do not modify `build/vps/*` unless a broken public-doc reference requires a minimal link correction.

---

# 31. Release-engine integration requirements

The current release graph is not merely documentation.

Update implementation and tests so real semantics match the new order.

The result must still have one canonical state/operation graph for:

- dry-run planning;
- real publication;
- resume.

Do not create:

```text
release.py says one order
workflow shell says another order
docs say a third order
```

The workflow should call/use the release tooling or consume a machine-readable release plan produced by it.

If a GitHub Action (e.g. PyPI Trusted Publishing action) must perform a write that Python cannot directly perform under OIDC, introduce a clean explicit adapter/executor boundary while keeping the state machine authoritative.

State transitions must be based on verified external state, not merely successful command exit.

---

# 32. Build-date / identity issue

Current production build uses a current wall-clock `BUILD_DATE`.

That can make two builds of the same source differ in metadata.

Because publication must use the already-qualified exact candidate, this is not automatically fatal.

Still, evaluate whether build timestamp should be source-derived (e.g. commit timestamp / `SOURCE_DATE_EPOCH`) for stronger reproducibility and resume safety.

If changed:

- update tests;
- update manifest semantics;
- preserve OCI `created` correctness;
- do not break W4C contracts.

Do not change it casually without recording the reason.

---

# 33. No public writes during W5-R04

The Agent may:

- run local Docker builds;
- use local temporary artifacts;
- validate workflow YAML;
- run unit/full regression tests;
- simulate release adapters with fakes;
- perform read-only remote checks.

The Agent must NOT:

- create Docker Hub repositories;
- push Docker Hub images;
- create final GHCR packages;
- create public GHCR tags;
- upload to PyPI;
- create Git tag;
- create GitHub Release;
- push the implementation commit;
- change canonical/main.

Private staging should also NOT be pushed during this local implementation run.

Its GitHub execution is tested after external Root PASS and exact push.

---

# 34. Tests — mandatory

At minimum run:

## Release tooling targeted

All release-tooling/unit tests, including new tests for:

- new state order;
- tag before first public publication;
- PyPI after tag;
- Docker Hub before GHCR;
- GHCR exact-manifest promotion;
- GitHub Release last;
- alias order;
- alias mapping for 0.x and >=1.x;
- Free + Pro exact identities;
- resume from each partial state;
- conflict fail-closed;
- unknown/unavailable fail-closed;
- exact tag immutability;
- no version bump on resume;
- dry-run zero writes;
- dry-run and real mode same graph;
- candidate manifest identity;
- local-path guard;
- GitHub workflow contract.

## Build tooling

Tests for:

- fresh empty Kroko artifact/cache path can trigger build path;
- validated reuse;
- Free/Pro separation;
- source-controlled fingerprint invalidation;
- GitHub-runner-compatible paths;
- production manifests bind source commit/tree/version.

## Workflow validation

- YAML parse;
- triggers;
- permissions;
- concurrency;
- pinned Actions;
- no publish on normal push/PR;
- qualification mode has zero public writes;
- publish mode has explicit approval/dispatch boundary;
- required credentials checked before public publication;
- GITHUB_TOKEN used for GHCR;
- no runtime Kroko key used as build input.

## Documentation/link validation

- no maintained link to `docs/engines/...`;
- `docs/engines` directory removed;
- `docs/faster-whisper.md` exists;
- `docs/kroko-onnx.md` exists;
- no maintained current docs advertise removed engine guides/product support;
- README links resolve to repository files;
- README contains no private secret/path leakage.

## Regression

Run the complete unit/regression suite on Windows.

Run the complete unit/regression suite on Ubuntu 24.04/WSL if practical using the already established native ext4 qualification approach.

A release-infrastructure/docs change should not regress product behavior.

Record exact counts.

## Diff checks

- `git diff --check`
- repository secret scan appropriate to existing project tooling
- no tracked build outputs
- no accidental large binaries
- no `.env`

---

# 35. GitHub-clean-runner feasibility proof

Because the new workflow cannot be executed on GitHub until the commit is pushed, provide a local structural proof in this run.

At minimum:

1. use a fresh/empty local artifact-store directory;
2. build/resolve Kroko Free and Pro through the same source-controlled path the workflow will use;
3. build wheel/sdist;
4. build Free/Pro production images;
5. create the same candidate manifest shape;
6. ensure no local pre-existing artifact is required for success;
7. record all hashes/fingerprints/image IDs;
8. no public writes.

If doing two full native Kroko builds locally is prohibitively expensive but existing source-level tests plus one true empty-store build provide strong coverage, document the exact limitation. Do not fake an empty-store proof.

After push, GitHub qualification mode will be the authoritative clean-runner proof.

---

# 36. Evidence structure

Create:

```text
W5-R04\
├── 00_PROMPT.md
├── 01_PREFLIGHT.md
├── 02_IMPLEMENTATION_PLAN.md
├── 03_REFERENCE_COMPARISON.md
├── 04_ARCHITECTURE_DECISION.md
├── 05_CHANGED_FILES.md
├── 06_TEST_MATRIX.md
├── 07_GATE_INDEX.md
├── 08_DEVIATIONS.md
├── 09_FINAL_REPORT.md
└── Evidence\
    ├── 00_PreEdit\
    ├── 01_ReleaseEngine\
    ├── 02_Workflows\
    ├── 03_GitHubNativeBuild\
    ├── 04_KrokoFreshBuild\
    ├── 05_CandidateManifest\
    ├── 06_DockerImages\
    ├── 07_Documentation\
    ├── 08_WindowsRegression\
    ├── 09_UbuntuRegression\
    ├── 10_Security\
    ├── 11_Diff\
    └── 12_FinalGit\
```

Copy prompt byte-identically to `00_PROMPT.md` and record source/copy SHA256.

---

# 37. Mandatory gates

Use exactly these IDs.

## Governance / identity

- **W5R4-G01** Remote start branch still exact `934e3be7...` before work.
- **W5R4-G02** New workspace starts exact commit/tree.
- **W5R4-G03** VERSION remains `2.0.0`.
- **W5R4-G04** Clean pre-edit status captured literally.
- **W5R4-G05** Implementation plan written before first tracked edit.
- **W5R4-G06** No prior Gemini E1 source changes merged.

## GitHub-native build

- **W5R4-G07** Fresh GitHub-runner architecture has no operator-local artifact dependency.
- **W5R4-G08** Wheel built from source-controlled checkout.
- **W5R4-G09** Sdist built from source-controlled checkout.
- **W5R4-G10** Kroko Free can build/reuse under source-controlled fingerprint authority.
- **W5R4-G11** Kroko Pro can build/reuse without runtime license key.
- **W5R4-G12** Empty-cache/artifact-store build path is real, not assumed.
- **W5R4-G13** Free/Pro cache/artifact identities cannot cross.
- **W5R4-G14** Free production image builds from candidate artifacts.
- **W5R4-G15** Pro production image builds from candidate artifacts.
- **W5R4-G16** Candidate manifest binds exact source/package/Kroko/image identities.
- **W5R4-G17** Qualified candidate can be persisted for publication without rebuild.
- **W5R4-G18** Resume can locate/reuse exact qualified candidate unambiguously.

## Release state / publication

- **W5R4-G19** One canonical state/operation graph remains authority.
- **W5R4-G20** Dry-run and real execution use same graph.
- **W5R4-G21** Tag is after deterministic qualification but before first public artifact.
- **W5R4-G22** PyPI is after tag.
- **W5R4-G23** Docker Hub exact publish precedes GHCR exact promotion.
- **W5R4-G24** GHCR uses same qualified OCI manifest/content, no second production build.
- **W5R4-G25** Exact registry identities are verified post-write.
- **W5R4-G26** Remote conflict hard-stops.
- **W5R4-G27** Unverifiable remote state hard-stops real publication.
- **W5R4-G28** Same-version resume works for partial release states.
- **W5R4-G29** No automatic 2.0.1 after partial 2.0.0 publication.
- **W5R4-G30** Git tag never moves/replaces an existing conflicting tag.
- **W5R4-G31** GitHub Release is last public success marker.
- **W5R4-G32** Final verification precedes COMPLETE.

## Aliases

- **W5R4-G33** `2.0.0` exact tag immutable.
- **W5R4-G34** 2.0 alias supported.
- **W5R4-G35** 2 alias supported for major >=1.
- **W5R4-G36** latest supported.
- **W5R4-G37** 0.x mapping omits broad `0` alias.
- **W5R4-G38** Aliases move only after exact Free/Pro artifacts verified in both registries.
- **W5R4-G39** Alias digests are verified.

## GitHub Actions / security

- **W5R4-G40** Normal CI cannot publish.
- **W5R4-G41** Release publication requires explicit dispatch/approval boundary.
- **W5R4-G42** PR/untrusted code path cannot receive release secrets.
- **W5R4-G43** Third-party Actions pinned to full commit SHA.
- **W5R4-G44** Job permissions are least-privilege.
- **W5R4-G45** GHCR uses GITHUB_TOKEN unless documented hard blocker.
- **W5R4-G46** Docker Hub uses username + write-capable PAT without Delete requirement.
- **W5R4-G47** PyPI uses Trusted Publishing/OIDC unless documented hard blocker.
- **W5R4-G48** Qualification mode performs zero final/public release writes.
- **W5R4-G49** Secret values cannot enter logs/manifests/artifacts.
- **W5R4-G50** Runtime Kroko Pro key is not a build input.

## Documentation

- **W5R4-G51** README fully rewritten from scratch.
- **W5R4-G52** README accurately presents current VoiceSTT public product surface.
- **W5R4-G53** README advertises only Faster-Whisper and Kroko-ONNX as supported production STT engines.
- **W5R4-G54** `docs/faster-whisper.md` exists and is current.
- **W5R4-G55** `docs/kroko-onnx.md` exists and is current.
- **W5R4-G56** `docs/engines/` removed.
- **W5R4-G57** Maintained docs contain no stale `docs/engines/...` links.
- **W5R4-G58** Maintained engine overview contains only current production engine support.
- **W5R4-G59** Historical `docs/.archiv` content not silently rewritten.
- **W5R4-G60** Build/release docs explain GitHub-native process and operator setup.

## Tests / final Git

- **W5R4-G61** Release tooling targeted tests PASS.
- **W5R4-G62** Build/Kroko targeted tests PASS.
- **W5R4-G63** Workflow/YAML/permission/trigger guard tests PASS.
- **W5R4-G64** Documentation/link guard tests PASS.
- **W5R4-G65** Windows full regression PASS.
- **W5R4-G66** Ubuntu 24.04 full regression PASS or a fully evidenced non-source environment block is explicitly reported; READY requires PASS.
- **W5R4-G67** `git diff --check` PASS.
- **W5R4-G68** Secret/large-binary/tracked-artifact scope review PASS.
- **W5R4-G69** Exact full diff archived for Root Review.
- **W5R4-G70** Exactly one final local implementation commit.
- **W5R4-G71** Final commit direct parent is exact `934e3be7c78aa9358f9b42b9fa4dc282bed54d6c`.
- **W5R4-G72** Final workspace literally clean.
- **W5R4-G73** Remote Distributed remains exact `934e3be7...`.
- **W5R4-G74** No push/tag/release/PyPI/DockerHub/public-GHCR write occurred.
- **W5R4-G75** Final report identities and evidence are internally consistent.

All 75 gates are mandatory for `READY FOR ROOT REVIEW`.

No success gate may be silently marked N/A.

---

# 38. Suggested commit

Exactly one local durable implementation commit.

Suggested message:

`AP-SRV-070 W5: finalize GitHub-native release infrastructure`

Do not create separate documentation or cleanup commits.

The README/docs cleanup belongs in the same implementation run/commit because it is part of the final public release surface rebaseline.

Do not push.

---

# 39. Final report

`09_FINAL_REPORT.md` begins exactly:

`READY FOR ROOT REVIEW`

or:

`NOT READY FOR ROOT REVIEW`

Never claim Root PASS.

If READY include:

- start commit/tree;
- final local commit/tree;
- direct parent;
- VERSION;
- full changed-file list;
- architecture summary;
- GitHub workflow names/triggers;
- candidate artifact persistence strategy;
- exact state order;
- credential/operator setup;
- README/docs result;
- exact test counts;
- 75/75 gate result;
- confirmation of zero public writes;
- remote still unchanged;
- workspace clean.

If NOT READY:

- list only concrete blockers;
- classify source/infrastructure/environment/evidence;
- do not create a second speculative solution inside this run.

---

# 40. Final implementation principle

The desired result is:

> A VoiceSTT release is produced from an exact source-controlled Git commit by GitHub-hosted automation. The same candidate bytes and OCI manifests that were qualified are later published without rebuilding. The release has a durable Git identity before the first public package/registry write, resumes safely under the same version after external failures, fails closed on conflicting or unverifiable remote state, publishes both Free and Pro images consistently to Docker Hub and GHCR, publishes wheel/sdist to PyPI, moves aliases only after exact artifacts are verified, and creates the GitHub Release last.

And the public repository front door must tell the truth:

> VoiceSTT's maintained production STT engine documentation is Faster-Whisper and Kroko-ONNX; obsolete engine documentation is removed, the two retained guides live directly under `docs/`, and the README is a complete new presentation of the current project.

Implement that once, thoroughly, and stop.
