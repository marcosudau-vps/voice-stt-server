# AP-SRV-070 / W5 — Frozen Release Candidate Qualification
## W5-R02 — W5-RC1 Full Qualification
### Model: Sonnet 5

---

# 0. Run identity

- **Project:** AP-SRV-070
- **Phase:** W5 — Release Candidate Qualification
- **Run:** W5-R02
- **Internal RC candidate:** `W5-RC1`
- **Product version:** `2.0.0`
- **Model:** Anthropic Sonnet 5
- **Session:** NEW SESSION
- **Repository:** `marcosudau-vps/voice-stt-server`
- **Target integration branch:** `feat/einheitliche-triggerarchitektur-distributed`
- **Frozen RC commit:** `bb7a4bb7cc27897aeb257aa5a5b9f3b550b8f602`
- **Frozen RC tree:** `f7b304b1959e48457a8eefd8919484f55214633b`
- **Direct parent:** `e5f76bf1e4fd28e68624f30140fcf8ec6876db96`
- **Session start folder:** `P:\GithubRepos\marcosudau-vps\voice-stt-server`
- **Dedicated qualification workspace:** `P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-070-w5-r02`
- **Prompt source:** `P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Prompts\2026-09-07_AP-SRV-070_W5_R02_SONNET5.md`
- **Run / evidence root:** `P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W5-R02\`

This run is a **frozen release-candidate qualification**.

The source state is already prepared and externally Root-approved in W5-R01.

This run must prove whether exactly:

- commit `bb7a4bb7cc27897aeb257aa5a5b9f3b550b8f602`
- tree `f7b304b1959e48457a8eefd8919484f55214633b`
- version `2.0.0`

is safe to advance to W6 publication.

---

# 1. Non-negotiable frozen-RC rule

## 1.1 No source modification

W5-R02 is **qualification-only**.

Do not modify source-controlled files.

Do not:

- patch product code;
- patch tests;
- patch release tooling;
- patch CI;
- patch Dockerfiles;
- patch docs;
- patch release notes;
- amend commits;
- create new commits;
- rebase;
- merge;
- tag;
- push;
- publish.

Evidence, temporary build outputs, test environments, downloaded models and generated runtime state must remain outside tracked source or in ignored paths.

If a source-controlled change would be required to make a mandatory gate pass:

> STOP and report `NOT READY FOR ROOT REVIEW`.

That finding will be handled in a separate correction run, creating a new internal RC candidate while product version remains `2.0.0`.

## 1.2 No public release

Forbidden during W5-R02:

- PyPI upload;
- GHCR push;
- Docker Hub push;
- Git tag creation/push;
- GitHub Release;
- any public registry mutation.

`release.py preflight` and `release.py dry-run` are allowed.
`release.py publish` must not be executed against real public services.

## 1.3 No private VPS/selfhost dependency

Public RC qualification must remain portable.

Do not depend on:

- Marcos VPS;
- private domains;
- private Caddy config;
- private selfhost paths;
- private production ports;
- private production model paths;
- private VPS secrets;
- `build/vps/*` operational behavior.

Local Windows `P:\...` paths are orchestration/evidence paths only.

---

# 2. Prepare run file and workspace

Create:

`P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W5-R02`

with:

```text
W5-R02\
├── 00_PROMPT.md
├── 01_RC_CONTEXT.md
├── 02_QUALIFICATION_REPORT.md
├── 03_GATE_INDEX.md
├── 04_DEVIATIONS.md
├── 05_RC_MANIFEST.json
├── 06_FINAL_REPORT.md
└── Evidence\
    ├── 00_RC_Freeze\
    ├── 01_GitHub_Actions\
    ├── 02_Source_Regression\
    ├── 03_Package_Build\
    ├── 04_Fresh_Install_Windows\
    ├── 05_Fresh_Install_Ubuntu\
    ├── 06_Kroko_Free\
    ├── 07_Kroko_Pro\
    ├── 08_Production_Image_Free\
    ├── 09_Production_Image_Pro\
    ├── 10_Live_E2E_FasterWhisper\
    ├── 11_Live_E2E_Kroko_Free\
    ├── 12_Live_E2E_Kroko_Pro\
    ├── 13_Model_Management\
    ├── 14_Runtime_Persistence\
    ├── 15_Graceful_Shutdown\
    ├── 16_Negative_Security\
    ├── 17_Release_Preflight_DryRun\
    └── 18_Final_Git_State\
```

Copy the prompt byte-identically to:

`W5-R02\00_PROMPT.md`

Record source/copy SHA256.

Create the dedicated qualification workspace from exactly the frozen RC commit:

`bb7a4bb7cc27897aeb257aa5a5b9f3b550b8f602`

with a local branch such as:

`work/ap-srv-070-w5-r02`

The workspace must be source-clean before qualification begins.

---

# 3. RC freeze verification

Before doing any qualification:

```text
git fetch origin
git rev-parse origin/feat/einheitliche-triggerarchitektur-distributed
git rev-parse HEAD
git rev-parse HEAD^{tree}
git status --porcelain
```

Expected:

```text
Remote Distributed:
bb7a4bb7cc27897aeb257aa5a5b9f3b550b8f602

Local HEAD:
bb7a4bb7cc27897aeb257aa5a5b9f3b550b8f602

Tree:
f7b304b1959e48457a8eefd8919484f55214633b
```

Also verify:

- `VERSION` resolves to `2.0.0`;
- Release Notes contain the prepared 2.0.0 release section;
- GitHub Actions workflow exists;
- `release.py` exists;
- RC manifest tooling exists.

Any mismatch = STOP.

---

# 4. Read binding authorities

At minimum:

- `AGENTS.md`
- applicable nested `AGENTS.md`
- `build/BUILD.md`
- `docs/testing.md`
- `docs/stt-model-management.md`
- `docs/.archiv/README.md`
- W5-R01 archive material
- `VERSION`
- `RELEASE_NOTES.md`
- `setup.py`
- `MANIFEST.in`
- `release.py`
- `release_tooling/*`
- `.github/workflows/*`
- `tools/build_production.py`
- `Dockerfile`
- `docker-compose.yml`
- Kroko artifact/fingerprint implementation
- model-management implementation/tests
- protocol-v2 tests/authorities
- installed-distribution/package tests

Do not use `build/vps/*` as public release authority.

---

# 5. Qualification philosophy

Do not re-audit closed architectures from first principles.

W5-R02 verifies that the final RC integrates and ships correctly.

Focus on:

```text
Frozen source
→ package artifacts
→ fresh installations
→ qualified Kroko artifacts
→ production images
→ real runtime
→ real protocol/audio/transcription
→ model management
→ negative/security
→ release preflight/dry-run
→ exact RC manifest
```

Closed areas may only be reopened if a reproducible RC blocker is observed.

---

# 6. GitHub Actions qualification

GitHub Actions is mandatory.

The exact RC commit must have a successful CI run for the W5 workflow.

Required:

- Windows job PASS;
- Ubuntu 24.04 job PASS;
- Python 3.12 mandatory path PASS;
- package build PASS;
- `twine check` PASS;
- fresh wheel install PASS;
- `pip check` PASS;
- import/version/script/assets PASS;
- relevant unit/guard/release-tool tests PASS.

Use GitHub's actual run/check data for the exact RC commit.

Do not substitute a local imitation for this gate.

If workflow trigger configuration means no run exists automatically, use only safe workflow invocation mechanisms that do not modify source or publish anything.

No release secret may be required.

Record:

- workflow name;
- run ID;
- commit SHA;
- job IDs;
- conclusions;
- relevant step summaries.

---

# 7. Source regression

Run the complete unit/guard suite from the frozen source.

At minimum:

```text
python -m pytest -q tests/unit
git diff --check
```

Record exact:

- passed;
- skipped;
- subtests;
- failed;
- errors;
- exit codes.

No regression relative to W5-R01-C1 is acceptable without explicit explanation.

Expected baseline from W5-R01-C1:

- `1704 passed`
- `14 skipped`
- `985 subtests passed`
- `0 failed`

If counts change due only to environment-specific skips, explain exactly why.
Do not silently accept unexpected skips.

---

# 8. Build final Python release artifacts

From exact RC source build:

- wheel;
- sdist.

Use isolated PEP-517 build.

At minimum:

```text
python -m build
python -m twine check dist/*
```

Record:

- exact filenames;
- byte sizes;
- SHA256;
- metadata version;
- package name;
- wheel tags;
- sdist identity.

These are final RC package identities.

Do not use editable install.

Inspect artifact contents for inclusion/exclusion boundaries.

Required positive checks include:

- `VoiceSTT`;
- `VoiceSTT_server`;
- `api_fastapi_server`;
- browser static asset;
- wake-word package assets;
- Kroko model authority metadata;
- expected console scripts;
- version resolver.

Required negative checks include:

- no secrets;
- no logs;
- no runtime DB;
- no downloaded STT models;
- no workspaces;
- no build cache;
- no private deployment state;
- no unmanifested historical wake-word package leakage.

---

# 9. Fresh install — Windows 11

Mandatory.

Use a genuinely clean isolated Python environment outside the source checkout.

Install from the built RC wheel only.

No:

- `pip install -e`;
- source path injection;
- `PYTHONPATH` rescue;
- current-working-directory rescue.

Recommended strategy:

- create temp/isolated venv outside repo;
- copy/install wheel from artifact path;
- change CWD away from repository before import/start checks.

Verify:

- `pip check`;
- `import VoiceSTT`;
- `VoiceSTT.__version__ == 2.0.0`;
- server module import;
- console scripts:
  - `stt-server`
  - `stt-server-legacy`
  - `stt`
  - `stt-install-kroko`;
- expected static/package assets resolve from installed distribution;
- server can start from installed package;
- no source checkout dependency.

Record Python/OS versions and exact artifact hash used.

---

# 10. Fresh install — Ubuntu 24.04

Mandatory.

Use Ubuntu 24.04 native/VM/container environment as appropriate, but this must be an installed-distribution proof, not merely importing source through a bind mount.

Python 3.12 mandatory.

Same checks as Windows:

- install exact wheel;
- `pip check`;
- import/version;
- console scripts;
- package assets;
- installed server startup;
- no source rescue.

Record exact environment and artifact hash.

---

# 11. Kroko Free qualification

Use the existing W4A artifact authority.

Requirements:

- resolve exact Linux/AMD64 Free fingerprint;
- artifact exists or is produced only through the existing qualified native-build path;
- prefer verified REUSE;
- record fingerprint;
- record artifact filename;
- record SHA256;
- verify variant = Free;
- verify package/runtime identity;
- verify no Pro key participates in build identity.

If an exact qualified artifact already exists, do not force rebuild.

Unexpected native rebuild without a clear reason = investigate and potentially BLOCK.

---

# 12. Kroko Pro qualification

Same as Free, but variant = Pro.

Requirements:

- exact Pro fingerprint;
- exact artifact SHA256;
- variant identity verified;
- Free and Pro artifact namespaces distinct;
- runtime key not build authority;
- no secret in build evidence.

If Pro artifact requires an existing private runtime credential for a runtime smoke, use runtime secret handling only.
Never write secret value into evidence.

---

# 13. Production Image — Free

Build the final Free production image from the frozen RC source using the public production orchestrator.

Record:

- image tag;
- image ID;
- repo digest if available locally;
- OCI version;
- OCI revision;
- architecture;
- base OS;
- installed VoiceSTT version;
- installed Kroko variant;
- non-root UID/GID;
- build manifest identity.

Required contracts:

- Ubuntu 24.04 runtime;
- linux/amd64;
- VoiceSTT installed from wheel;
- no editable install;
- no source checkout required at runtime;
- Kroko wheel consumed, not compiled inside Production Docker Build;
- no large STT models in image;
- no secrets in image;
- no secrets in history/labels;
- health probe verifies process/control plane only;
- missing STT model = NOT_READY but container healthy;
- no restart loop.

---

# 14. Production Image — Pro

Same public Production Docker contract.

Verify:

- same VoiceSTT source/version as Free;
- Pro Kroko runtime identity;
- product image identity = Pro;
- Free image cannot become Pro merely by setting key;
- runtime credential passed only at runtime;
- no key in image/config/history/evidence;
- all common W4C production contracts remain true.

---

# 15. Mandatory live E2E — controlled audio fixture

Use one or more controlled local audio fixtures with known spoken content.

The fixture must be:

- documented;
- local;
- non-secret;
- deterministic enough for qualification;
- not dependent on live microphone capture.

Define acceptance before running engines.

Do not require exact punctuation/casing if backend output legitimately varies.

Use a meaningful content criterion such as:

- expected key phrase/words present after normalization;
- non-empty final transcription;
- no unrelated/hallucinated output;
- protocol/session lifecycle complete.

Record audio SHA256 and expected normalized phrase.

---

# 16. Live E2E — Faster-Whisper

Mandatory real transcription.

Required path:

```text
server/image or installed release runtime
→ Protocol-v2 connection
→ session configuration
→ real audio fixture
→ Faster-Whisper engine processing
→ final transcription
→ expected transcription event/log evidence
→ clean session completion
```

Must prove:

- actual model loaded;
- actual audio processed;
- actual final transcription returned;
- transcript passes predefined content criterion;
- no fatal server error;
- correct session correlation;
- clean shutdown/close.

Use an already-available appropriately small qualified Faster-Whisper model if present.

If provisioning is required, it must be explicit and controlled.
Do not allow an unexpected startup download.

---

# 17. Live E2E — Kroko Free

Mandatory real transcription.

Use the qualified Free runtime artifact and a valid Free-compatible model.

Required path:

```text
Free production/runtime identity
→ Protocol-v2 session
→ real audio fixture
→ Kroko Free processing
→ final transcription
→ events/logs
→ clean session completion
```

Verify:

- runtime variant really Free;
- model/runtime compatibility;
- no Pro credential needed to establish Free identity;
- transcript passes predefined content criterion;
- no secret leakage.

---

# 18. Live E2E — Kroko Pro

Mandatory real transcription.

Use:

- qualified Pro runtime artifact;
- Pro-compatible model;
- runtime credential only as secret.

Required path:

```text
Pro production/runtime identity
→ runtime secret injected safely
→ Protocol-v2 session
→ real audio fixture
→ Kroko Pro processing
→ final transcription
→ events/logs
→ clean session completion
```

Verify:

- runtime variant really Pro;
- credential is runtime-only;
- secret absent from evidence/logs/state;
- transcript passes predefined content criterion;
- no fallback to Free identity.

If required Pro runtime material/credential is unavailable in the environment, do not fake PASS.
Report BLOCKED with exact missing prerequisite.

---

# 19. Model-management qualification

Do not reimplement W4B.

Verify final RC integration with representative positive and negative flows.

At minimum:

## Positive

- model discovery;
- managed Faster-Whisper store;
- managed Kroko store;
- refresh;
- explicit provisioning path where applicable;
- persisted model availability after recreate;
- expected ownership/writability.

## External/custom path

Where supported:

- read-only custom model source can be discovered/used;
- server does not mutate read-only custom path.

## Download policy

- normal startup does not unexpectedly download large models;
- explicit authorized provisioning may access network as designed;
- failed/interrupted provisioning does not leave a silently accepted corrupt artifact.

---

# 20. Persistence / recreate

Use disposable isolated Docker/Compose resources.

Verify canonical container root:

`/var/lib/voicestt`

and managed model paths:

- `/var/lib/voicestt/models/stt/fasterwhisper`
- `/var/lib/voicestt/models/stt/kroko_asr`

Required:

- state/model probe written by runtime user;
- full container recreate;
- contents persist;
- SHA256 unchanged;
- paths remain writable as expected;
- service remains healthy after recreate.

Do not reuse private production volumes.

---

# 21. Graceful shutdown

Verify real application shutdown, not merely container exit.

Required evidence should include equivalent ASGI/application lifecycle:

```text
Shutting down
Waiting for application shutdown
Application shutdown complete
Finished server process
```

and/or structured `server.stopping` event where applicable.

Also verify:

- reasonable stop duration;
- timeout not exhausted;
- no OOM kill;
- no SIGKILL dependency.

---

# 22. Negative/security qualification

At minimum qualify representative cases for:

## Authentication

- missing API key;
- invalid API key;
- admin endpoint with non-admin/normal user credential;
- admin credential boundary;
- no credential reflection in error output.

## Protocol

- malformed Protocol-v2 message;
- invalid/unknown action;
- invalid settings payload;
- invalid model request;
- session isolation.

## Engine/model identity

- unknown model;
- unavailable model;
- Free/Pro runtime/model mismatch;
- Pro runtime invocation without required runtime credential;
- runtime key cannot transform Free build identity into Pro.

## Download behavior

- startup does not silently download;
- explicit provisioning remains explicit.

## Secret scan

Scan:

- wheel;
- sdist;
- Docker image config/history/labels;
- release state;
- RC manifest;
- evidence;
- representative logs/events.

No real secret values may appear.

---

# 23. Release preflight / dry-run qualification

This is mandatory and must use the final RC artifact identities.

Generate the RC manifest before final preflight/dry-run so `release.py` validates exact qualified inputs.

Run safe release preflight.

Verify as much as practical:

- VERSION = 2.0.0;
- exact source commit/tree;
- clean source;
- release notes prepared;
- wheel/sdist hashes match;
- Free/Pro image identities match;
- tools available;
- remote/tag/release checks are read-only;
- no conflicting local release state;
- no version bump.

Run `release.py` dry-run.

Verify planned operation order exactly:

```text
PyPI
→ GHCR
→ Docker Hub
→ external verification
→ Git tag
→ GitHub Release
→ final verification
```

Verify:

- same operation engine as real publish;
- no public writes;
- no tag;
- no release;
- no VERSION mutation;
- no source mutation;
- same version 2.0.0;
- no secret leakage.

Also execute targeted release-tool tests for:

- same-version resume;
- conflict fail-closed;
- tag barrier;
- GitHub Release barrier;
- stale-state reconciliation.

Do not execute real publish.

---

# 24. RC manifest

Populate:

`W5-R02\05_RC_MANIFEST.json`

using the canonical repository RC-manifest format/helper.

It must bind at minimum:

- candidate ID = `W5-RC1`;
- product version = `2.0.0`;
- source commit;
- source tree;
- wheel filename;
- wheel SHA256;
- sdist filename;
- sdist SHA256;
- Kroko Free fingerprint;
- Kroko Free artifact SHA256;
- Kroko Pro fingerprint;
- Kroko Pro artifact SHA256;
- Free image identity;
- Pro image identity;
- OCI version;
- OCI revision;
- Windows qualification result;
- Ubuntu qualification result;
- GitHub Actions run identity/result;
- Faster-Whisper E2E result;
- Kroko Free E2E result;
- Kroko Pro E2E result;
- qualification gate/evidence references;
- qualification status.

No secrets.

The manifest must be sufficient for W6 to refuse a different artifact/source identity.

---

# 25. W5-R02 gates

Use these exact gate IDs in `03_GATE_INDEX.md`.

## RC freeze / source

- **W5Q-G01** Distributed HEAD equals frozen RC commit.
- **W5Q-G02** Frozen RC tree equals expected tree.
- **W5Q-G03** VERSION resolves exactly to 2.0.0.
- **W5Q-G04** Qualification workspace is clean and source-immutable.
- **W5Q-G05** No source commit/tag/push/publication occurred during W5-R02.

## GitHub Actions / regression

- **W5Q-G06** GitHub Actions run exists for exact RC commit.
- **W5Q-G07** Windows CI job PASS.
- **W5Q-G08** Ubuntu 24.04 CI job PASS.
- **W5Q-G09** CI package/fresh-install checks PASS.
- **W5Q-G10** Complete local unit/guard suite PASS.
- **W5Q-G11** `git diff --check` PASS.

## Python artifacts

- **W5Q-G12** Final wheel built from exact RC.
- **W5Q-G13** Final sdist built from exact RC.
- **W5Q-G14** `twine check` PASS for final artifacts.
- **W5Q-G15** Package content positive boundary PASS.
- **W5Q-G16** Package content negative/leak boundary PASS.
- **W5Q-G17** Wheel/sdist hashes recorded and stable.

## Fresh install

- **W5Q-G18** Windows 11 fresh wheel install PASS.
- **W5Q-G19** Windows installed-distribution import/version/scripts/assets PASS.
- **W5Q-G20** Ubuntu 24.04 fresh wheel install PASS.
- **W5Q-G21** Ubuntu installed-distribution import/version/scripts/assets PASS.
- **W5Q-G22** Neither fresh-install proof depends on editable/source checkout.

## Kroko artifacts

- **W5Q-G23** Kroko Free fingerprint/artifact identity qualified.
- **W5Q-G24** Kroko Pro fingerprint/artifact identity qualified.
- **W5Q-G25** Free/Pro namespaces and runtime identity remain distinct.
- **W5Q-G26** No unexpected native Kroko rebuild occurred.
- **W5Q-G27** Runtime credential is not build identity and no secret leaked.

## Production images

- **W5Q-G28** Free production image built from exact RC and qualified.
- **W5Q-G29** Pro production image built from exact RC and qualified.
- **W5Q-G30** Free/Pro OCI version/revision match RC.
- **W5Q-G31** Production images are linux/amd64, Ubuntu 24.04, non-root.
- **W5Q-G32** No editable/source runtime dependency.
- **W5Q-G33** No secrets or large STT models embedded.
- **W5Q-G34** Missing STT model yields healthy container + NOT_READY, no restart loop.

## Live E2E

- **W5Q-G35** Controlled audio fixture identity/acceptance criterion documented.
- **W5Q-G36** Faster-Whisper real Protocol-v2 audio→final transcription E2E PASS.
- **W5Q-G37** Kroko Free real Protocol-v2 audio→final transcription E2E PASS.
- **W5Q-G38** Kroko Pro real Protocol-v2 audio→final transcription E2E PASS.
- **W5Q-G39** All three E2Es show clean session lifecycle and correlated event/log evidence.

## Model management / runtime

- **W5Q-G40** Representative model discovery/refresh PASS.
- **W5Q-G41** Managed Faster-Whisper/Kroko store behavior PASS.
- **W5Q-G42** Read-only custom model source behavior PASS where supported.
- **W5Q-G43** No unexpected startup download.
- **W5Q-G44** Explicit provisioning integrity behavior PASS.
- **W5Q-G45** Managed model persistence across recreate PASS.
- **W5Q-G46** Graceful application shutdown PASS.

## Negative/security

- **W5Q-G47** API authentication negative cases PASS.
- **W5Q-G48** Admin-vs-normal credential boundary PASS.
- **W5Q-G49** Malformed/invalid Protocol-v2 requests fail safely.
- **W5Q-G50** Invalid settings/model requests fail safely.
- **W5Q-G51** Free/Pro mismatch and missing Pro credential fail safely.
- **W5Q-G52** Secret scans across package/image/state/evidence/logs PASS.

## Release process

- **W5Q-G53** Final RC manifest generated from exact qualified identities.
- **W5Q-G54** `release.py` preflight PASS against final RC inputs.
- **W5Q-G55** `release.py` dry-run PASS using shared publication engine.
- **W5Q-G56** Dry-run operation order exactly matches fixed W6 order.
- **W5Q-G57** Same-version resume/conflict/barrier tests PASS.
- **W5Q-G58** Dry-run performs zero public writes and no version/source mutation.

## Final freeze

- **W5Q-G59** Final workspace remains source-clean.
- **W5Q-G60** Local HEAD/tree still equal frozen RC commit/tree.
- **W5Q-G61** Remote Distributed still equals frozen RC commit.
- **W5Q-G62** RC manifest status and final report are internally consistent and complete.

Every mandatory gate must be PASS for `READY FOR ROOT REVIEW`.

A real unavailable prerequisite may be BLOCKED, but then the overall status is `NOT READY FOR ROOT REVIEW`.

Do not mark mandatory real E2E gates N/A.

---

# 26. Evidence format

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

Never include real secrets.

For sensitive commands, redact before saving evidence.

Do not rely only on prose summaries when a raw command/probe output can prove the gate.

---

# 27. `01_RC_CONTEXT.md`

Include:

- Run ID/model/session;
- RC candidate ID;
- exact RC commit/tree;
- Distributed verification;
- workspace path;
- Windows host identity;
- Ubuntu environment identity;
- Docker/Compose versions;
- Python versions;
- prompt source/copy SHA256;
- source-clean status;
- fixed W5 decisions;
- explicit statement: no source modifications allowed.

---

# 28. `02_QUALIFICATION_REPORT.md`

Summarize:

- GitHub Actions;
- source regression;
- package build;
- Windows fresh install;
- Ubuntu fresh install;
- Kroko Free;
- Kroko Pro;
- Free image;
- Pro image;
- Faster-Whisper E2E;
- Kroko Free E2E;
- Kroko Pro E2E;
- model management;
- persistence;
- shutdown;
- negative/security;
- release preflight/dry-run;
- RC manifest.

For each area:

| Area | Result | Exact identity | Key evidence | Gate(s) |
|---|---|---|---|---|

---

# 29. `03_GATE_INDEX.md`

Use exactly W5Q-G01 through W5Q-G62.

Columns:

| Gate | Status | Short proof | Evidence | Command/Test | Result |
|---|---|---|---|---|---|

---

# 30. `04_DEVIATIONS.md`

If none:

`Keine bekannten W5-R02-Abweichungen.`

If a qualification prerequisite is unavailable, document:

- expected;
- actual;
- cause;
- whether source is implicated;
- affected gates;
- whether a Correction Run is required.

Do not hide environment blockers.

---

# 31. `06_FINAL_REPORT.md`

Must begin with exactly one:

`READY FOR ROOT REVIEW`

or

`NOT READY FOR ROOT REVIEW`

Never self-award Root PASS.

Include:

- candidate = W5-RC1;
- version;
- commit;
- tree;
- package identities;
- Kroko identities;
- image identities;
- GitHub Actions result;
- Windows result;
- Ubuntu result;
- three live E2E results;
- unit regression result;
- negative/security summary;
- release preflight/dry-run result;
- final gate count;
- source-clean verification;
- no source commit/tag/push/publication statement;
- RC manifest SHA256.

---

# 32. Final Git verification

At the very end run:

```text
git status --porcelain
git rev-parse HEAD
git rev-parse HEAD^{tree}
git fetch origin
git rev-parse origin/feat/einheitliche-triggerarchitektur-distributed
git diff --check
```

Expected:

```text
HEAD:
bb7a4bb7cc27897aeb257aa5a5b9f3b550b8f602

TREE:
f7b304b1959e48457a8eefd8919484f55214633b

REMOTE DISTRIBUTED:
bb7a4bb7cc27897aeb257aa5a5b9f3b550b8f602

WORKSPACE:
clean
```

Any tracked source modification at the end = FAIL.

---

# 33. Stop conditions

STOP and report `NOT READY FOR ROOT REVIEW` if:

- RC commit/tree mismatch;
- Distributed changes;
- source modification becomes necessary;
- GitHub Actions cannot be made green without source modification;
- package/fresh install requires source rescue;
- a mandatory engine E2E cannot be executed honestly;
- a required runtime/model/credential prerequisite is unavailable;
- artifact identity cannot be established;
- real public publication would be required;
- a secret would need to be exposed in evidence;
- a closed product area would need redesign.

Do not patch around a failing RC.

---

# 34. Success state

W5-R02 succeeds only when this exact chain is demonstrated:

```text
RC_COMMIT bb7a4bb...
→ CI green on exact commit
→ full regression green
→ final wheel/sdist qualified
→ Windows fresh install PASS
→ Ubuntu fresh install PASS
→ Kroko Free artifact qualified
→ Kroko Pro artifact qualified
→ Free image qualified
→ Pro image qualified
→ Faster-Whisper real E2E PASS
→ Kroko Free real E2E PASS
→ Kroko Pro real E2E PASS
→ model management/persistence/shutdown PASS
→ negative/security PASS
→ release preflight PASS
→ release dry-run PASS
→ exact RC manifest complete
→ source still byte-for-byte frozen
→ READY FOR ROOT REVIEW
```

No public release occurs in W5-R02.

W6 may begin only after external Root PASS for this frozen RC.
