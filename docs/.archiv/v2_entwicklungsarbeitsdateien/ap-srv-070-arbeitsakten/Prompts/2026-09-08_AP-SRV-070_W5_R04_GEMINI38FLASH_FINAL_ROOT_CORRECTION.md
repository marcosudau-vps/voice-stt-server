# AP-SRV-070 / W5-R04 — Final Root Correction B5 + B6

## Run mode

**Model:** Gemini 3.8 Flash
**Session:** CONTINUE THE EXISTING GEMINI SESSION
**Workspace:** continue the existing W5-R04 workspace
**Task type:** final narrow Root-Review correction only

Workspace:

`P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-070-w5-r04`

Working branch:

`work/ap-srv-070-w5-r04`

Binding durable parent:

`934e3be7c78aa9358f9b42b9fa4dc282bed54d6c`

Current local corrected commit under review:

`202bedadd4a2448e7ab11fb11b2567053b46a2e1`

Current tree:

`3102e6cb1e036e95fa8109e909e8380117cf337c`

Remote Distributed branch must remain:

`934e3be7c78aa9358f9b42b9fa4dc282bed54d6c`

Evidence root:

`P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W5-R04\`

This remains **W5-R04**. Do not create W5-R05.

---

# 1. Root-review status

The external Root Review accepts the previous corrections:

- **B1 PASS:** publish workflow permissions
- **B2 PASS:** Linux + Windows public-wheel candidate matrix
- **B3 PASS:** QUALIFIED publication barrier
- **E1 PASS:** staging evidence consistency

Do not reopen those areas.

The review found exactly two remaining deterministic release-infrastructure defects:

- **B5:** PyPI release JSON is parsed using an API shape that the release-specific PyPI endpoint no longer returns.
- **B6:** `workflow_dispatch.inputs.version` controls the publish concurrency key but is not validated against the downloaded candidate manifest version.

Only B5 and B6 are in scope.

---

# 2. B5 — Fix PyPI read-only precheck against the real current API

## Concrete defect

`release_tooling.remote_checks.inspect_pypi_release()` requests:

`https://pypi.org/pypi/<project>/<version>/json`

but currently reads files from:

```python
payload.get("releases", {}).get(version, [])
```

The current official PyPI release-specific JSON endpoint explicitly **does not include `releases`**. Its files for that exact release are in the top-level:

```json
"urls": [...]
```

Therefore an existing exact release currently appears to this code as if none of its files were present.

That breaks the intended B4 semantics:

```text
ABSENT   -> publish missing exact files
MATCH    -> resume safely
CONFLICT -> STOP before write
UNKNOWN  -> STOP before write
```

and also breaks post-write PyPI verification.

This is a concrete release blocker.

## Required fix

Keep the release-specific endpoint because it is already scoped to the exact version.

Parse the current response using the top-level `urls` list.

For each object in `payload["urls"]`, read:

- `filename`
- `digests.sha256`

Do not use the removed release-specific `releases` key.

Fail closed if a 200 response is structurally unusable in a way that prevents reliable identity verification. Do not silently convert malformed/unexpected API data into ABSENT.

404 remains genuine ABSENT.

Network / HTTP / malformed verification state remains UNKNOWN / `VerificationUnavailableError`.

Keep the existing conflict semantics for:

- unexpected files;
- same filename with wrong SHA256;
- partial MATCH + ABSENT;
- exact full MATCH.

## Tests

Update the fake PyPI fetcher and relevant tests so they mirror the **current real release-specific PyPI JSON shape**, e.g.:

```json
{
  "info": {"name": "...", "version": "2.0.0"},
  "urls": [
    {
      "filename": "...whl",
      "digests": {"sha256": "..."}
    }
  ]
}
```

Add at least these regression cases:

1. current release-specific `urls` shape yields MATCH;
2. wrong SHA in `urls` yields CONFLICT;
3. missing expected file with another unexpected file yields CONFLICT;
4. partial candidate files yield PARTIAL / missing-file staging behavior;
5. response with no usable `urls` field after a successful existing-release response fails closed rather than being mistaken for a safe empty release, unless the exact API semantics make an empty `urls` list a valid known state and this is documented/tested;
6. 404 remains ABSENT;
7. precheck and post-write adapter verification use the same corrected semantics.

Do not introduce a live network dependency into unit tests.

Document in the test/source comment that the shape matches the current official PyPI release JSON API.

---

# 3. B6 — Validate workflow input version against candidate version

## Concrete defect

`.github/workflows/release-publish.yml` accepts:

```yaml
inputs:
  version:
    required: true
```

and uses it for:

```yaml
concurrency:
  group: release-publish-${{ inputs.version }}
```

but the workflow never verifies that this input equals:

```json
rc-manifest.json -> productVersion
```

The actual release engine publishes the manifest version, not the workflow input.

Therefore:

```text
candidate = 2.0.0
workflow input = 2.0.1
```

would execute in concurrency group `release-publish-2.0.1` while attempting to publish `2.0.0`.

That makes the stated per-version serialization bypassable by a typo or wrong dispatch input.

## Required fix

Before the first mutative release action (before tag creation), after the candidate manifest has been downloaded, fail closed unless:

```text
inputs.version == manifest.productVersion
```

The check must occur in the `tag` job before `release.py publish --until TAGGED`.

Do not merely document the requirement.

Prefer a small source-controlled CLI/preflight check if that naturally fits the existing release authority; otherwise a minimal workflow check is acceptable.

Do not duplicate release semantics unnecessarily.

## Tests

Extend workflow/release tests to prove:

- candidate version MATCH proceeds;
- candidate version mismatch fails before tag/public write;
- the concurrency key remains based on the explicitly validated version;
- no broader workflow permissions are introduced.

---

# 4. Scope boundary

Do NOT reopen or redesign:

- B1 permissions architecture
- B2 platform matrix
- B3 qualification model
- B4 overall precheck/OIDC architecture beyond the PyPI API-shape fix required by B5
- E1 evidence
- state order
- Docker Hub -> GHCR promotion
- aliases
- GitHub Release ordering
- PyPI Free/Pro product split
- packaging/import/CLI authority
- no-sdist decision
- Kroko build authority
- README/docs engine surface
- model management
- any application functionality

No new feature work.

---

# 5. Verification

Run focused tests first, including at least:

- `test_release_remote_checks.py`
- `test_release_cli.py`
- `test_release_adapters.py`
- `test_release_workflows.py`
- any directly affected preflight/engine tests

Then run the complete affected release/build test set.

After the corrected tracked tree is frozen, rerun:

### Windows

```powershell
python -m pytest -q --basetemp=<fresh-unique-dir> tests/unit
```

### Ubuntu 24.04 / WSL2 native ext4

Refresh the native ext4 source copy from the final corrected worktree, then:

```bash
python -m pytest -q tests/unit
```

Also run:

```powershell
git diff --check
```

No tracked edit after the final successful regressions unless a concrete test defect forces it.

---

# 6. Evidence

Update the existing W5-R04 evidence set only.

At minimum:

- `05_CHANGED_FILES.md`
- `06_TEST_MATRIX.md`
- `07_GATE_INDEX.md`
- `08_DEVIATIONS.md`
- `09_FINAL_REPORT.md`

Record that:

```text
External Root Review on 202bedadd4a2448e7ab11fb11b2567053b46a2e1:
FAIL

Accepted from prior correction:
B1, B2, B3, E1

Remaining findings corrected:
B5 - current PyPI release JSON API shape
B6 - workflow input version validation
```

Do not erase prior failed-review history.

Archive the new corrected final diff and SHA256.

---

# 7. Git

The current commit `202bedadd4a2448e7ab11fb11b2567053b46a2e1` is local, unpushed, and has failed Root Review.

After all final tests pass:

```powershell
git add -A
git commit --amend --no-edit
```

This amend is explicitly authorized.

The resulting commit must still be the **single W5-R04 commit directly parented to**:

`934e3be7c78aa9358f9b42b9fa4dc282bed54d6c`

Then capture:

```powershell
git rev-parse HEAD
git rev-parse "HEAD^{tree}"
git rev-parse HEAD^
git status --porcelain=v1
git rev-parse origin/feat/einheitliche-triggerarchitektur-distributed
```

---

# 8. Dirty Review Push — explicitly authorized

After the corrected final commit exists, tests are green, evidence is updated, and the worktree is clean, a **temporary review-only Dirty Push is authorized** so the external Root Review can inspect the exact commit directly on GitHub.

Push the corrected commit only to this temporary branch:

`review/ap-srv-070-w5-r04-root`

Requirements:

- the temporary branch must point exactly to the corrected final local commit;
- do NOT push to `feat/einheitliche-triggerarchitektur-distributed`;
- do NOT touch `feat/einheitliche-triggerarchitektur`;
- do NOT touch `main`;
- do NOT create or push a tag;
- no force push to any durable branch;
- no PyPI/DockerHub/GHCR/staging/GitHub Release write.

This temporary branch is inspection-only and may be deleted after external Root Review.

Record the pushed review branch SHA in the evidence.

This Dirty Review Push is **not** publication approval and **not** Root PASS.

---

# 9. Final report

If B5 and B6 are closed and all required tests pass, begin:

`READY FOR ROOT REVIEW`

Include:

- superseded commit `202bedadd4a2448e7ab11fb11b2567053b46a2e1`;
- new corrected commit/tree/parent;
- B5 exact API correction;
- B6 version/concurrency correction;
- final test counts;
- clean worktree;
- Distributed remote still unchanged;
- temporary review branch SHA if pushed;
- zero tag/PyPI/DockerHub/GHCR/staging/GitHub Release writes.

Never claim Root PASS.

Do exactly this and stop.
