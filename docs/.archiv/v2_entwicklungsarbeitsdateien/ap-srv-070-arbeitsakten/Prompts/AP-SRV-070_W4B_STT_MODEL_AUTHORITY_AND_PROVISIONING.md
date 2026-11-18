# AP-SRV-070 / W4B — STT Model Authority, Discovery, Recovery & Provisioning

## Mission

Implement the remaining server-side STT model-management layer as one coherent production feature.

This is a **high-autonomy implementation task**.

The requirements below define outcomes, invariants and acceptance gates. They intentionally do **not** prescribe class names, module layout, algorithms or an implementation sequence. Choose the design that best fits the existing codebase.

Do not turn this into a new architecture research project. Understand the relevant existing call graph, implement the contract, test it adversarially, self-review the final diff and finish the run.

---

## 1. Start authority

Repository:

```text
P:\GithubRepos\marcosudau-vps\voice-stt-server
```

Expected worktree for this run:

```text
P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-070-w4b
```

Expected branch:

```text
work/AP-SRV-070-W4B
```

Required parent and initial Distributed authority:

```text
169cb57eecbf71a010f494e0fc44936d1ad5976e
```

Required parent tree:

```text
2ff94b397af37b8ecb5bf75aba14c2a573d92603
```

Canonical must remain:

```text
c82923fc6ce889b4dfbbde1f9877b8b76481a1e8
```

GitHub authority remote:

```text
github
```

At start verify HEAD, tree, branch, clean status, GitHub Distributed and Canonical.

If the worktree does not start exactly from the required W4A authority, stop before mutation and report `STATUS: BLOCKED`.

---

## 2. Minimal context contract

Before repository exploration, read the external completion context:

```text
P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Context\ServerV2\SERVER_V2_AUTHORITY.md
P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Context\ServerV2\SERVER_V2_CLOSED_CONTRACTS.md
P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Context\ServerV2\SERVER_V2_REMAINING_WORK.md
P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Context\ServerV2\SERVER_V2_AGENT_ENTRYPOINT.md
```

Then inspect only the repository surface needed for W4B.

Do not reread historical AP/W4A evidence unless a concrete W4B call path requires it.

The W4A Kroko artifact authority is closed and must be consumed, not redesigned.

---

## 3. Product outcome

VoiceSTT must have one server-authoritative model-management contract for **large STT models** used by at least the currently supported Faster-Whisper and Kroko engines.

Wake-word assets are not part of this system.

The finished server must be able to:

- discover existing STT models from configured and default locations,
- cheaply validate discovered candidates,
- load-probe only serious candidates,
- represent model/product facts separately from operator intent,
- select a minimum working STT configuration deterministically,
- recover through explicitly eligible fallback candidates,
- provision explicitly requested missing models when allowed,
- verify downloaded content before activation,
- install model content atomically,
- preserve last-known-good state across failed refresh/provisioning,
- remain administrable when STT itself is not ready,
- expose actionable status/diagnostics,
- prevent engine libraries from silently downloading models outside this authority.

The internal design is yours to choose.

---

## 4. Persistent model storage

Use the server's **existing persistent runtime/data-root authority**. Do not invent a second unrelated persistence root.

Default logical layout:

```text
<runtime>/models/stt/fasterwhisper
<runtime>/models/stt/kroko_asr
```

Existing configuration conventions may determine the final spelling.

Engine-specific custom paths/overrides are supported.

Required semantics:

- custom paths are searched before the default runtime model store;
- all configured discovery paths are considered;
- a read-only custom path remains a valid discovery/read source;
- lack of write permission disqualifies a path only as a provisioning target;
- provisioning should prefer the configured/custom target when it is writable, otherwise fall back to the guaranteed writable runtime store;
- no permanent second download cache of large models.

Temporary `.part` files or staging directories are allowed for atomic installation and must never be discovered as complete models.

---

## 5. Discovery lifecycle

The model-management layer must distinguish these concepts:

```text
DISCOVERED
VALIDATED
LOAD_VERIFIED
```

Their semantics are fixed:

### DISCOVERED

A candidate exists and can be associated with an engine/model identity.

### VALIDATED

Cheap deterministic checks appropriate to that model/engine have passed.

Examples include structure, metadata, known hash/size, runtime compatibility, operator enablement and obvious eligibility.

### LOAD_VERIFIED

The actual engine can load/use the serious candidate.

Do not load-probe the entire catalog during ordinary discovery/refresh.

Pro/private model credentials may be checked for presence/eligibility cheaply, but an expensive real model load is reserved for a serious candidate unless the existing engine exposes a genuinely cheap authoritative license check.

---

## 6. Product Model Authority vs operator configuration

Static product/model facts belong to a central model authority, not to mutable user configuration.

The authority must be capable of representing, where applicable:

- stable model ID,
- engine,
- language,
- Community/Pro/license class,
- runtime variant,
- supported STT roles/capabilities,
- immutable source/revision,
- expected filename/layout,
- content identity such as SHA-256 and bytes when required for provisioning,
- whether automatic provisioning is fundamentally allowed,
- rights/provisioning status,
- optional `recovery_priority`.

Operator configuration expresses intent only, such as:

- enabled/disabled engine,
- enabled/disabled model,
- default realtime/final choice,
- custom model locations,
- auto-download scope,
- optional supported priority overrides.

Operator configuration must not be able to rewrite static product/legal/runtime facts.

### Honesty rule for authority data

Never fabricate an immutable revision, hash, size, license fact or download permission.

If a catalog entry lacks enough authority for safe automatic provisioning:

- it may remain locally discoverable/selectable when that is safe,
- but automatic provisioning for that entry must remain ineligible/blocked until the required authority genuinely exists.

Do not weaken verification to make a catalog look complete.

---

## 7. `auto_download_enabled` — fixed semantics

This is one hierarchical activation flag, not three independent allow/deny policies.

For a model:

```text
effective_auto_download =
    global.auto_download_enabled
    OR engine.auto_download_enabled
    OR model.auto_download_enabled
```

Missing values behave as `false`.

A lower `false` **never vetoes** an upper `true`.

Therefore:

- global `true` requests every fundamentally provisionable model of every enabled STT engine;
- otherwise engine `true` requests every fundamentally provisionable model of that enabled engine;
- otherwise model `true` requests that specific model;
- `false` merely activates nothing at that level and delegates downward.

Keep hard eligibility gates separate from this scope calculation.

A requested model may still be `BLOCKED`/`INELIGIBLE` because its source authority, rights, runtime variant, credentials or other immutable prerequisite is absent.

Status must expose that distinction rather than pretending the requested scope was satisfied.

---

## 8. Recovery semantics

Defaults are preferences and recovery starts with explicit operator intent.

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

- effective auto-download requests it, and
- immutable eligibility/provisioning gates permit it.

---

## 9. `MINIMUM_READY`

Recovery seeks the **smallest functioning STT configuration**, not all configured preferences.

One model may satisfy both realtime and final roles.

As soon as the required STT roles are genuinely covered:

```text
MINIMUM_READY
```

and recovery escalation stops.

This does **not** cancel other models that were independently and explicitly requested through auto-download.

Those additional requested models may continue provisioning after readiness.

Their failure must not destroy an already working minimum configuration.

The observable state must distinguish, in whatever representation best fits the existing server:

- ready and complete,
- ready while optional requested provisioning continues,
- ready with optional provisioning errors,
- STT not ready,
- blocked/ineligible requested provisioning.

Do not create a parallel health subsystem; integrate with existing readiness/diagnostics conventions.

---

## 10. Refresh / last-known-good

Refresh is transactional from the perspective of active server state.

Build and validate a candidate registry/configuration before replacing the active one.

A failed refresh/provisioning attempt must not prematurely destroy:

- the previous working registry,
- the previous active model assignment,
- a verified existing model,
- a usable `MINIMUM_READY` state.

Concurrent refresh/provisioning must not expose partial registry state or corrupt the same target.

Choose synchronization/atomicity mechanisms appropriate to the existing architecture and prove the important interleavings deterministically in tests.

---

## 11. Provisioning integrity

Large model downloads/installations must be atomic and verified.

For a file model, the observable contract is equivalent to:

```text
download temporary
→ verify expected identity
→ atomically activate final path
```

Directory models require equivalent staged installation.

Requirements:

- partial/staging content is never discoverable as a complete model;
- hash/size/source mismatch never activates;
- a failed replacement preserves known-good content;
- no permanent duplicate download-cache copy;
- concurrent provisioning of one target cannot corrupt or produce ambiguous active state.

Tests must use small deterministic fixtures/local transports rather than downloading multi-GB production models.

---

## 12. Engine integration

The common orchestration is server-authoritative; engine-specific details remain engine-specific.

The implementation should naturally accommodate at least:

- Faster-Whisper
- Kroko

without hiding provisioning policy inside the transcription engines.

Required boundary:

- discovery/validation/provisioning/load-probe may have engine-specific adapters,
- selection/recovery/refresh/readiness policy is common,
- ordinary engine construction must receive a resolved local model,
- engine/runtime libraries must not silently perform a network model download outside the explicit provisioner.

Do not prescribe class names merely to match this prompt. Fit the existing code.

---

## 13. Kroko-specific invariants

Preserve W4A.

For Kroko:

- native runtime artifact and ASR model are separate artifacts;
- Community and Pro model classes remain distinct;
- Pro model eligibility requires a compatible Pro runtime and required runtime license prerequisites;
- a Pro model present on disk without usable prerequisites remains visible diagnostically but cannot become active/available;
- the Pro key is a runtime secret, never model metadata, build metadata, store content or log content;
- model paths are resolved at runtime;
- W4B must not trigger Kroko native compilation.

---

## 14. Server behavior when no STT model is usable

A missing/invalid STT model is an STT readiness failure, not automatically a process-liveness failure.

The server must remain administrable enough to expose meaningful diagnostics and allow recovery/configuration.

Do not create a Docker restart-loop behavior in server code.

Production container wiring belongs to W4C.

---

## 15. Configuration integration

Use the existing configuration/settings framework and naming conventions.

The following concepts must become configurable where appropriate:

- global STT auto-download activation,
- engine enabled state,
- engine auto-download activation,
- engine custom model path/candidates,
- model enabled state,
- model auto-download activation,
- realtime/final defaults,
- any operator-level priority override only if it fits the existing settings architecture cleanly.

Do not introduce a second configuration parser or independent settings authority.

Defaults should be conservative: no surprise large downloads solely because the server starts.

---

## 16. Documentation contract

Update the relevant product/admin documentation.

It must clearly explain:

- default model store and custom paths,
- read-only discovery path vs writable provisioning target,
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
- diagnostics/readiness when STT is unavailable.

Include a concise decision tree that conveys this exact logic:

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

Equivalent formatting is allowed; semantic content is not.

---

## 17. Required adversarial behavior to prove

Your tests and self-review must prove at least these contracts. You may consolidate them into appropriately designed tests rather than creating one test per bullet.

- default runtime store resolution;
- custom path precedence;
- read-only custom path remains discoverable but is not selected as download target;
- writable fallback provisioning target;
- partial/staging content ignored by discovery;
- invalid hash/size/source rejected;
- failed replacement preserves known-good content;
- no permanent duplicate cache;
- discovery does not eagerly load every model;
- load-probe only serious candidates;
- defaults precede priority fallback;
- priority ordering and deterministic ties;
- no-priority model is not generic recovery fallback;
- locally present recovery candidate does not require auto-download;
- missing recovery candidate does require effective auto-download;
- exact `global OR engine OR model` semantics;
- lower `false` cannot veto upper `true`;
- hard ineligibility remains hard despite auto-download request;
- one model may satisfy both realtime/final;
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

Use deterministic concurrency barriers where race behavior matters; do not rely on timing sleeps as the only proof.

---

## 18. Agent self-review and completion gates

You own the implementation and its correction loop inside W4B.

Before finalizing:

### Requirement trace

Build a concise internal/evidence mapping from each fixed contract in this prompt to:

- implementation location,
- test/evidence.

Any uncovered requirement must be closed before commit.

### Diff review

Review the complete diff as if you were the independent Root reviewer.

Specifically look for:

- duplicate policy in engine-specific code,
- accidental implicit downloads,
- partial-state publication,
- stale last-known-good invalidation,
- path traversal or unsafe archive extraction if archive provisioning exists,
- concurrent writer races,
- secret leakage,
- confusing readiness/liveness coupling,
- configuration precedence errors,
- non-atomic filesystem transitions.

Fix defects you find within W4B and rerun gates. Do not stop merely because the first attempt was imperfect.

### Tests

Run the narrowest relevant tests continuously while implementing.

Before commit, run:

1. all new/changed W4B tests;
2. all directly affected existing engine/settings/readiness/API tests;
3. full server unit regression:

```text
python -m pytest -q tests/unit
```

Use an external `--basetemp` if needed.

Required final result:

```text
0 failed
```

Expected pre-existing skips may remain if documented.

Also run:

```text
git diff --check
```

### Scope/hygiene

No:

- large real STT model blobs in the repository,
- temporary downloads,
- test caches,
- generated logs/evidence,
- venvs,
- credentials,
- Pro keys,
- unrelated refactors.

---

## 19. Blocking vs autonomous correction

Within W4B, you are expected to diagnose and fix failures yourself.

Do **not** stop and ask for a new prompt merely because:

- a new test is red,
- an implementation approach needs revision,
- an existing local interface differs from your initial expectation.

Stop as `STATUS: BLOCKED` only when the contract cannot honestly be completed without something outside authorized scope, for example:

- required credentials unavailable,
- a required immutable upstream fact cannot be established and there is no safe non-provisionable representation,
- external environment/tooling required by a mandatory gate is unavailable,
- a closed contract must change and you can demonstrate the conflict with a minimal reproducer.

Do not weaken an acceptance criterion to avoid a blocker.

---

## 20. Git / publication mechanics

Do not create intermediate commits.

When all implementation, scope, self-review and test gates are satisfied:

**Wenn alle im Prompt definierten Implementierungs-, Scope- und Test-Gates erfüllt sind, genau einen Run-Commit erzeugen und Distributed ausschließlich per Fast-Forward aktualisieren.**

Suggested subject:

```text
AP-SRV-070 W4B: add server-authoritative STT model management
```

Required parent:

```text
169cb57eecbf71a010f494e0fc44936d1ad5976e
```

Before push:

- fetch `github`,
- verify remote Distributed still equals the required parent,
- prove it is ancestor of HEAD,
- push only HEAD → `feat/einheitliche-triggerarchitektur-distributed`.

If remote Distributed moved unexpectedly, do not merge/rebase/force. Report `STATUS: BLOCKED`.

Canonical must remain unchanged.

W4C must not begin.

---

## 21. Evidence

Write W4B evidence outside the repository to:

```text
P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W4B\Implementation\
```

At minimum create:

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

Evidence should be concise and factual. Do not reproduce thousands of lines of test output when counts, commands and specific failures/proofs suffice.

`W4B_STATE.md` must include at least:

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

## 22. Final response

On success, answer with a compact completion summary containing:

- major architecture chosen,
- model authority/config boundary,
- readiness/recovery/provisioning result,
- full regression counts,
- commit SHA/tree/parent,
- Distributed FF result,
- Evidence folder.

On blocker, state the exact contract that cannot be met and the minimal evidence proving why.

Do not begin W4C.
