# AP-SRV-070 / W5 — W5-R03 Evidence Completion
## W5-R03-E1 — Final Qualification Evidence Closure
### Model: Gemini 3.8 Flash

---

# 0. Run identity

- **Project:** AP-SRV-070
- **Phase:** W5 — Final Frozen RC Qualification
- **Parent run:** W5-R03
- **Run:** W5-R03-E1
- **Purpose:** Close the remaining evidence/accounting gaps discovered by external Root Review
- **Model:** Gemini 3.8 Flash
- **Session:** CONTINUE THE EXISTING W5-R03 GEMINI SESSION
- **Frozen RC:** W5-RC2
- **Version:** `2.0.0`
- **Commit:** `934e3be7c78aa9358f9b42b9fa4dc282bed54d6c`
- **Tree:** `2936f70ca44b7a902e1e5c7c5ca69eacc3154fdb`
- **Workspace:** continue using the existing clean qualification workspace:
  `P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-070-w5-r03`
- **Existing run root:**
  `P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W5-R03\`
- **NEW evidence-completion subfolder:**
  `P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W5-R03\Evidence\18_RootReview_Completion\`

This is **not** a new qualification run and **not** a source-correction run.

Do not create a new RC.
Do not modify tracked source.
Do not rebuild already-qualified artifacts unless explicitly required below.
Do not rerun the three Live E2E engine qualifications.
Do not rerun fresh-install qualification.
Do not rerun GitHub Actions.

The objective is only to close the exact Root Review evidence gaps below.

---

# 1. External Root Review result

W5-R03 is technically strong and the following major areas are accepted as substantiated:

- exact W5-RC2 source identity;
- GitHub Actions Windows + Ubuntu green;
- package build + twine;
- Kroko Free/Pro artifact authority;
- Free/Pro production images;
- Windows/Ubuntu fresh installed distribution;
- D7 read-only custom source;
- Faster-Whisper full Protocol-v2 Live E2E;
- Kroko Free full Protocol-v2 Live E2E;
- Kroko Pro full Protocol-v2 Live E2E;
- security/negative qualification;
- manifest producer/consumer compatibility;
- frozen source remained clean and unmodified.

Do **not** reopen those areas.

External Root Review found only these remaining issues:

## RR-1 — W5Q2-G50 was incorrectly marked PASS

Raw evidence from:

`Evidence/13_Release_Preflight/01_release_preflight.txt`

contains:

```json
{
  "passed": false
}
```

because:

```text
ghcr_repo_configured      = FAIL
dockerhub_repo_configured = FAIL
```

Specifically:

- `VOICESTT_RELEASE_GHCR_REPO` was unset
- `VOICESTT_RELEASE_DOCKERHUB_REPO` was unset

This is not equivalent to missing credentials.

The release tooling intentionally treats missing registry repository roots as hard FAIL.
Credential absence may remain WARN during W5; repository target identity may not.

Therefore W5Q2-G50 is currently **FAIL**, not PASS.

## RR-2 — W5Q2-G30 lacks execution evidence

The existing model-management evidence says the provisioner *enforces* SHA256 integrity, but does not show an actual explicit provisioning operation against the frozen RC2 runtime.

W5Q2-G30 requires:

`Explicit hash-verified provisioning PASS`

This must be demonstrated, not inferred from implementation.

## RR-3 — W5Q2-G31 lacks raw persistence evidence

The reports state that a provisioned managed model survives container destroy/recreate, but the referenced raw evidence contains no recreate/volume test.

W5Q2-G31 requires:

`Managed-store persistence over required recreate cycle PASS`

This must be demonstrated with raw evidence.

## RR-4 — Gate-index audio hash typo

The raw Faster-Whisper and Kroko Free evidence correctly records the frozen fixture:

`tests/unit/audio/asr-reference.wav`

SHA256:

`17a30810b13aaad4382a5e60a7102faeb1c624adeca6b1145fc1619579c62750`

The gate index incorrectly says `68b6d36e2f...`.

This is a reporting typo only.
Correct the gate index/reporting to the raw-evidence value.
Do not rerun the E2E tests.

## RR-5 — qualification manifest/readiness is premature until these gaps close

The current external `05_RC_MANIFEST.json` says:

`releaseReadiness: QUALIFIED`

but Root Review has not accepted W5-R03 yet.

After RR-1 through RR-4 are resolved, rebuild/refresh the external RC manifest using the same already-qualified artifact identities and validate it again.

No product/source artifact identity may change.

---

# 2. Absolute no-go boundaries

Do NOT:

- modify tracked source;
- modify tracked tests;
- modify tracked docs;
- modify VERSION;
- create a commit;
- push;
- tag;
- publish to PyPI;
- publish to GHCR;
- publish to Docker Hub;
- create GitHub Release;
- rebuild Faster-Whisper/Kroko E2E qualification;
- rebuild the package merely to obtain a different hash;
- rebuild production images merely to obtain a different image ID;
- regenerate Kroko native wheels;
- reinterpret previously passed gates.

If a source change appears necessary: STOP and report `NOT READY FOR ROOT REVIEW`.

---

# 3. Preflight registry-target rule

The release tooling explicitly refuses to invent registry namespaces.

The authoritative variables are:

- `VOICESTT_RELEASE_GHCR_REPO`
- `VOICESTT_RELEASE_DOCKERHUB_REPO`

Do not invent values.

Resolve them only from an existing operator-provided source, for example:

- already-set process/user environment;
- explicit local release configuration;
- an existing operator-maintained non-secret release configuration;
- another clearly authoritative local source.

Do not infer a Docker Hub namespace from the GitHub username.
Do not assume a GHCR path merely because the GitHub repository exists.

The values themselves are not credentials, but they are release target identities and must be exact.

If either repository root cannot be resolved from an existing operator-authoritative source:

1. do not guess;
2. write a short `NEEDS_OPERATOR_INPUT.md` under `18_RootReview_Completion`;
3. state exactly which variable(s) are missing;
4. do not perform any public operation;
5. final status remains `NOT READY FOR ROOT REVIEW`.

Once exact repository roots are available, export them process-locally for the qualification commands.

Credential variables may remain absent in W5.
Preflight may report credential `WARN`.
There must be **zero FAIL checks**.

---

# 4. W5Q2-G30 — explicit hash-verified provisioning proof

Against the exact frozen W5-RC2 runtime, perform a real supported explicit provisioning operation for a controlled catalog model.

Requirements:

1. use the production-supported model-management/provisioning path;
2. choose a model with authoritative SHA256 in the current catalog;
3. provision into the managed writable store, not the D7 read-only custom source;
4. record:
   - requested model ID/name;
   - authoritative expected SHA256;
   - resulting managed path;
   - resulting file SHA256;
   - size;
   - provisioning API/command result;
5. prove:
   - resulting SHA256 exactly equals authority;
   - no unverified artifact is accepted;
   - managed-model discovery sees the provisioned model after completion.

You may reuse an already downloaded verified source artifact as provisioning input if the supported provisioning path permits it.

Do not require a new internet download merely for theatrics.

Evidence file:

`Evidence/18_RootReview_Completion/01_explicit_provisioning.txt`

Result must be PASS for G30.

---

# 5. W5Q2-G31 — managed-store recreate persistence proof

Use the managed model from G30, or another already verified managed model produced through the supported final RC2 path.

Perform an actual container recreate cycle using a named Docker volume.

Required topology:

```text
named volume
→ mounted as the documented managed model/data store
→ container A sees verified managed model
→ record path + SHA256 + size
→ destroy container A
→ DO NOT delete named volume
→ create fresh container B from exact already-qualified RC2 image
→ same named volume mounted
→ model is rediscovered
→ path + SHA256 + size unchanged
→ runtime/model-management view recognizes the model
```

"Restart" is insufficient.
The first container must be removed and a new container created.

Record:

- named-volume identity;
- exact RC2 image ID used;
- container A identity;
- model hash before destroy;
- destroy/removal proof;
- container B identity;
- model hash after recreate;
- discovery/API proof;
- equality result.

Clean up temporary container/volume only after evidence is complete.

Evidence file:

`Evidence/18_RootReview_Completion/02_managed_store_recreate.txt`

Result must be PASS for G31.

---

# 6. Release preflight completion — W5Q2-G50

After exact registry repository roots are configured process-locally, rerun:

```text
python release.py preflight
```

with the same exact:

- version `2.0.0`;
- commit `934e3be7c78aa9358f9b42b9fa4dc282bed54d6c`;
- tree `2936f70ca44b7a902e1e5c7c5ca69eacc3154fdb`;
- RC manifest path.

Required result:

- command return code reflects successful preflight;
- JSON:
  `"passed": true`
- `ghcr_repo_configured`: PASS
- `dockerhub_repo_configured`: PASS
- no FAIL checks;
- credential absence may remain WARN;
- no public writes.

Evidence:

`Evidence/18_RootReview_Completion/03_release_preflight_pass.txt`

Do not reinterpret `"passed": false` as PASS.

---

# 7. Release dry-run confirmation

Rerun the side-effect-free dry-run after registry target identity is available.

Require:

- `sideEffectFree: true`;
- all steps `executed: false`;
- exact fixed order:
  `pypi -> ghcr -> dockerhub -> external_verification -> git_tag -> github_release -> final_verification -> complete`;
- no automatic version bump;
- version remains `2.0.0`;
- registry steps are no longer classified `unavailable` merely because their repository roots are unset.

No public writes.

Evidence:

`Evidence/18_RootReview_Completion/04_release_dryrun_with_targets.txt`

This is evidence completion only; do not perform `publish`.

---

# 8. Correct G35 reporting typo

Do not rerun E2E.

Use the already-recorded raw evidence:

`17a30810b13aaad4382a5e60a7102faeb1c624adeca6b1145fc1619579c62750`

Update external qualification reporting only:

- `03_GATE_INDEX.md`
- `06_QUALIFICATION_REPORT.md` if it contains an inconsistent fixture hash
- `07_FINAL_REPORT.md` if applicable

Do not touch repository source.

Evidence note:

`Evidence/18_RootReview_Completion/05_reporting_corrections.txt`

State that raw E2E evidence was already correct and no runtime result changed.

---

# 9. Refresh RC manifest only after gates are truly complete

After G30, G31 and G50 are PASS:

Rebuild/refresh external:

`05_RC_MANIFEST.json`

using the exact already-qualified identities.

The following MUST NOT change:

- Candidate: `W5-RC2`
- Version: `2.0.0`
- Source commit:
  `934e3be7c78aa9358f9b42b9fa4dc282bed54d6c`
- Source tree:
  `2936f70ca44b7a902e1e5c7c5ca69eacc3154fdb`
- Wheel SHA256:
  `7c131128a58464e88eb2e403c80ce00e67b19d0c0c4b0436dce37611946e68d9`
- Sdist SHA256:
  `43c1dda9669530336fe272418732b671a08c02a80e743d77066845fe4488b035`
- Kroko Free fingerprint:
  `ab8986fd7fb93756`
- Kroko Free artifact SHA256:
  `df99ecb1def4a9a62cede4f708e76d0e42953f61e17541f0f7ec20641ed74952`
- Kroko Pro fingerprint:
  `36b440630c0a9475`
- Kroko Pro artifact SHA256:
  `37ae1630cf239f0bbe41abb1b47f90623eb0a8402803af98e27048c382f6ef43`
- Free image ID:
  `sha256:c4ec6a2888b14f23256db771dafcccdbd5ba972323f3c3c15c56c45ca541ebf9`
- Pro image ID:
  `sha256:a6c01686ccae6bb2af0e59c3d6c80c733912df2c7773b2172e680293b65d6269`

Qualification timestamp / evidence reference / manifest file SHA may legitimately change.

Run:

`release.py manifest validate`

and preserve output.

Evidence:

`Evidence/18_RootReview_Completion/06_manifest_refresh.txt`

---

# 10. Correct gate accounting

Re-evaluate all 62 gates without rerunning already accepted areas.

The following gates require NEW evidence in E1:

- **W5Q2-G30**
- **W5Q2-G31**
- **W5Q2-G50**

The following requires reporting correction only:

- **W5Q2-G35**

The following must be re-evaluated after the above:

- **W5Q2-G51**
- **W5Q2-G52**
- **W5Q2-G53**
- **W5Q2-G54**
- **W5Q2-G55**
- **W5Q2-G56**
- **W5Q2-G62**

All other already-substantiated gates may reference the existing W5-R03 evidence.

Do not duplicate expensive qualification.

---

# 11. Final Git integrity

At the end verify again:

```text
HEAD = 934e3be7c78aa9358f9b42b9fa4dc282bed54d6c
TREE = 2936f70ca44b7a902e1e5c7c5ca69eacc3154fdb
VERSION = 2.0.0
git status --porcelain = empty
Distributed remote = same exact commit
```

No commit.
No push.
No tag.
No release.
No registry publication.

Evidence:

`Evidence/18_RootReview_Completion/07_final_integrity.txt`

---

# 12. Final reports

Update external:

- `03_GATE_INDEX.md`
- `04_DEVIATIONS.md`
- `06_QUALIFICATION_REPORT.md`
- `07_FINAL_REPORT.md`

The deviation report must acknowledge the Root Review evidence correction:

- initial preflight was not passing because registry target identities were unset;
- G30/G31 initially lacked raw execution evidence;
- G35 had a reporting-only hash typo;
- no source defect was found;
- no RC identity changed.

If every mandatory gate is now actually supported:

`07_FINAL_REPORT.md` begins:

`READY FOR ROOT REVIEW`

and reports:

```text
Internal Candidate: W5-RC2
Version: 2.0.0
Commit: 934e3be7c78aa9358f9b42b9fa4dc282bed54d6c
Tree: 2936f70ca44b7a902e1e5c7c5ca69eacc3154fdb
Mandatory gates: 62/62 PASS
Preflight passed: true
Public writes: 0
```

If registry target identities are still unavailable or any new mandatory proof fails:

`NOT READY FOR ROOT REVIEW`

Do not invent a PASS.

---

# 13. Success condition

This evidence completion succeeds only when:

```text
G30 real explicit hash-verified provisioning PASS
+
G31 real named-volume destroy/recreate persistence PASS
+
G50 release.py preflight JSON passed=true
+
dry-run has exact W6 graph with target repositories configured
+
G35 reporting corrected to 17a30810...
+
manifest refreshed and VALID
+
62/62 gates honestly supported
+
frozen source remains bit-identical
+
zero public writes
```

Then stop.

Do not perform any additional qualification or optimization.

This is intended to be the final W5 evidence closure before external Root PASS.
