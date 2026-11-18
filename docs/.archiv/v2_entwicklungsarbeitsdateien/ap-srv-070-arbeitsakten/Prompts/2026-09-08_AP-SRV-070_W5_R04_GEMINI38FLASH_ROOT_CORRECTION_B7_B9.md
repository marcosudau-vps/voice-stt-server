# AP-SRV-070 / W5-R04 — Root Review Correction B7–B9

## 0. Run mode

**Model:** Gemini 3.8 Flash
**Session:** CONTINUE THE EXISTING GEMINI SESSION
**Workspace:** continue the existing W5-R04 workspace
**Run identity:** remains W5-R04 — do NOT create W5-R05
**Task type:** final narrow external-Root-Review correction

Workspace:

`P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-070-w5-r04`

Working branch:

`work/ap-srv-070-w5-r04`

Binding durable parent:

`934e3be7c78aa9358f9b42b9fa4dc282bed54d6c`

Current local / temporary-review commit rejected by this Root Review:

`40a6eee93102b8355067973e94368b55ed2bf049`

Current tree:

`7aa37473f44dcf39587c33dc3cde1fe0caed7ed0`

Temporary inspection branch currently points to that rejected commit:

`review/ap-srv-070-w5-r04-root`

Remote durable Distributed branch must remain unchanged at:

`934e3be7c78aa9358f9b42b9fa4dc282bed54d6c`

Evidence root:

`P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W5-R04\`

---

# 1. Root Review status and hard scope boundary

The external Root Review directly inspected commit `40a6eee...` on GitHub.

The following previous findings are now accepted and CLOSED:

- B1 — GitHub publish workflow permissions
- B2 — Linux + Windows public distribution wheel candidate matrix
- B3 — QUALIFIED publication barrier
- B5 — current PyPI release-specific JSON uses top-level `urls`
- B6 — workflow input `version` is validated against candidate `productVersion`
- E1 — staging evidence wording is internally consistent

Do not reopen or redesign them.

The review found exactly three remaining deterministic defects:

- **B7:** `_cmd_publish()` uses an undefined local variable `version` on the real publish happy path.
- **B8:** annotated Git tags are created, but remote tag verification does not peel the annotated tag to its commit; additionally local-only tag state after a failed push is incorrectly treated as a completed remote tag.
- **B9:** the candidate SHA256 inventory is generated before `rc-manifest.json` is changed from `NOT_QUALIFIED` to `QUALIFIED`, so the uploaded inventory contains a stale hash for the final manifest.

Only B7–B9 plus directly necessary tests/evidence are in scope.

---

# 2. B7 — fix the real publish happy path (`version` NameError)

## Concrete defect

In `release_tooling/cli.py`, `_cmd_publish()` now computes:

```python
expected_version = args.version or manifest["productVersion"]
```

but later uses an undefined variable:

```python
state_path = Path(args.state_file) if args.state_file else default_state_path(repo_root, version)
...
new_state(version=version, ...)
...
ensure_same_version(state, version)
```

There is no local assignment to `version`.

Therefore, after preflight passes, every real publish invocation reaches a deterministic `NameError` before the engine can execute.

## Required correction

Use exactly one canonical local value derived from the candidate manifest after the optional operator/dispatch-version equality assertion:

```python
version = manifest["productVersion"]
```

Use it consistently for:

- preflight expected version;
- release-state path;
- new state;
- same-version resume validation.

`--version` remains an asserted expected value only. The candidate manifest remains the release identity authority.

## Required regression test

The existing positive version test intentionally fails later at preflight and therefore never exercises the successful path.

Add a test that:

1. supplies a valid QUALIFIED manifest;
2. makes preflight return PASS;
3. mocks all external/mutative adapters and the engine;
4. executes the publish command through state construction/loading;
5. proves no `NameError`;
6. proves the state/engine version equals the manifest `productVersion`;
7. performs zero real tag/public write.

---

# 3. B8 — annotated remote Git tag verification and local-only resume semantics

## Concrete defect A: annotated tag is not peeled remotely

`release_tooling/gitinfo.py` creates release tags as annotated tags:

```text
git tag -a <tag> <commit> -m <tag>
```

But `remote_tag_commit()` currently runs:

```text
git ls-remote --tags <remote> refs/tags/<tag>
```

and returns that SHA verbatim.

For an annotated tag, this is the **tag-object SHA**, not the target commit SHA.

`GitTagAdapter.verify()` then compares that tag-object SHA against `manifest["sourceCommit"]`.

Thus the normal successful path becomes:

```text
tag absent
→ create annotated tag
→ push succeeds
→ post-publish verify
→ remote_tag_commit returns tag-object SHA
→ != sourceCommit
→ false CONFLICT
```

This was independently reproduced by the external Root Review with a temporary local repository and bare remote.

## Required fix A

`remote_tag_commit()` must return the commit the remote tag ultimately resolves to for both annotated and lightweight tags.

A robust implementation may query both:

```text
refs/tags/<tag>
refs/tags/<tag>^{}
```

Then:

- prefer the peeled `^{}`
  SHA when present;
- otherwise use the exact ref SHA for a lightweight tag;
- reject malformed or ambiguous output fail-closed.

Do not compare an annotated tag-object SHA to a commit SHA.

## Concrete defect B: local-only tag is treated as remotely complete

Current `GitTagAdapter.verify()` effectively uses:

```python
existing = remote_commit or local_commit
```

If local annotated tag creation succeeded but the push failed, a retry in the same checkout sees:

```text
local tag = correct
remote tag = absent
```

and incorrectly returns MATCH.

The state machine can therefore advance to TAGGED even though the immutable release tag does not exist on the remote.

## Required semantics

### Remote tag exists

- remote peeled commit differs from expected → CONFLICT
- remote peeled commit equals expected → MATCH
- conflicting local tag must also fail closed

### Remote tag absent

- conflicting local tag → CONFLICT
- correct local tag only → ABSENT, because remote publication is incomplete
- no local tag → ABSENT

## Required publish retry behavior

If remote is absent:

- correct local tag already exists → do **not** recreate it; push it
- no local tag → create annotated tag, then push
- conflicting local tag → hard stop
- never delete, move, replace, or force-rewrite a release tag

## Required tests

Do not test this solely by mocking `remote_tag_commit()`.

Add at least one real local Git integration test using temporary repositories and a temporary bare remote:

1. initialize source repo and commit;
2. create annotated tag;
3. push to bare remote;
4. assert `remote_tag_commit()` returns the target commit and not the tag-object SHA.

Also cover:

- lightweight remote tag;
- conflicting remote tag;
- correct local tag + remote absent → ABSENT;
- publish retry with correct local tag + remote absent pushes without recreating;
- conflicting local tag remains fail-closed.

No external network is required.

---

# 4. B9 — final candidate SHA256 inventory must describe final QUALIFIED bytes

## Concrete defect

Current `.github/workflows/release-candidate.yml` performs:

```text
assemble rc-manifest.json as NOT_QUALIFIED
→ validate
→ package smoke
→ build sha256-inventory.json
→ manifest qualify rewrites rc-manifest.json
→ validate QUALIFIED
→ upload both
```

`tools/release_candidate.build_inventory()` hashes regular files under the candidate directory and excludes only the inventory itself.

Therefore the generated inventory contains the SHA256 of the old `NOT_QUALIFIED` `rc-manifest.json`.

Qualification then rewrites that manifest.

The uploaded evidence pair is inconsistent:

```text
uploaded rc-manifest.json = QUALIFIED bytes
inventory hash for rc-manifest.json = old NOT_QUALIFIED bytes
```

## Required correction

Finalize inventory only after the candidate manifest has reached its final QUALIFIED bytes.

Required order:

```text
assemble NOT_QUALIFIED
→ validate
→ package smoke
→ qualify
→ validate QUALIFIED
→ build final SHA256 inventory
→ verify every inventory entry against actual files
→ upload candidate artifacts
```

The inventory itself remains excluded from its own inventory.

Add a verification helper/step immediately before upload that fails if any listed path size/hash no longer matches.

At minimum the inventory entry for `rc-manifest.json` must exactly match the final qualified file.

## Required tests

Add a regression test that:

1. writes NOT_QUALIFIED manifest;
2. qualifies it;
3. builds final inventory;
4. asserts inventory SHA for `rc-manifest.json` equals actual final file SHA.

Also add/update workflow contract tests proving:

- qualification precedes inventory generation;
- inventory generation precedes artifact upload;
- a final inventory verification step exists before upload.

---

# 5. Hard scope boundary

Do NOT reopen:

- B1 permissions
- B2 platform matrix
- B3 qualification model
- B4/B5 PyPI precheck architecture
- B6 version/concurrency guard
- release state order
- Docker Hub → GHCR promotion
- alias semantics
- GitHub Release ordering
- Free/Pro package identities
- import/CLI authority
- no-sdist decision
- Kroko build authority
- docs/product surface
- application functionality
- model management

No unrelated hardening or refactor.

---

# 6. Verification

Run focused tests first, including at minimum:

- `tests/unit/test_release_cli.py`
- `tests/unit/test_release_adapters.py`
- new/appropriate Git-tag integration tests
- `tests/unit/test_release_workflows.py`
- candidate/inventory tests
- directly affected state/engine tests

Then run the complete affected release/build test set.

After the corrected tracked tree is frozen, run the final full regressions again.

## Windows

```powershell
python -m pytest -q --basetemp=<fresh-unique-dir> tests/unit
```

## Ubuntu 24.04 / WSL2 native ext4

Refresh `/home/marco/w5r04-native-src` from the corrected final worktree and run:

```bash
/home/marco/w5r02c1-ubuntu-test/bin/python -m pytest -q tests/unit
```

Also run:

```powershell
git diff --check
```

Do not make a tracked edit after the final successful regressions unless a concrete test failure requires it. If a tracked edit occurs, rerun the affected final verification.

---

# 7. Evidence

Update the existing W5-R04 evidence set only:

- `05_CHANGED_FILES.md`
- `06_TEST_MATRIX.md`
- `07_GATE_INDEX.md`
- `08_DEVIATIONS.md`
- `09_FINAL_REPORT.md`

Record explicitly:

```text
External Root Review of 40a6eee93102b8355067973e94368b55ed2bf049:
FAIL

Accepted and kept closed:
B1, B2, B3, B5, B6, E1

Remaining findings corrected:
B7 - real publish happy-path version NameError
B8 - annotated remote tag peeling + local-only tag resume
B9 - stale pre-qualification RC-manifest hash in final candidate inventory
```

Archive the new corrected final diff and SHA256.

Do not erase previous rejected review history.

---

# 8. Git

The current commit `40a6eee...` is not Root-approved.

After all final tests pass:

```powershell
git add -A
git commit --amend --no-edit
```

The resulting commit must remain the **single W5-R04 commit directly parented to**:

`934e3be7c78aa9358f9b42b9fa4dc282bed54d6c`

Verify:

```powershell
git rev-parse HEAD
git rev-parse "HEAD^{tree}"
git rev-parse HEAD^
git status --porcelain=v1
git rev-parse origin/feat/einheitliche-triggerarchitektur-distributed
```

Distributed must remain unchanged until external Root PASS.

---

# 9. Temporary Dirty Review branch update

The disposable review branch currently points to the rejected commit:

`review/ap-srv-070-w5-r04-root = 40a6eee93102b8355067973e94368b55ed2bf049`

Because the corrected commit is produced via amend, the branch update is non-fast-forward.

A force update is explicitly authorized **only for this disposable review branch**, and only with force-with-lease against the exact expected old SHA.

Before pushing, verify the remote review branch is still exactly `40a6eee...`.

Preferred command:

```powershell
git push --force-with-lease=refs/heads/review/ap-srv-070-w5-r04-root:40a6eee93102b8355067973e94368b55ed2bf049 `
  origin HEAD:refs/heads/review/ap-srv-070-w5-r04-root
```

Afterward verify the temporary remote branch points exactly to the new corrected commit.

Absolutely no force push to:

- `feat/einheitliche-triggerarchitektur-distributed`
- `feat/einheitliche-triggerarchitektur`
- `main`

No Git tag.
No PyPI/TestPyPI write.
No Docker Hub write.
No public GHCR write.
No private staging write.
No GitHub Release.

---

# 10. Final report

If and only if B7–B9 are closed and all mandatory verification passes, `09_FINAL_REPORT.md` begins:

`READY FOR ROOT REVIEW`

Include:

- rejected review commit `40a6eee...`;
- new corrected commit/tree/parent;
- B7 correction plus positive publish-happy-path test;
- B8 real annotated-tag integration proof and local-only resume proof;
- B9 final inventory / final QUALIFIED-manifest proof;
- targeted test counts;
- Windows full regression;
- Ubuntu full regression;
- `git diff --check`;
- literal clean worktree;
- Distributed still unchanged;
- temporary review branch at exact corrected SHA;
- zero tag/PyPI/DockerHub/GHCR/staging/GitHub Release writes.

Never claim Root PASS.

Do exactly this and stop.
