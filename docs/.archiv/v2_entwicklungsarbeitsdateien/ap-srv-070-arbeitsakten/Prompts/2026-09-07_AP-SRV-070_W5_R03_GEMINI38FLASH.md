# AP-SRV-070 / W5 — Final Frozen RC Qualification
## W5-R03 — W5-RC2 Release Candidate Qualification
### Model: Gemini 3.8 Flash

---

# 0. Run identity

- **Project:** AP-SRV-070
- **Phase:** W5 — Release Candidate Qualification
- **Run:** W5-R03
- **Purpose:** Final frozen qualification of internal candidate W5-RC2
- **Model:** Gemini 3.8 Flash
- **Session:** NEW SESSION
- **Repository:** `marcosudau-vps/voice-stt-server`
- **Local project/session start folder:** `P:\GithubRepos\marcosudau-vps\voice-stt-server`
- **Distributed branch:** `feat/einheitliche-triggerarchitektur-distributed`
- **Frozen RC name:** `W5-RC2`
- **Frozen RC commit:** `934e3be7c78aa9358f9b42b9fa4dc282bed54d6c`
- **Frozen RC tree:** `2936f70ca44b7a902e1e5c7c5ca69eacc3154fdb`
- **Direct parent:** `7f1ad1f02da9b1c4e3bf226f2a056066921ef77a`
- **Product version:** `2.0.0`
- **GitHub Actions run on exact RC:** `34155005726`
- **GitHub Actions status:** Windows PASS, Ubuntu 24.04 PASS
- **NEW qualification workspace:** `P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-070-w5-r03`
- **Suggested local branch:** `qual/ap-srv-070-w5-r03`
- **Prompt source:** `P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Prompts\2026-09-07_AP-SRV-070_W5_R03_GEMINI38FLASH.md`
- **Run/evidence root:** `P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W5-R03\`
- **Previous W5-R02 evidence:** `P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W5-R02\`
- **Previous correction evidence:** W5-R02-C1 / C2 / C3 / C3-R1 under the same AP-SRV-070 Runs root

This is a **frozen qualification run**.

The frozen RC source identity must not change during this run.

No source correction is permitted here.

If qualification finds a reproducible product/release blocker:
- document it precisely;
- preserve evidence;
- report `NOT READY FOR ROOT REVIEW`;
- do not repair it in this run.

---

# 1. Gemini operating constraints

Gemini 3.8 Flash is expected to work independently, but this run is deliberately constrained because W5-RC2 is frozen.

## You MUST NOT

- redesign architecture;
- refactor unrelated code;
- "clean up" implementation;
- improve style merely because you see an opportunity;
- change tests to make failures disappear;
- reinterpret closed AP-SRV-070 contracts;
- modify source code;
- modify workflow files;
- modify docs except qualification reports/evidence outside the repository;
- modify VERSION;
- create a replacement RC;
- create commits;
- push;
- tag;
- publish;
- change `main`;
- change `feat/einheitliche-triggerarchitektur`;
- change Distributed.

## You MAY

- create external qualification scripts under the external Run/Evidence directory;
- create temporary local runtime/config files outside Git tracking;
- build release artifacts from the frozen RC;
- create isolated virtual environments;
- create Docker images/containers locally;
- run WSL2 Ubuntu 24.04 qualification;
- load runtime secrets process-only where explicitly required by this prompt;
- inspect and compare prior qualification evidence;
- adapt the **external qualification harness** if the old W5-R02 harness is proven to be the source of a false/inconclusive result.

The rule is:

> Frozen source stays frozen. Qualification infrastructure outside the product may be improved when needed to obtain valid evidence.

---

# 2. Why this run exists

W5-RC1 qualification was largely successful but found concrete blockers.

Those blockers were corrected through C1/C2/C3/C3-R1.

The final correction was Root-approved, pushed, and independently validated by GitHub Actions on exact commit:

`934e3be7c78aa9358f9b42b9fa4dc282bed54d6c`

with exact tree:

`2936f70ca44b7a902e1e5c7c5ca69eacc3154fdb`

and both mandatory CI jobs green.

Therefore this exact source identity is now frozen as:

`W5-RC2`

W5-R03 is the final qualification of that exact RC.

---

# 3. What remains open from W5-R02

Do not reopen already-closed areas unless a new reproducible failure appears.

The main unresolved W5-R02 items are:

## D4 — Live E2E inconclusive

W5-R02 used:

`tests/unit/audio/asr-reference.wav`

- duration approx. 51.925 s
- 16 kHz
- controlled English reference audio
- 9 expected utterances
- SHA256 previously recorded as:
  `17a30810b13aaad4382a5e60a7102faeb1c624adeca6b1145fc1619579c62750`

Faster-Whisper and Kroko Free both correctly transcribed the beginning but the final output stopped at roughly the same position before the end.

Because two structurally different engines stopped at approximately the same point, W5-R02 concluded that the shared harness/client/VAD interaction was more likely than two simultaneous engine defects.

W5-R03 must close this properly.

## D5 — Kroko Pro live E2E blocked by missing runtime credential

The runtime credential now exists locally.

Authoritative local secret file:

`P:\GithubRepos\marcosudau-vps\voice-stt-server\secrets\voice-stt.env`

This path is intentionally outside all Git worktrees even though it is inside the local project parent directory.

The relevant supported qualification variable is:

`VOICESTT_KROKO_ONNX_KEY`

The secret value must never enter evidence.

## D7 — Read-only custom model source not tested

W5-R03 must explicitly qualify a custom external read-only model source/path and prove VoiceSTT does not attempt to mutate it.

---

# 4. Closed areas — do not conceptually re-audit

Unless this frozen RC produces a new reproducible failure, treat the following as closed:

- Trigger / Activation architecture
- Commands / Timer
- Protocol v2 design
- Settings architecture
- Wake Word architecture
- packaging/version authority
- Kroko Artifact Authority Free/Pro
- Windows/Ubuntu Kroko artifact qualification
- STT model management/discovery/recovery/provisioning semantics
- secret boundary
- transactional refresh
- Linux test portability
- Production Docker/Compose architecture
- W5-R01 release tooling architecture
- canonical log-store recovery semantics fixed in C3-R1
- Windows Kroko semantic path identity fix
- manifest `wheelSha256` producer/consumer fix

You still need to prove the final RC artifacts integrate correctly, but do not redesign or reopen the underlying architecture.

---

# 5. Frozen-RC rule

Before doing anything substantive:

1. `git fetch origin`
2. create the new qualification worktree from exact RC commit;
3. verify:
   - HEAD =
     `934e3be7c78aa9358f9b42b9fa4dc282bed54d6c`
   - tree =
     `2936f70ca44b7a902e1e5c7c5ca69eacc3154fdb`
   - VERSION =
     `2.0.0`
4. verify Distributed still points to the same commit;
5. verify workspace clean;
6. write qualification plan before creating any repo-local temporary artifact;
7. do not modify tracked source.

At the end, repeat all identity checks.

Any tracked repository modification = qualification failure unless it is caused only by a known generated file that is immediately removed and never committed. Prefer avoiding repo-local generated files entirely.

---

# 6. Run archive

Create:

`P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W5-R03\`

with at least:

```text
W5-R03\
├── 00_PROMPT.md
├── 01_RC_CONTEXT.md
├── 02_QUALIFICATION_PLAN.md
├── 03_GATE_INDEX.md
├── 04_DEVIATIONS.md
├── 05_RC_MANIFEST.json
├── 06_QUALIFICATION_REPORT.md
├── 07_FINAL_REPORT.md
└── Evidence\
    ├── 00_Preflight\
    ├── 01_Source_Identity\
    ├── 02_Package_Build\
    ├── 03_Kroko_Artifacts\
    ├── 04_Production_Images\
    ├── 05_Fresh_Install_Windows\
    ├── 06_Fresh_Install_Ubuntu\
    ├── 07_Model_Management\
    ├── 08_ReadOnly_Custom_Source\
    ├── 09_Live_E2E_FasterWhisper\
    ├── 10_Live_E2E_Kroko_Free\
    ├── 11_Live_E2E_Kroko_Pro\
    ├── 12_Security_Negative\
    ├── 13_Release_Preflight\
    ├── 14_Release_DryRun\
    ├── 15_GitHub_CI\
    ├── 16_RC_Manifest\
    └── 17_Final_Git_State\
```

Copy this prompt byte-identically into `00_PROMPT.md`.

Record source and copy SHA256.

---

# 7. Evidence rules

Every evidence file begins with:

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

For commands producing long output:
- preserve raw output;
- also create concise machine-readable summary when useful.

For runtime secret use:
- record variable NAME only;
- never record value;
- never dump full environment;
- never `cat`, `type`, `Get-Content`, or otherwise print the secret file;
- never copy the secret file into Evidence;
- never hash secret contents.

---

# 8. Secret handling

Authoritative secret file:

`P:\GithubRepos\marcosudau-vps\voice-stt-server\secrets\voice-stt.env`

Use only for the Kroko Pro live runtime qualification and only when required.

Expected relevant variable:

`VOICESTT_KROKO_ONNX_KEY`

If server API keys are needed by the chosen live harness, the same secret bundle may contain:

- `VOICESTT_API_KEY`
- `VOICESTT_ADMIN_API_KEY`

Load only the variables required by the current process.

## Forbidden

- print secret values;
- copy `.env` to worktree;
- copy `.env` into Docker build context;
- include `.env` in package;
- include `.env` in image layer;
- record process environment wholesale;
- include secret-bearing command lines in Evidence.

Evidence should say only e.g.:

```text
VOICESTT_KROKO_ONNX_KEY: PRESENT
value: REDACTED / NOT CAPTURED
```

If required variable is absent:
mark Kroko Pro gate BLOCKED and final run `NOT READY FOR ROOT REVIEW`.

---

# 9. Package build — exact RC2

Build from exact frozen source:

- wheel
- sdist

Expected public version:

`2.0.0`

Use the official documented build path.

Require:

- wheel built successfully;
- sdist built successfully;
- `twine check` PASS;
- filenames correspond to 2.0.0;
- no editable-install artifact;
- record SHA256 for both artifacts;
- record file size;
- inspect package contents for accidental:
  - secrets
  - local absolute paths
  - source checkout metadata
  - large model files
  - qualification evidence.

Do not reuse W5-RC1 wheel/sdist.

These must be new artifacts built from W5-RC2.

---

# 10. Kroko artifact qualification

Rebuild or obtain via the official W4/W5 production artifact path exactly as required by current build authority.

Qualify both:

## Kroko Free
- Linux/AMD64
- correct Free build identity
- official artifact authority
- fingerprint recorded
- wheel SHA256 recorded
- no Pro-only authority accidentally present

## Kroko Pro
- Linux/AMD64
- correct Pro build identity
- official Pro artifact authority
- fingerprint recorded
- wheel SHA256 recorded
- clearly distinct from Free
- no secret embedded in artifact/build manifest

Do not use the runtime license key as proof of Pro build identity.

Pro build identity must come from the explicit Pro build/artifact authority.

---

# 11. Production images

Build exact W5-RC2 production images:

- Free
- Pro

Use current official Production Docker path.

Record:

- image ID / digest
- architecture
- base OS
- OCI version label
- OCI revision label
- effective runtime user UID/GID
- build source commit/tree
- embedded Kroko artifact identity/fingerprint where applicable

Require:

- Linux/AMD64
- Ubuntu 24.04 runtime authority as currently defined
- non-root runtime user as documented
- OCI version = `2.0.0`
- OCI revision = exact RC commit
- no source checkout mount required
- no editable install
- no secret in image config/history/layers/labels
- no large STT model accidentally embedded
- Free and Pro images distinguish correctly
- production Dockerfile does not compile native Kroko during image build if current authority says artifacts are reused

Do not publish images.

---

# 12. Fresh installed-distribution qualification

Mandatory platforms:

1. Windows 11 / Python 3.12
2. Ubuntu 24.04 / Python 3.12

Use the exact W5-RC2 wheel built in this run.

Use isolated clean environments.

Do not install editable checkout.

For both:

- install exact wheel;
- `pip check`;
- import VoiceSTT from installed distribution;
- verify installed version `2.0.0`;
- verify console scripts;
- verify required installed package assets;
- start server from installed distribution;
- prove no dependency on source checkout;
- prove no implicit large model download merely from startup;
- verify expected NOT_READY / model-unavailable behaviour where appropriate;
- shut down cleanly.

Record exact wheel SHA256 used on both platforms and prove they are identical.

---

# 13. Model management final integration

Do not redesign or re-audit architecture.

From the final RC artifacts/runtime prove:

- model discovery works;
- refresh works;
- managed STT stores resolve correctly;
- startup does not unexpectedly auto-download large models;
- explicit provisioning remains hash-verified;
- provisioned model survives full container recreation where persistence is part of current production contract;
- graceful shutdown remains clean.

Reuse prior known-good model fixtures/artifacts where valid, but evidence must be generated against W5-RC2 runtime.

---

# 14. D7 — read-only custom source

This is mandatory.

Create or use a controlled external custom model source/path **outside managed writable stores**.

Make the source read-only at the filesystem level.

The qualification must prove:

1. VoiceSTT can discover/use the custom source in the intended supported way;
2. startup/refresh/runtime access succeeds;
3. VoiceSTT does not write into it;
4. no temp files, lock files, metadata, downloads, renames or chmod mutations appear inside it;
5. content hashes before and after are identical;
6. filesystem permissions remain unchanged;
7. managed writable operations continue to use the managed store, not the read-only source.

If Windows permission semantics are not sufficiently strong for the test, perform the authoritative proof on Ubuntu 24.04 with real read-only permissions and optionally add Windows observational coverage.

This gate must be PASS, not NOT TESTED.

---

# 15. Live E2E philosophy

This is the most important unresolved part of W5.

The previous W5-R02 harness produced incomplete final transcripts at nearly the same position for Faster-Whisper and Kroko Free.

Do not simply rerun the exact same potentially flawed harness and call another inconclusive result a product failure.

First determine the most faithful supported live path.

Prefer a real product-facing client path such as:

```text
real controlled WAV/audio
→ real Protocol-v2 WebSocket connection
→ real server
→ real engine
→ final transcript events
→ clean session completion
```

The qualification harness may live outside the repository under Evidence.

It must not modify product source.

Use a real WebSocket connection whenever practical, not a direct internal method shortcut.

The harness must:
- feed the complete source audio;
- preserve correct sample rate/frame ordering;
- not stop early because of an arbitrary client timeout;
- observe the complete product session lifecycle;
- distinguish interim vs final frames;
- wait for semantically correct completion;
- record enough timing/session state to diagnose truncation;
- terminate with a hard overall safety timeout.

Avoid byte-exact transcript equality.

Use controlled plausibility/coverage expectations.

---

# 16. Controlled live-audio fixture

Default controlled fixture remains:

`tests/unit/audio/asr-reference.wav`

Before use:

- verify file exists in frozen source;
- record SHA256;
- record duration;
- sample rate;
- channel count;
- expected reference text/utterance boundaries from current test authority.

If this fixture is unsuitable for a particular engine because of documented language/model limitations, do not silently substitute a trivial fixture.

Instead:
- document why;
- use an existing controlled fixture appropriate to that engine if present;
- otherwise create an external synthetic/recorded controlled fixture under Evidence without modifying product source;
- preserve its SHA256 and expected speech text.

For cross-engine comparison, prefer the same fixture where technically valid.

---

# 17. D4 — Faster-Whisper live E2E

Mandatory.

Use a real Faster-Whisper model already available or explicitly provisioned through the supported path.

Run:

```text
controlled real audio
→ Protocol-v2 live session
→ Faster-Whisper engine
→ engine processing
→ final transcription(s)
→ structured events/logs
→ clean session completion
```

Require:

- the complete input audio is sent;
- server receives complete input;
- no unexplained early client disconnect;
- no unexplained session truncation;
- final transcript meaningfully covers the expected spoken content;
- all expected major utterance regions are represented;
- session reaches documented completion;
- no engine crash;
- no silent data loss;
- relevant structured events exist;
- transcript is plausible, not necessarily byte-identical;
- evidence includes transcript plus timing/coverage summary.

If final transcript still stops around the old ~22 s region:
- determine whether the server session, client, VAD, or engine stops;
- preserve trace evidence;
- only classify product defect if the product boundary proves it;
- otherwise fix the external qualification harness and rerun.

No product source edits.

---

# 18. D4 — Kroko Free live E2E

Mandatory.

Use:

- exact RC2 Free production artifact/image;
- real Kroko Free artifact;
- controlled real audio;
- supported Free model.

Run the same semantic pipeline:

```text
controlled real audio
→ Protocol-v2 live session
→ Kroko Free engine
→ final transcription(s)
→ structured events/logs
→ clean session completion
```

Require the same completeness guarantees as Faster-Whisper.

Explicitly verify:
- Free artifact identity;
- no Pro key required;
- no accidental Pro path;
- transcript plausibility;
- complete audio consumed;
- clean session completion.

If a shared truncation recurs in both Faster-Whisper and Kroko Free:
first suspect the qualification/client path and prove the boundary before blaming both engines.

---

# 19. D5 — Kroko Pro live E2E

Mandatory.

Use exact RC2 Pro artifact/image and the runtime-only credential.

Secret source:

`P:\GithubRepos\marcosudau-vps\voice-stt-server\secrets\voice-stt.env`

Relevant variable:

`VOICESTT_KROKO_ONNX_KEY`

Requirements:

- load credential process-only;
- never print value;
- never copy `.env`;
- never put key into image;
- never put key into evidence;
- prove exact Pro artifact/image identity independently of secret;
- run real controlled audio through Protocol v2;
- obtain plausible final transcription;
- prove complete session lifecycle;
- prove Pro engine actually initialized/processed;
- prove clean shutdown.

Evidence may say:

```text
Kroko Pro runtime credential: PRESENT
Secret value captured: NO
```

If Pro runtime rejects the credential:
record sanitized error and classify accurately.
Do not expose the credential.

---

# 20. Live E2E quality criteria

For each of the three engines:

- Faster-Whisper
- Kroko Free
- Kroko Pro

record a machine-readable result containing at least:

```json
{
  "engine": "...",
  "artifactIdentity": "...",
  "audioSha256": "...",
  "audioDurationSeconds": 0,
  "audioFramesSent": 0,
  "sessionStarted": true,
  "sessionCompleted": true,
  "finalCount": 0,
  "lastFinalAtSeconds": 0,
  "transcript": "...",
  "coverageAssessment": "...",
  "cleanShutdown": true,
  "result": "PASS"
}
```

You may add fields.

`PASS` requires:
- complete audio path;
- meaningful final transcript;
- no unexplained truncation;
- clean session completion.

Do not assign PASS solely because the engine emitted any text.

---

# 21. Security / negative qualification

Against final RC artifacts/runtime verify at least:

- invalid/missing auth rejected where required;
- admin/session separation remains correct;
- secret values absent from logs/events;
- Kroko credential absent from serialized settings/status/output;
- no secret in wheel/sdist;
- no secret in image history/config/labels;
- no local `.env` path embedded in product artifacts;
- malformed protocol input rejected cleanly;
- event-store unavailable behaviour remains fail-closed as fixed in C3-R1;
- failed structured events do not appear as committed `log.event`;
- no unexpected source checkout path exposure.

Do not expand into a general penetration test.

---

# 22. Release preflight

Use the W5-R01 release tooling from exact RC2.

Run the documented W6-capable **preflight** without public writes.

Require:

- target version exactly `2.0.0`;
- exact RC commit/tree accepted;
- package/image/artifact inputs bind correctly;
- no automatic version bump;
- no conflicting local state;
- publication operation order remains:

```text
PyPI
→ GHCR
→ Docker Hub
→ external verification
→ Git tag
→ GitHub Release
→ final verification
```

Do not execute public writes.

---

# 23. Release dry-run

Run the real release orchestration in side-effect-free/dry-run mode.

Require:

- same operation graph as publication;
- version `2.0.0`;
- zero public writes;
- zero tag creation;
- zero GitHub Release creation;
- same-version resume logic remains intact;
- no automatic 2.0.1 or RC public version;
- release state/order valid.

Preserve machine-readable output.

---

# 24. Final RC manifest

Build the RC manifest using the **real production-shaped outputs** from this run.

Do not hand-create a fake manifest.

The previously fixed producer/consumer field contract must now work end-to-end.

Manifest must bind at least:

- RC name `W5-RC2`
- version `2.0.0`
- commit
- tree
- wheel filename + SHA256
- sdist filename + SHA256
- Kroko Free fingerprint + artifact SHA256
- Kroko Pro fingerprint + artifact SHA256
- Free image identity/digest
- Pro image identity/digest
- platform qualification summary
- live E2E summary
- GitHub Actions run identity
- release readiness state

Run documented manifest validation.

For a successful final qualification, readiness should reflect the qualified final state expected by current tooling/contract.

If the tooling intentionally uses a different status name, document it exactly rather than inventing a value.

Store final manifest as:

`05_RC_MANIFEST.json`

Record its SHA256.

---

# 25. GitHub Actions proof

Record independent GitHub evidence for exact frozen RC:

- branch
- commit
- tree
- workflow run ID `34155005726`
- event
- conclusion
- Windows job conclusion
- Ubuntu job conclusion

Expected:

```text
head_sha = 934e3be7c78aa9358f9b42b9fa4dc282bed54d6c
tree     = 2936f70ca44b7a902e1e5c7c5ca69eacc3154fdb
Windows  = success
Ubuntu   = success
```

Do not rerun CI unless necessary.

---

# 26. Final Git integrity

At the end verify:

- HEAD still exact frozen commit;
- tree still exact frozen tree;
- `git status --porcelain` empty;
- no qualification source commit;
- no tag;
- Distributed unchanged;
- canonical unchanged;
- main unchanged;
- no public publication.

Qualification artifacts/evidence must remain outside tracked source.

---

# 27. Deviations

`04_DEVIATIONS.md` must list every meaningful qualification deviation.

Examples:
- harness changed from W5-R02 due proven old harness limitation;
- environment-only bind-mount issue;
- external model fixture substitution;
- runtime library prerequisite installed;
- WSL/native filesystem requirement.

Do not classify an environment workaround as a source defect without evidence.

Do not hide deviations merely because the final result is PASS.

---

# 28. Mandatory gates

Use exactly these IDs in `03_GATE_INDEX.md`.

## RC identity / governance

- **W5Q2-G01** Frozen RC commit exactly `934e3be7c78aa9358f9b42b9fa4dc282bed54d6c`.
- **W5Q2-G02** Frozen RC tree exactly `2936f70ca44b7a902e1e5c7c5ca69eacc3154fdb`.
- **W5Q2-G03** VERSION exactly `2.0.0`.
- **W5Q2-G04** New clean qualification worktree created from exact RC.
- **W5Q2-G05** No tracked source modification.
- **W5Q2-G06** No commit/push/tag/publication.

## Package artifacts

- **W5Q2-G07** RC2 wheel built successfully.
- **W5Q2-G08** RC2 sdist built successfully.
- **W5Q2-G09** `twine check` PASS.
- **W5Q2-G10** Package artifact SHA256 identities recorded.
- **W5Q2-G11** Package contents free of secrets/models/local qualification artifacts.

## Kroko artifacts

- **W5Q2-G12** Kroko Free Linux/AMD64 artifact authority PASS.
- **W5Q2-G13** Kroko Pro Linux/AMD64 artifact authority PASS.
- **W5Q2-G14** Free/Pro fingerprints and SHA256 identities distinct and recorded.
- **W5Q2-G15** Runtime Pro credential not used as build identity and absent from artifacts.

## Production images

- **W5Q2-G16** Free production image built from exact RC2.
- **W5Q2-G17** Pro production image built from exact RC2.
- **W5Q2-G18** Image architecture/runtime OS/nonroot contracts PASS.
- **W5Q2-G19** OCI version/revision exact.
- **W5Q2-G20** No secrets/models/editable checkout/source mount dependency in images.
- **W5Q2-G21** Free/Pro image identity separation PASS.

## Fresh installed distribution

- **W5Q2-G22** Windows fresh wheel install PASS.
- **W5Q2-G23** Ubuntu 24.04 fresh wheel install PASS.
- **W5Q2-G24** Same exact wheel SHA256 used on both platforms.
- **W5Q2-G25** pip/import/version/console-script/assets smoke PASS both platforms.
- **W5Q2-G26** Installed distribution runs without source checkout dependency.
- **W5Q2-G27** Startup does not implicitly download large STT models.
- **W5Q2-G28** Clean startup/shutdown behaviour PASS.

## Model management / custom source

- **W5Q2-G29** Final RC model discovery/refresh PASS.
- **W5Q2-G30** Explicit hash-verified provisioning PASS.
- **W5Q2-G31** Managed-store persistence over required recreate cycle PASS.
- **W5Q2-G32** Read-only custom model source is usable.
- **W5Q2-G33** Read-only custom source unchanged by content/hash/permissions after use.
- **W5Q2-G34** Managed writable operations do not mutate read-only custom source.

## Live E2E

- **W5Q2-G35** Controlled audio fixture identity/duration/reference recorded.
- **W5Q2-G36** Faster-Whisper complete Protocol-v2 live E2E PASS.
- **W5Q2-G37** Faster-Whisper transcript coverage/plausibility PASS.
- **W5Q2-G38** Kroko Free complete Protocol-v2 live E2E PASS.
- **W5Q2-G39** Kroko Free transcript coverage/plausibility PASS.
- **W5Q2-G40** Kroko Pro runtime credential available without secret exposure.
- **W5Q2-G41** Kroko Pro exact artifact/image identity PASS.
- **W5Q2-G42** Kroko Pro complete Protocol-v2 live E2E PASS.
- **W5Q2-G43** Kroko Pro transcript coverage/plausibility PASS.
- **W5Q2-G44** All three live E2E sessions complete cleanly with no unexplained truncation.

## Security / failure semantics

- **W5Q2-G45** Authentication/authorization negative checks PASS.
- **W5Q2-G46** Secret redaction and artifact secret scans PASS.
- **W5Q2-G47** Canonical store unavailable/fail-closed behaviour PASS.
- **W5Q2-G48** Failed events never appear as committed live events.
- **W5Q2-G49** No local secret path/value leakage.

## Release tooling

- **W5Q2-G50** Release preflight PASS on exact RC2.
- **W5Q2-G51** Release dry-run PASS with zero public writes.
- **W5Q2-G52** Publication order exact.
- **W5Q2-G53** Same-version resume/no-auto-version-bump contract PASS.
- **W5Q2-G54** RC manifest builds from real production-shaped outputs.
- **W5Q2-G55** RC manifest validation PASS.
- **W5Q2-G56** RC manifest binds exact package/Kroko/image/commit/tree identities.

## External CI / final integrity

- **W5Q2-G57** GitHub Actions run `34155005726` binds exact RC commit/tree.
- **W5Q2-G58** GitHub Actions Windows PASS.
- **W5Q2-G59** GitHub Actions Ubuntu PASS.
- **W5Q2-G60** Final workspace clean and frozen HEAD/tree unchanged.
- **W5Q2-G61** No tag/release/public registry write occurred.
- **W5Q2-G62** Final RC manifest/report consistently represents W5-RC2 readiness.

All 62 mandatory gates must PASS for:

`READY FOR ROOT REVIEW`

No mandatory gate may be silently marked N/A.

If a gate is genuinely impossible because of an external prerequisite:
mark it BLOCKED and final result `NOT READY FOR ROOT REVIEW`.

---

# 29. Failure classification

If something fails, classify it before drawing conclusions.

Use:

- `SOURCE_DEFECT`
- `ARTIFACT_DEFECT`
- `HARNESS_DEFECT`
- `ENVIRONMENT_DEFECT`
- `EXTERNAL_PREREQUISITE`
- `EVIDENCE_GAP`

For any non-PASS gate record:
- observed failure;
- classification;
- why;
- whether frozen source is implicated;
- exact reproduction;
- sanitized logs;
- recommended next action.

Do not modify source to fix failures in this run.

---

# 30. Live E2E anti-false-positive rules

Do not call a live engine PASS merely because:
- server starts;
- model loads;
- one partial transcript appears;
- first utterance transcribes;
- websocket remains open;
- no exception is thrown.

PASS requires:
- complete controlled audio delivery;
- meaningful output from expected speech across the fixture;
- clean product session completion;
- no unexplained missing tail;
- final evidence from product-visible path.

Do not call a product FAIL merely because:
- the external harness times out;
- client stops sending early;
- local process scheduling stalls;
- a WSL/Windows mount behaves oddly.

Prove the product boundary.

---

# 31. Release-candidate result

The final report `07_FINAL_REPORT.md` must begin exactly:

`READY FOR ROOT REVIEW`

or:

`NOT READY FOR ROOT REVIEW`

Do not claim Root PASS yourself.

If READY, include:

```text
Internal Candidate: W5-RC2
Version: 2.0.0
Commit: 934e3be7c78aa9358f9b42b9fa4dc282bed54d6c
Tree: 2936f70ca44b7a902e1e5c7c5ca69eacc3154fdb
GitHub Actions: PASS
Mandatory gates: 62/62 PASS
Public writes: 0
```

plus exact artifact identities.

Also state:

> W5-RC2 is qualified but not published. W6 may publish only these exact qualified identities according to the frozen same-version resume/publication order.

If NOT READY:
do not recommend broad redesign.
List only concrete release blockers.

---

# 32. Stop conditions

STOP and report `NOT READY FOR ROOT REVIEW` if:

- RC commit/tree changes;
- source changes become necessary;
- tracked files are modified;
- Pro credential unavailable;
- Pro credential leaks;
- a mandatory live engine cannot complete;
- read-only custom source cannot be qualified;
- package/image/manifest identities cannot be bound;
- release preflight/dry-run would require public writes;
- GitHub CI does not bind exact RC;
- a real product blocker is found;
- evidence becomes insufficient to support a gate.

Do not improvise a new RC in this run.

---

# 33. Success chain

```text
W5-RC2 frozen
934e3be7... / 2936f70c...
GitHub Windows PASS
GitHub Ubuntu PASS
        ↓
build exact RC2 package artifacts
        ↓
build/qualify Free + Pro Kroko artifacts
        ↓
build exact RC2 Free + Pro production images
        ↓
fresh install Windows + Ubuntu
        ↓
model-management integration
        ↓
read-only custom source PASS
        ↓
Faster-Whisper live E2E PASS
Kroko Free live E2E PASS
Kroko Pro live E2E PASS
        ↓
security/negative PASS
        ↓
release preflight PASS
release dry-run PASS
        ↓
real RC manifest build + validate
        ↓
62/62 mandatory gates PASS
        ↓
READY FOR ROOT REVIEW
        ↓
external ROOT PASS
        ↓
W5 COMPLETE
        ↓
W6 publishes exact qualified 2.0.0 identities
```

---

# 34. Final reminder for Gemini

This is not a design task.

This is not an implementation task.

This is not an opportunity to improve the product.

This is a **frozen release-candidate qualification task**.

When unsure:
- inspect authority;
- test the frozen product;
- improve only external qualification evidence/harness;
- preserve source;
- classify failures;
- do not redesign.
