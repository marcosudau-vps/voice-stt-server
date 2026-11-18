# AP-SRV-070 / W4B — Self-Contained Execution Contract
## STT Model Authority, Discovery, Recovery & Provisioning

This file is intentionally self-contained.

Do not require or wait for any external `Context\ServerV2` files. All context needed to execute W4B is included below.

---

# 0. Execution Mode

This is a high-autonomy implementation task.

The requirements in this prompt define:
- required product outcomes,
- fixed semantics,
- closed boundaries,
- acceptance gates,
- Git/publication rules.

They intentionally do **not** prescribe:
- class names,
- module layout,
- exact algorithms,
- exact implementation sequence.

Choose the smallest coherent design that fits the existing codebase.

Do not perform a repository-wide historical audit before beginning implementation.

Read the repository only as needed to understand the W4B call graph and existing abstractions.

Within W4B scope:
- diagnose failures yourself,
- correct your own implementation,
- rerun tests,
- self-review the complete diff,
- finish only when all defined gates pass.

A red test is not by itself a blocker.

Stop as `BLOCKED` only when completion genuinely requires something outside authorized scope or unavailable external authority.

---

# 1. Git Authority / Start Gate

Repository working directory:

```text
P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-070-w4b
```

Expected branch:

```text
work/AP-SRV-070-W4B
```

Required starting commit / W4A authority:

```text
169cb57eecbf71a010f494e0fc44936d1ad5976e
```

Required starting tree:

```text
2ff94b397af37b8ecb5bf75aba14c2a573d92603
```

GitHub remote:

```text
github
```

Distributed authority at start:

```text
github/feat/einheitliche-triggerarchitektur-distributed
= 169cb57eecbf71a010f494e0fc44936d1ad5976e
```

Canonical must remain unchanged during W4B:

```text
feat/einheitliche-triggerarchitektur
= c82923fc6ce889b4dfbbde1f9877b8b76481a1e8
```

At start verify:

```text
git branch --show-current
git rev-parse HEAD
git rev-parse "HEAD^{tree}"
git status --short
git remote -v
git fetch github
git rev-parse github/feat/einheitliche-triggerarchitektur-distributed
```

Required:
- branch exact,
- HEAD exact,
- tree exact,
- clean worktree,
- `github` remote present,
- remote Distributed still exact W4A commit.

If not:

```text
STATUS: BLOCKED
```

and stop before mutation.

---

# 2. Accepted Server V2 Authority

The following server areas are already accepted and are **not open for general re-audit**.

Use them as existing contracts.

## Accepted/closed areas

- Protocol V2 identity and session semantics.
- Server-authoritative activation lifecycle.
- Manual activation and internal wake activation.
- Serial segment lifecycle.
- Exactly-one terminal outcome semantics.
- Session-wide sequencing and idempotency.
- Safe input close/finalization ordering.
- Settings snapshot/event consistency.
- Wake-word catalog/runtime/policy architecture.
- OpenWakeWord assets/backend selection.
- Logging/replay/retention foundations.
- Python distribution/version authority.
- Wheel/sdist packaging.
- Kroko native runtime/artifact authority.
- Kroko persistent artifact store/reuse.
- Kroko artifact-store locking/crash-recovery semantics.

Current source version authority:

```text
VERSION = 2.0.0
```

W4A final qualified commit:

```text
169cb57eecbf71a010f494e0fc44936d1ad5976e
```

W4A Windows Free Kroko artifact authority:

```text
fingerprint:
28594e6d201fc4a7

toolchain authority:
63224eaaaa84424e

filename:
kroko_onnx-1.12.9-1free-cp312-cp312-win_amd64.whl

sha256:
cdaa28193366c21d21b6f59e73cd0733fd59ba3eba6a471d540ba11a34f48f38

bytes:
12549999
```

W4A final full unit qualification:

```text
1448 passed
14 skipped
974 subtests passed
0 failed
```

## Closed-contract rule

Do not reopen a closed area merely because:
- a different design might be nicer,
- additional hardening is theoretically possible,
- old implementation history could be reread.

A closed area may be touched only when W4B exposes a concrete reproducible defect or a directly required integration point.

If that occurs:
1. prove the conflict with the smallest useful reproducer,
2. make only the narrowest necessary compatible change,
3. document why the closed area had to be touched.

---

# 3. W4B Mission

Implement the remaining server-side STT model-management layer as one coherent production feature.

VoiceSTT must have one server-authoritative model-management contract for **large STT models** used by at least:

- Faster-Whisper
- Kroko

Wake-word assets are not part of this system.

The finished server must be able to:

- discover existing STT models from configured and default locations,
- cheaply validate discovered candidates,
- load-probe only serious candidates,
- represent immutable product/model facts separately from operator intent,
- select a minimum working STT configuration deterministically,
- recover through explicitly eligible fallback candidates,
- provision explicitly requested missing models when allowed,
- verify downloaded content before activation,
- install model content atomically,
- preserve last-known-good state across failed refresh/provisioning,
- remain administrable when STT itself is not ready,
- expose actionable status/diagnostics,
- prevent engine libraries from silently downloading models outside this authority.

---

# 4. Persistent Model Storage

Use the server's existing persistent runtime/data-root authority.

Do not invent a second unrelated persistence root.

Default logical layout:

```text
<runtime>/models/stt/fasterwhisper
<runtime>/models/stt/kroko_asr
```

Use existing naming/configuration conventions where appropriate.

Required semantics:

- custom paths are searched before the default runtime model store;
- all configured discovery paths are considered;
- a read-only custom path is a valid discovery/read source;
- lack of write permission disqualifies a path only as a provisioning target;
- provisioning prefers the intended/configured target when writable, otherwise falls back to the guaranteed writable runtime store;
- no permanent duplicate cache of large model content.

Temporary `.part` files/staging directories are allowed for atomic install and must never be discovered as complete models.

---

# 5. Discovery Lifecycle

The model-management layer must distinguish these concepts:

```text
DISCOVERED
VALIDATED
LOAD_VERIFIED
```

## DISCOVERED

A candidate exists and can be associated with an engine/model identity.

## VALIDATED

Cheap deterministic checks appropriate to that engine/model passed.

Examples:
- expected structure,
- metadata,
- known hash/size,
- runtime compatibility,
- operator enablement,
- immutable eligibility.

## LOAD_VERIFIED

The actual engine can load/use the serious candidate.

Do not load-probe the entire catalog during ordinary discovery/refresh.

Expensive real load checks are reserved for serious candidates.

---

# 6. Product Model Authority vs Operator Configuration

Static product/model facts belong to central product authority, not mutable user config.

The authority must be capable of representing, where applicable:

- stable model ID,
- engine,
- language,
- Community/Pro/license class,
- runtime variant,
- supported STT roles/capabilities,
- immutable source/revision,
- expected filename/layout,
- content identity such as SHA-256/bytes when required for provisioning,
- whether automatic provisioning is fundamentally allowed,
- rights/provisioning status,
- optional `recovery_priority`.

Operator configuration expresses intent only, such as:

- enabled/disabled engine,
- enabled/disabled model,
- realtime/final defaults,
- custom model locations,
- auto-download scope,
- optional supported priority overrides.

Operator configuration must not rewrite static product/legal/runtime facts.

## Honesty rule

Never fabricate:
- immutable revision,
- hash,
- byte count,
- license fact,
- download permission.

If an entry lacks enough immutable authority for safe automatic provisioning:
- it may remain locally discoverable/selectable when safe,
- automatic provisioning for it must remain ineligible/blocked.

Do not weaken verification to make the catalog appear complete.

---

# 7. `auto_download_enabled` — Fixed Semantics

This is one hierarchical activation flag.

For a model:

```text
effective_auto_download =
    global.auto_download_enabled
    OR engine.auto_download_enabled
    OR model.auto_download_enabled
```

Missing values behave as `false`.

A lower `false` never vetoes an upper `true`.

Therefore:

- global `true` requests every fundamentally provisionable model of every enabled STT engine;
- otherwise engine `true` requests every fundamentally provisionable model of that enabled engine;
- otherwise model `true` requests that specific model;
- `false` activates nothing at that level and delegates downward.

Keep hard eligibility separate.

A requested model may still be `BLOCKED`/`INELIGIBLE` because immutable prerequisites are missing.

Diagnostics must distinguish:
- requested scope,
- eligibility,
- provisioning result.

---

# 8. Recovery Semantics

Recovery starts from explicit operator intent.

Required order:

1. eligible configured realtime/final defaults first;
2. then automatic fallback candidates ordered by ascending `recovery_priority`;
3. deterministic stable-ID tie-break for equal priority.

A model with no `recovery_priority`:

- is not a generic automatic recovery fallback,
- remains discoverable/selectable,
- may still be explicitly provisioned by effective auto-download.

A recovery candidate already present locally may be validated/load-probed regardless of auto-download.

A missing recovery candidate may be provisioned automatically only when both:
- effective auto-download requests it,
- immutable eligibility/provisioning gates permit it.

---

# 9. `MINIMUM_READY`

Recovery seeks the smallest functioning STT configuration.

One model may satisfy both realtime and final roles.

As soon as required STT roles are genuinely covered:

```text
MINIMUM_READY
```

Recovery escalation stops.

This does not cancel independently requested optional provisioning.

Additional explicitly requested models may continue provisioning after readiness.

Their failure must not destroy an already-working minimum configuration.

Observable state must distinguish, in a representation that fits the existing server:

- ready and complete,
- ready while optional requested provisioning continues,
- ready with optional provisioning errors,
- STT not ready,
- requested provisioning blocked/ineligible.

Integrate with existing readiness/diagnostics conventions.

Do not create a parallel health subsystem.

---

# 10. Refresh / Last-Known-Good

Refresh is transactional from the perspective of active server state.

Build/validate a candidate registry/configuration before replacing the active one.

A failed refresh/provisioning attempt must not prematurely destroy:

- previous working registry,
- previous active model assignment,
- verified existing model,
- usable `MINIMUM_READY` state.

Concurrent refresh/provisioning must not expose partial registry state or corrupt the same target.

Choose synchronization appropriate to the existing architecture and prove important interleavings deterministically.

---

# 11. Provisioning Integrity

Large model downloads/installations must be atomic and verified.

For a file model, the observable contract is equivalent to:

```text
download temporary
→ verify expected identity
→ atomically activate final path
```

Directory models require equivalent staged installation.

Requirements:

- partial/staging content is never discoverable as complete;
- hash/size/source mismatch never activates;
- failed replacement preserves known-good content;
- no permanent duplicate download cache;
- concurrent provisioning of one target cannot corrupt or produce ambiguous active state.

Tests must use small deterministic fixtures/local transports.

Do not download multi-GB production models for test coverage.

If archive extraction is used:
- prevent path traversal,
- do not trust archive paths blindly,
- prove safe extraction behavior.

---

# 12. Engine Integration

Common orchestration is server-authoritative.

Engine-specific details remain engine-specific.

The design must naturally accommodate at least:

- Faster-Whisper
- Kroko

Required boundary:

- discovery/validation/provisioning/load-probe may have engine-specific adapters;
- selection/recovery/refresh/readiness policy is common;
- ordinary engine construction receives a resolved local model;
- engine/runtime libraries must not silently perform network model downloads outside the explicit provisioner.

Fit existing abstractions.

Do not create duplicate policy inside each engine.

---

# 13. Kroko-Specific Invariants

Preserve W4A.

For Kroko:

- native runtime artifact and ASR model are separate artifacts;
- Community and Pro model classes remain distinct;
- Pro model eligibility requires compatible Pro runtime and required runtime license prerequisites;
- Pro model present on disk without usable prerequisites remains visible diagnostically but cannot become active/available;
- Pro key is runtime secret, never model metadata, build metadata, store content or logs;
- model paths are resolved at runtime;
- W4B must not trigger Kroko native compilation.

---

# 14. Server Behavior When No STT Model Is Usable

Missing/invalid STT model is an STT readiness failure, not automatically process-liveness failure.

The server must remain administrable enough to:
- expose meaningful diagnostics,
- allow configuration/recovery.

Do not create a Docker restart-loop behavior in server code.

Production container wiring belongs to W4C.

---

# 15. Configuration Integration

Use the existing settings/configuration framework.

Do not add a second parser or parallel settings authority.

The following concepts must become configurable where appropriate:

- global STT auto-download activation,
- engine enabled state,
- engine auto-download activation,
- engine custom model path/candidates,
- model enabled state,
- model auto-download activation,
- realtime/final defaults,
- optional operator-level priority override only if it fits existing settings architecture cleanly.

Defaults must be conservative:
- no surprise large downloads solely because the server starts.

---

# 16. Documentation Contract

Update relevant product/admin documentation.

Explain clearly:

- default model store and custom paths,
- read-only discovery source vs writable provisioning target,
- DISCOVERED / VALIDATED / LOAD_VERIFIED,
- product authority vs operator configuration,
- exact global/engine/model auto-download semantics,
- hard eligibility gates,
- recovery ordering,
- `MINIMUM_READY`,
- optional provisioning after readiness,
- atomic `.part`/staging behavior,
- refresh/last-known-good,
- Community/Pro behavior,
- diagnostics/readiness when STT unavailable.

Include an equivalent decision flow to:

```text
START / REFRESH
│
├─ discover all configured/default locations
│
├─ cheaply validate candidates
│
├─ viable local candidate for required role(s)?
│      ├─ yes → load-probe serious candidate
│      │          ├─ covers required roles → MINIMUM_READY
│      │          └─ fails → continue recovery
│      └─ no → continue recovery
│
└─ recovery
       ├─ explicit defaults first
       ├─ then recovery_priority candidates
       ├─ candidate local?
       │      ├─ yes → validate/load-probe
       │      └─ no → effective auto-download AND hard eligibility?
       │                 ├─ yes → verified atomic provisioning → load-probe
       │                 └─ no → next candidate / diagnostic
       │
       └─ MINIMUM_READY reached
              ├─ stop recovery escalation
              └─ continue only independently requested optional provisioning
```

Equivalent formatting is fine. Semantic content is fixed.

---

# 17. Required Adversarial Behavior to Prove

Tests/self-review must prove at least:

- default runtime store resolution;
- custom path precedence;
- read-only custom path remains discoverable but not download target;
- writable fallback provisioning target;
- partial/staging content ignored by discovery;
- invalid hash/size/source rejected;
- failed replacement preserves known-good;
- no permanent duplicate cache;
- discovery does not eagerly load every model;
- load-probe only serious candidates;
- defaults precede priority fallback;
- priority ordering and deterministic ties;
- no-priority model not generic recovery fallback;
- locally present recovery candidate does not require auto-download;
- missing recovery candidate does require effective auto-download;
- exact `global OR engine OR model` semantics;
- lower `false` cannot veto upper `true`;
- hard ineligibility remains hard despite auto-download request;
- one model may satisfy realtime + final;
- recovery stops at `MINIMUM_READY`;
- optional explicitly requested provisioning may continue afterward;
- optional provisioning failure does not remove readiness/LKG;
- failed refresh preserves active registry/configuration;
- concurrent refresh never publishes partial state;
- concurrent provisioning of same target converges safely;
- server stays administrable with STT `NOT_READY`;
- Pro model cannot activate without required Pro prerequisites;
- no Pro secret in logs/evidence/model store;
- no hidden engine download path outside provisioner;
- no Kroko native build path invoked by W4B.

Where race behavior matters, use deterministic barriers/events rather than timing sleeps as the only proof.

---

# 18. Efficient Repository Exploration

Do not inspect the whole repository indiscriminately.

Start by locating only:

- existing STT engine interfaces/construction,
- Faster-Whisper model path/runtime handling,
- Kroko model authority/path/runtime handling,
- current settings/config machinery,
- current readiness/health/diagnostic machinery,
- runtime/data-root authority,
- relevant existing tests,
- admin/status surfaces that naturally expose W4B state.

Expand scope only when the actual call graph requires it.

Do not read old AP reports unless the code itself is insufficient to resolve a concrete interface question.

---

# 19. Self-Review / Completion Gates

You own the implementation and correction loop.

Before finalizing:

## Requirement trace

Create a concise mapping:
- requirement,
- implementation location,
- test/evidence.

Close every uncovered requirement before commit.

## Complete diff review

Review the final diff as an independent Root reviewer.

Specifically look for:

- duplicate policy in engine-specific code,
- accidental implicit downloads,
- partial-state publication,
- stale LKG invalidation,
- path traversal / unsafe extraction,
- concurrent writer races,
- secret leakage,
- readiness/liveness coupling,
- configuration precedence errors,
- non-atomic filesystem transitions,
- hidden native build invocation.

Fix issues within W4B and rerun gates.

## Tests

Run focused tests during implementation.

Before commit run:

1. all new/changed W4B tests;
2. all directly affected existing engine/settings/readiness/API tests;
3. full server unit regression:

```text
python -m pytest -q tests/unit
```

Use external `--basetemp` if appropriate.

Required:

```text
0 failed
```

Expected pre-existing skips may remain if documented.

Also run:

```text
git diff --check
```

## Scope / hygiene

No:
- real large STT model blobs in repo,
- temp downloads,
- generated evidence/logs,
- venvs,
- credentials,
- Pro keys,
- unrelated refactors.

---

# 20. Blocking vs Autonomous Correction

Do not stop merely because:
- a new test is red,
- initial implementation needs revision,
- a local interface differs from first expectation.

Diagnose and fix within W4B.

Stop as `STATUS: BLOCKED` only when completion requires something genuinely outside scope, for example:

- unavailable required credentials,
- required immutable upstream fact cannot be established and no safe non-provisionable representation exists,
- mandatory external tooling/environment unavailable,
- closed contract must change and conflict is proven by minimal reproducer,
- remote Distributed moved unexpectedly and FF publication cannot be done safely.

Do not weaken acceptance criteria to avoid a blocker.

---

# 21. Git / Publication

Do not create intermediate commits.

When all implementation, scope, self-review and test gates are satisfied:

**Wenn alle im Prompt definierten Implementierungs-, Scope- und Test-Gates erfüllt sind, genau einen Run-Commit erzeugen und Distributed ausschließlich per Fast-Forward aktualisieren.**

Suggested commit subject:

```text
AP-SRV-070 W4B: add server-authoritative STT model management
```

Required parent:

```text
169cb57eecbf71a010f494e0fc44936d1ad5976e
```

Before push:

```text
git fetch github
git rev-parse github/feat/einheitliche-triggerarchitektur-distributed
git merge-base --is-ancestor github/feat/einheitliche-triggerarchitektur-distributed HEAD
```

Remote Distributed must still equal required parent before push.

Then push only:

```text
HEAD -> feat/einheitliche-triggerarchitektur-distributed
```

If remote Distributed moved:
- no merge,
- no rebase,
- no force,
- `STATUS: BLOCKED`.

Canonical must remain unchanged.

Do not begin W4C.

---

# 22. Evidence

Write evidence outside repo:

```text
P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W4B\Implementation\
```

Create at minimum:

```text
01_START_AND_SCOPE.md
02_REQUIREMENT_TRACE.md
03_MODEL_AUTHORITY_AND_CONFIG.md
04_DISCOVERY_RECOVERY_PROVISIONING.md
05_CONCURRENCY_ATOMICITY_SECURITY.md
06_TEST_REPORT.md
07_FINAL_GIT_STATE.md
W4B_STATE.md
```

Evidence should be concise and factual.

Do not dump enormous raw test logs when commands/counts/proofs suffice.

`W4B_STATE.md` must include:

```text
START_GATE: PASS|BLOCKED

MODEL_AUTHORITY: PASS|FAIL
DISCOVERY: PASS|FAIL
VALIDATION: PASS|FAIL
LOAD_PROBE_POLICY: PASS|FAIL
AUTO_DOWNLOAD_SCOPE: PASS|FAIL
RECOVERY_ORDER: PASS|FAIL
MINIMUM_READY: PASS|FAIL
OPTIONAL_PROVISIONING_AFTER_READY: PASS|FAIL
ATOMIC_PROVISIONING: PASS|FAIL
LAST_KNOWN_GOOD: PASS|FAIL
CONCURRENCY: PASS|FAIL
READINESS_DIAGNOSTICS: PASS|FAIL
KROKO_PRO_BOUNDARY: PASS|FAIL
NO_HIDDEN_ENGINE_DOWNLOADS: PASS|FAIL
NO_KROKO_NATIVE_BUILD: PASS|FAIL

TARGETED_TESTS: PASS|FAIL
FULL_UNIT_REGRESSION: PASS|FAIL
FULL_UNIT_FAILURES: 0|<count>
GIT_DIFF_CHECK: PASS|FAIL
SECRET_SCAN: PASS|FAIL
SCOPE_GATE: PASS|FAIL

RUN_COMMIT_CREATED: YES|NO
RUN_COMMIT_SHA: <sha>
RUN_TREE_SHA: <sha>
RUN_PARENT_SHA: 169cb57eecbf71a010f494e0fc44936d1ad5976e

DISTRIBUTED_FAST_FORWARD: PASS|FAIL
DISTRIBUTED_SHA: <sha>
CANONICAL_UNCHANGED: YES|NO

W4C_STARTED: NO
```

---

# 23. Final Response

On success, answer compactly with:

- architecture chosen,
- model authority/config boundary,
- discovery/recovery/provisioning result,
- readiness result,
- targeted test summary,
- full regression counts,
- commit SHA/tree/parent,
- Distributed FF result,
- Canonical unchanged,
- Evidence folder.

On blocker:
- exact unmet contract,
- minimal evidence,
- no speculative redesign.

Do not begin W4C.
