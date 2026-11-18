# W5-R04 — 01 Preflight

Run: AP-SRV-070 / W5-R04 (Claude Opus 5, new session)
Date: 2026-09-08

## 1. Prompt authority

| Item | Value |
| --- | --- |
| Prompt source | `P:\GithubRepos\marcosudau-vps\_workflow-tools\AP-SRV-070\Prompts\2026-09-08_AP-SRV-070_W5_R04_OPUS5.md` |
| Source SHA256 | `40ea279b8d676714e121ea7bec4b4a494fcd6fe67d4b97e3348c3eaeef738ff4` |
| Byte-identical copy | `00_PROMPT.md` |
| Copy SHA256 | `40ea279b8d676714e121ea7bec4b4a494fcd6fe67d4b97e3348c3eaeef738ff4` |
| `cmp` result | byte-identical |

The complete prompt (1478 lines) was read before any inventory or edit.

## 2. Remote start-branch proof (W5R4-G01)

`git fetch origin --prune` was executed in the shared clone
`P:\GithubRepos\marcosudau-vps\voice-stt-server\main`.

```text
$ git rev-parse origin/feat/einheitliche-triggerarchitektur-distributed
934e3be7c78aa9358f9b42b9fa4dc282bed54d6c
```

Commit metadata of the binding start commit:

```text
commit  934e3be7c78aa9358f9b42b9fa4dc282bed54d6c
tree    2936f70ca44b7a902e1e5c7c5ca69eacc3154fdb
parent  7f1ad1f02da9b1c4e3bf226f2a056066921ef77a
author  Claude Opus 5
date    Mon Sep 7 21:06:57 2026 +0200
subject AP-SRV-070 W5: correct canonical log-store recovery semantics
```

All three identities (commit / tree / direct parent) match the prompt's
section 0 exactly. **G01 PASS.**

## 3. New workspace (W5R4-G02)

```text
$ git worktree add -b work/ap-srv-070-w5-r04 \
    P:/GithubRepos/marcosudau-vps/voice-stt-server/workspaces/ap-srv-070-w5-r04 \
    934e3be7c78aa9358f9b42b9fa4dc282bed54d6c
Preparing worktree (new branch 'work/ap-srv-070-w5-r04')
HEAD is now at 934e3be AP-SRV-070 W5: correct canonical log-store recovery semantics
```

Post-creation proof inside the new workspace:

```text
$ git rev-parse HEAD
934e3be7c78aa9358f9b42b9fa4dc282bed54d6c
$ git rev-parse "HEAD^{tree}"
2936f70ca44b7a902e1e5c7c5ca69eacc3154fdb
$ git branch --show-current
work/ap-srv-070-w5-r04
```

**G02 PASS.**

## 4. VERSION (W5R4-G03)

```text
$ cat VERSION
2.0.0
```

**G03 PASS.**

## 5. Literal pre-edit working-tree status (W5R4-G04)

```text
$ git status --porcelain
```

The command produced **no output at all**. The literal (empty) capture is
archived at `Evidence/00_PreEdit/git_status_porcelain.txt`
(SHA256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`,
which is the SHA-256 of the empty byte string and therefore itself proof that
the file is empty). Tracked file count at start: 518.

**G04 PASS.**

## 6. Superseded W5-R03-E1 run (W5R4-G06)

The new workspace was created directly from `934e3be7...`, which is the
W5-R03 result commit and the direct ancestor named by this prompt. No branch,
worktree, patch, stash or file from the Gemini W5-R03-E1 evidence-completion
run was consulted, cherry-picked, merged or copied. The E1 repository-variable
preflight questions are treated as superseded per prompt section 1 and are not
pursued.

**G06 PASS (pre-edit).** Re-confirmed at the end of the run by the final diff.

## 7. Environment available to this run

| Capability | Result |
| --- | --- |
| Docker Server | 29.7.2 (Docker Desktop, WSL2 backend) |
| Windows Python | 3.12.10 |
| WSL2 | `Ubuntu` (running), `docker-desktop` (running) |
| Existing local Kroko artifact store | present (free: 3 slots, pro: 1 slot) |
| Network | available (read-only registry/manifest queries used for base-image digests) |

The pre-existing local Kroko artifact store is deliberately **not** used as a
release input. The section 35 fresh-runner proof uses a newly created, empty
artifact-store directory (see `Evidence/04_KrokoFreshBuild`).

## 8. Inventory of the current release/build/docs surfaces

### Release engine (`release_tooling/`, 2469 lines including `release.py`)

| File | Role |
| --- | --- |
| `state.py` | `STATE_ORDER`, `ReleaseState`, resume/identity guards, order barriers |
| `engine.py` | the one operation graph (`STEP_DEFINITIONS`), `run_engine` for DRY_RUN/REAL |
| `pipeline.py` | backwards-compatible facade plus `dry_run()` |
| `adapters.py` | PyPI (twine), GHCR/Docker Hub (docker tag+push), Git tag, GitHub Release, aggregate verification |
| `remote_checks.py` | read-only PyPI JSON and `docker manifest inspect` identity checks |
| `rc_manifest.py` | canonical RC manifest schema v1, build/validate/load/write |
| `preflight.py` | read-only preflight checks |
| `config.py` | image names, distribution name, registry-root env vars, credential presence |
| `gitinfo.py` | read-only git identity plus `create_tag`/`push_tag` |
| `errors.py`, `redaction.py` | error hierarchy, secret redaction/assertions |

Current `STATE_ORDER` (to be changed by this run):

```text
PREPARED -> PYPI_PUBLISHED -> GHCR_PUBLISHED -> DOCKERHUB_PUBLISHED
-> EXTERNAL_VERIFIED -> TAGGED -> GITHUB_RELEASED -> FINAL_VERIFIED -> COMPLETE
```

Findings relevant to this run:

1. The Git tag is created **after** every public artifact. Superseded by
   prompt section 15.
2. GHCR is published **before** Docker Hub. Superseded by section 20.
3. GHCR publication is an independent `docker tag` plus `docker push` of a
   local image, not a manifest promotion of the Docker Hub artifact.
   Superseded by section 20.
4. There is **no movable-alias step at all** (`2.0`, `2`, `latest`), which
   section 21 requires.
5. Registry identity is checked by comparing the remote manifest digest to the
   locally recorded `docker inspect` **image Id**. Those are different values
   and can never legitimately be equal, so every real registry verification
   would have raised `ConflictError`. The RC manifest carries no registry
   digest field at all.
6. Registry roots come from operator env vars `VOICESTT_RELEASE_GHCR_REPO` and
   `VOICESTT_RELEASE_DOCKERHUB_REPO`; there is no GitHub-derived default.
7. There is no candidate-identity binding (run id / candidate manifest hash)
   in `ReleaseState`, so a resume cannot prove it is resuming the exact
   qualified candidate.

### Build tooling

| File | Role |
| --- | --- |
| `tools/build_production.py` (585 lines) | wheel build, Kroko resolve (REUSE or BUILD ONCE in a container), production image, build manifest |
| `build/kroko-builder.Dockerfile` (45 lines) | standalone Linux/AMD64 Kroko builder |
| `Dockerfile` (109 lines) | two-stage production image (builder plus runtime) |
| `Dockerfile.pro-upgrade` (9 lines) | narrow VPS repair path |
| `VoiceSTT/kroko/buildinputs.py` (543) | declared Kroko build inputs plus Windows toolchain pins |
| `VoiceSTT/kroko/fingerprint.py` (246) | fingerprint document/id |
| `VoiceSTT/kroko/artifacts.py` (1091) | variant-namespaced artifact store, verify, locks |

Findings relevant to this run:

1. `fingerprint.toolchain_identity("linux")` returns `{"kind": "host-native"}`.
   The Linux builder container (`python:3.12-slim-bookworm`, a floating tag;
   live `apt-get update`; unpinned pip packaging tools) is therefore **not**
   part of the Linux fingerprint. Two builds on materially different
   toolchains would share one fingerprint. This is the exact hole W4A-C3
   Finding J closed for Windows but which is still open for Linux, and
   section 12 requires this audit.
2. `build_production.build_production_image()` stamps a wall-clock
   `BUILD_DATE`, so re-running the same source produces a different image
   identity (section 32).
3. `Dockerfile` builder and runtime stages use the floating `ubuntu:24.04` tag.
4. No sdist is produced by the build orchestrator, although PyPI needs one.
5. No GitHub-native reuse mechanism exists; reuse is the local artifact store
   only.

### Workflows

Only `.github/workflows/ci.yml` exists. It is read-only
(`permissions: contents: read`), never publishes, and uses `actions/checkout@v4`
and `actions/setup-python@v5` — **tag references, not commit SHAs**, while
section 23 requires full-SHA pinning.

### Documentation

`docs/engines/` contains 11 guides; only `faster-whisper.md` and
`kroko-onnx.md` are to be retained (and moved to `docs/`). Maintained
references to `docs/engines/...` exist in:

`README.md` (13 links), `docs/transcription-engines.md` (12),
`docs/installation.md` (3), `docs/testing.md` (2), `docs/troubleshooting.md` (1),
`docs/module-map.md` (1), `build/BUILD.md` (1), `build/vps/README.md` (1).

Archive references under `docs/.archiv/` are historical and stay untouched.

## 9. Project-process obligation

`AGENTS.md` and `docs/.archiv/README.md` require, for a cross-cutting
release/deployment/documentation change:

1. a dated plan **before** implementation, and
2. a dated Soll/Ist review **after** implementation,

in `docs/.archiv/einheitliche_triggerarchitektur/AP-SRV-070/`.

This run therefore writes `2026-09-08_W5_R04_PLAN.md` as its **first tracked
edit**, after this preflight and after `02_IMPLEMENTATION_PLAN.md`.

## 10. Preflight verdict

G01, G02, G03, G04 and the pre-edit part of G06 are satisfied. No tracked edit
had been made at the time this document was written.
