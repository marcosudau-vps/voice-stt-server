# AP-SRV-070 / W5-R04 — Gemini 3.8 Flash Resume & Closure

## 0. Run mode

**Model:** Gemini 3.8 Flash
**Session:** NEW SESSION
**Task type:** narrow continuation / closure of the already substantially completed W5-R04 run
**Do not start a new implementation design. Do not create a new workspace.**

Continue the existing workspace:

`P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-070-w5-r04`

Existing local branch:

`work/ap-srv-070-w5-r04`

Binding start commit / required direct parent of the final commit:

`934e3be7c78aa9358f9b42b9fa4dc282bed54d6c`

Binding start tree:

`2936f70ca44b7a902e1e5c7c5ca69eacc3154fdb`

VERSION remains:

`2.0.0`

Evidence root:

`P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W5-R04\`

Original prompt copy:

`P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W5-R04\00_PROMPT.md`

Current abort report:

`P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Runs\W5-R04\09_FINAL_REPORT.md`

Read the original prompt and the current final report fully before doing anything else.

---

# 1. Critical continuation authority

Claude Opus 5 completed the substantive W5-R04 implementation but the session was stopped because the model limit was exhausted before the formal closing sequence.

This is **not a new implementation run**.

The current `09_FINAL_REPORT.md` states `NOT READY FOR ROOT REVIEW` for three concrete completion reasons only:

1. no final commit exists;
2. Windows and Ubuntu full regressions were green but ran before the last documentation edits, so they are not formal evidence for the final tree;
3. one intended documentation correction in `docs/fastapi-server.md` did not apply.

Unless your verification finds a **concrete reproducible defect**, treat all other implementation work as closed.

## Hard boundary

Do **not**:

- redesign the release architecture;
- rewrite release tooling;
- restructure workflows;
- refactor packaging;
- alter the candidate model;
- change release ordering;
- add features;
- add model-image functionality;
- revisit closed product areas;
- “improve” code style or architecture;
- create extra commits;
- push anything;
- create a tag;
- publish anything;
- perform staging/public registry writes.

A source-code change beyond the single known documentation correction is allowed **only** if a required verification step exposes a concrete reproducible blocker. If that occurs, document the blocker precisely before changing anything and keep the correction minimal.

The goal is to finish the existing run, not to make it better.

---

# 2. Newer binding product/packaging authority

The original W5-R04 prompt was supplemented during the run. The newer decisions override older conflicting assumptions.

The implemented and binding product identity is:

## PyPI Free

`voice-stt-server`

Contains the complete normal server distribution including the Kroko Free native runtime.

## PyPI Pro

`voice-stt-server-pro`

Contains the complete Pro server distribution including the Kroko Pro native runtime.

The two distributions are alternative installations, not co-installed packages.

Both expose the same canonical Python import:

`voice_stt_server`

Example:

```python
from voice_stt_server import AudioToTextRecorder
```

Both expose the same canonical CLI:

`voice-stt-server`

Legacy import/CLI compatibility may remain where already implemented.

There are **no separate public Kroko PyPI distributions**.

The native Kroko Free/Pro artifacts are internal build/candidate artifacts embedded into the corresponding complete VoiceSTT distribution wheels.

There is **no sdist publication for these native distributions** if an sdist would violate the requirement that a supported `pip install voice-stt-server` / `voice-stt-server-pro` needs no local Kroko native build. This later binding authority supersedes the original generic sdist requirement.

Do not re-open this decision.

Docker remains:

Free:
- `marcosudau/voice-stt-server`
- `ghcr.io/marcosudau-vps/voice-stt-server`

Pro:
- `marcosudau/voice-stt-server-pro`
- `ghcr.io/marcosudau-vps/voice-stt-server-pro`

No model-image feature is part of this release.

---

# 3. GitHub-native build authority — binding clarification

The authoritative release candidate must be built **only in GitHub Actions from a clean checkout of the exact repository commit**.

Binding invariant:

`Repository → GitHub Build → GitHub Qualification → Approval → publication of the exact same qualified artifacts`

The local developer PC is not:

- Build Authority,
- Candidate Authority,
- Qualification Authority,
- Publication Authority.

The local empty-artifact-store proof already performed by Claude is only a structural pre-push feasibility proof. It must not be turned into a local release path.

Do not introduce any dependency on:

- local prebuilt VoiceSTT wheels;
- local Kroko wheels;
- local production images;
- a local Kroko artifact store;
- locally produced candidate artifacts;
- local release credentials.

After Root PASS and the exact push, GitHub's clean-runner candidate/qualification path is authoritative.

Do not make additional architecture changes here unless current files actually violate this invariant.

---

# 4. Current documented state from the aborted Claude run

The current report records:

- HEAD still `934e3be7c78aa9358f9b42b9fa4dc282bed54d6c`;
- remote Distributed branch unchanged at that commit;
- no commit from W5-R04 yet;
- no push;
- no Git tag;
- no PyPI upload;
- no Docker Hub push;
- no public GHCR write;
- no staging push;
- implementation substantially complete in the worktree;
- Windows full suite passed:
  `1894 passed, 14 skipped, 1213 subtests, 0 failures`;
- Ubuntu 24.04 full suite passed:
  `1894 passed, 14 skipped, 1213 subtests, 0 failures`;
- those two full runs were against the pre-final tree;
- targeted release/build/docs/workflow tests were green on the final implementation as last individually run;
- the one known unapplied edit is `docs/fastapi-server.md`.

Do not trust these statements blindly: verify the current literal repository state first. But do not redo already completed work just to obtain fresh evidence if it is not required by the closing gates.

---

# 5. Step 1 — literal resume preflight

Before modifying anything, capture and record:

```powershell
git status --short
git status --porcelain=v1
git rev-parse HEAD
git rev-parse "HEAD^{tree}"
git branch --show-current
git rev-parse origin/feat/einheitliche-triggerarchitektur-distributed
git diff --cached --stat
git diff --stat
```

Also determine whether the existing implementation changes are staged, unstaged, or mixed.

Expected baseline:

- branch `work/ap-srv-070-w5-r04`;
- HEAD `934e3be7...`;
- remote Distributed `934e3be7...`;
- dirty worktree containing the uncommitted W5-R04 implementation;
- zero W5-R04 commits.

If the repository identity differs materially, stop and document `NOT READY FOR ROOT REVIEW` rather than guessing.

Do not reset, checkout, restore, clean, rebase, amend, or otherwise discard existing work.

---

# 6. Step 2 — inspect the known documentation defect only

Inspect:

`docs/fastapi-server.md`

The abort report says this file still exposes `whisper_cpp` and `sherpa_onnx_moonshine` server recipes without making clear that they are internal/experimental rather than supported production engines.

The current maintained product surface must advertise only:

- Faster-Whisper
- Kroko-ONNX

as supported production STT engines.

The equivalent correction in `docs/quick-start.md` already applied.

Make the **smallest truthful correction** to `docs/fastapi-server.md` required to align it with the final documentation authority.

Do not use this as an excuse to rewrite the whole file.

After the edit, run the relevant documentation/link guard tests first.

If those tests fail because another maintained documentation file violates the same already-defined product-surface rule, make only the minimum documentation correction necessary. Do not change source architecture.

---

# 7. Step 3 — freeze the final tracked tree before full regressions

After the documentation correction and targeted documentation tests:

1. inspect all tracked changes;
2. run `git diff --check`;
3. verify no accidental `.env`, secret, build output, large binary, model data, wheel, archive, runtime data, or generated release artifact is tracked;
4. verify the diff is still within W5-R04 scope;
5. archive the exact final pre-commit diff for Root Review.

Important:

Once the full Windows/Ubuntu regressions begin, **do not make any further tracked edit unless a required test exposes a concrete blocker**.

Record an identity for the exact tested tree. Since the final implementation is still uncommitted, record at minimum:

- HEAD;
- staged/working diff SHA256 or equivalent deterministic diff identity;
- `git diff --cached --stat`;
- `git diff --stat`;
- literal status.

The final commit must contain exactly this tested tracked tree.

---

# 8. Step 4 — required final-tree verification

## 8.1 Targeted suites

Re-run the targeted suites needed for gates G61-G64 against the final tree:

- release tooling;
- build/Kroko;
- workflow/YAML/permission/trigger guards;
- documentation/link guards.

Use the existing test commands/evidence conventions from W5-R04 rather than inventing a new matrix.

All must PASS.

## 8.2 Windows full regression — G65

Run against the final tree:

```powershell
python -m pytest -q --basetemp=<fresh-unique-directory> tests/unit
```

The abort report notes that:

`C:\Users\user\AppData\Local\Temp\pytest-of-marco`

may be locked, therefore an explicit fresh `--basetemp` is required.

Expected prior reference count:

`1894 passed, 14 skipped, 1213 subtests, 0 failures`

Do not hard-code PASS based on that count. Record the actual final-tree result.

## 8.3 Ubuntu 24.04 full regression — G66

The previous established test environment is:

`/home/marco/w5r02c1-ubuntu-test/bin/python`

and a previous source copy exists at:

`/home/marco/w5r04-native-src`

**Refresh/recreate the Ubuntu native-ext4 source copy from the current final Windows worktree before running the final test.** Do not accidentally test the stale pre-final copy.

Then run the full `tests/unit` suite under Ubuntu 24.04 / WSL2 native ext4 using the established environment.

Expected prior reference count:

`1894 passed, 14 skipped, 1213 subtests, 0 failures`

Again, record the actual final-tree result.

If either full suite fails, diagnose first.

- If failure is environment-only and cannot satisfy the mandatory PASS gate, final status remains `NOT READY FOR ROOT REVIEW`.
- If a concrete source defect is exposed, make only the narrow required correction, then all affected final-tree verification must be repeated.
- Do not broaden scope.

---

# 9. Step 5 — complete the evidence set

Complete/update these files under the existing W5-R04 evidence root:

- `06_TEST_MATRIX.md`
- `07_GATE_INDEX.md`
- `08_DEVIATIONS.md`
- `09_FINAL_REPORT.md`

Do not overwrite historical/raw evidence unnecessarily.

Use the already captured evidence and the final-tree verification.

## 9.1 `06_TEST_MATRIX.md`

Include:

- targeted suite commands and results;
- Windows final-tree full regression command/result/count;
- Ubuntu final-tree full regression command/result/count;
- `git diff --check`;
- relevant security/scope checks;
- exact tested-tree identity.

## 9.2 `07_GATE_INDEX.md`

Account for **all W5R4-G01 through W5R4-G75**.

Do not silently mark a gate N/A.

Where the original prompt's generic sdist wording conflicts with the later binding native-distribution authority, explicitly state that the later authority supersedes it and cite the implementation-plan / architecture-decision addendum. Do not fabricate an sdist merely to satisfy obsolete wording.

The gate index must make the authority change visible rather than hiding it.

## 9.3 `08_DEVIATIONS.md`

Use the existing project archive deviation record:

`docs/.archiv/einheitliche_triggerarchitektur/AP-SRV-070/2026-09-08_W5_R04_ABWEICHUNGEN.md`

as source, plus any actual closing-run deviation.

Do not invent deviations.

## 9.4 `09_FINAL_REPORT.md`

Replace the abort report only after all mandatory closing gates are actually satisfied.

It must begin exactly:

`READY FOR ROOT REVIEW`

or:

`NOT READY FOR ROOT REVIEW`

Never claim Root PASS.

---

# 10. Step 6 — create the one and only W5-R04 commit

Only if every required final-tree verification is green and no unresolved blocker remains:

Create exactly one local commit.

Required commit message:

`AP-SRV-070 W5: finalize GitHub-native release infrastructure`

Requirements:

- direct parent exactly:
  `934e3be7c78aa9358f9b42b9fa4dc282bed54d6c`;
- exactly one W5-R04 implementation commit;
- include the complete intended tracked W5-R04 implementation;
- no extra cleanup commit;
- no amend after evidence is finalized;
- no push.

After commit capture:

```powershell
git rev-parse HEAD
git rev-parse "HEAD^{tree}"
git rev-parse HEAD^
git log -1 --format="%H%n%T%n%P%n%s"
git status --porcelain=v1
git rev-parse origin/feat/einheitliche-triggerarchitektur-distributed
```

Mandatory final conditions:

- parent is exact start commit;
- final workspace literally clean;
- remote Distributed still exact `934e3be7...`;
- no public/staging write occurred.

Also verify the committed tree is exactly the same tracked tree that passed the final regressions. No tracked edit may occur between final successful regression and commit except changes required solely to evidence files outside the repository.

---

# 11. Final report contents if READY

If all gates are satisfied, `09_FINAL_REPORT.md` must include at least:

- `READY FOR ROOT REVIEW` first line;
- start commit/tree;
- final local commit SHA;
- final local tree SHA;
- direct parent SHA;
- VERSION;
- literal final clean status;
- remote Distributed SHA;
- exact changed-file list/count;
- concise architecture summary;
- canonical release state order;
- workflow names and trigger boundaries;
- GitHub-native candidate strategy;
- candidate persistence strategy;
- Free/Pro PyPI distribution identities;
- shared canonical import and CLI;
- no-sdist rationale under the later binding authority;
- Docker Hub → GHCR same-manifest promotion;
- Trusted Publishing/OIDC boundary;
- Windows final-tree regression result;
- Ubuntu final-tree regression result;
- targeted-suite results;
- `git diff --check`;
- secret/large-binary/tracked-artifact review;
- confirmation of zero push/tag/PyPI/DockerHub/public-GHCR/staging/GitHub-Release writes;
- explicit statement that only external Root Review may grant Root PASS.

If any mandatory gate is not satisfied, report:

`NOT READY FOR ROOT REVIEW`

with the exact concrete blocker.

---

# 12. Absolute prohibitions

Do not:

- push `work/ap-srv-070-w5-r04`;
- push `feat/einheitliche-triggerarchitektur-distributed`;
- touch canonical or `main`;
- create/push a Git tag;
- publish PyPI;
- push Docker Hub;
- push public GHCR;
- push private staging;
- create GitHub Release;
- use force push;
- amend/rebase after final commit;
- create multiple commits;
- delete existing evidence;
- merge/cherry-pick any superseded Gemini W5-R03-E1 source work;
- add model-image functionality;
- redesign already completed release infrastructure.

---

# 13. Completion criterion

This continuation is successful only when the already implemented W5-R04 work is closed with:

1. the one pending maintained-doc correction;
2. final-tree targeted test PASS;
3. final-tree Windows full regression PASS;
4. final-tree Ubuntu 24.04 full regression PASS;
5. all evidence documents completed;
6. exactly one local implementation commit directly parented to `934e3be7...`;
7. literal clean final workspace;
8. remote Distributed unchanged;
9. zero push/tag/public/staging writes;
10. `09_FINAL_REPORT.md` begins `READY FOR ROOT REVIEW`.

No additional implementation work is desired unless a mandatory verification exposes a concrete reproducible blocker.
