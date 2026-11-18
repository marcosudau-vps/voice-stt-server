# W5-R04 — 02 Implementation Plan

Written **before the first tracked edit** (prompt section 6, gate W5R4-G05).

Start commit `934e3be7c78aa9358f9b42b9fa4dc282bed54d6c`,
tree `2936f70ca44b7a902e1e5c7c5ca69eacc3154fdb`, VERSION `2.0.0`,
workspace literally clean (`Evidence/00_PreEdit`).

---

## 0. Objective

One coherent change that makes a VoiceSTT release producible and publishable by
GitHub-hosted automation from an exact source commit, keeps the existing
VoiceSTT release state machine as the single canonical authority, and
rebaselines the public documentation surface (full README rewrite plus engine
documentation cleanup).

Scope is limited to release / build / workflow / documentation surfaces.
No product architecture is reopened.

---

## 1. Work packages

### WP-A — Project process entry (first tracked edit)

- `docs/.archiv/einheitliche_triggerarchitektur/AP-SRV-070/2026-09-08_W5_R04_PLAN.md`
- Register row update in `docs/.archiv/README.md` is **not** needed: AP-SRV-070
  is already listed as `In Umsetzung`; only its status text is refreshed to name
  W5-R04.

### WP-B — Kroko Linux builder reproducibility (prompt section 12)

Problem: `toolchain_identity("linux")` is `{"kind": "host-native"}`, so the
Linux builder container is not a fingerprint input. On a GitHub runner that is
not acceptable: the container *is* the toolchain.

- `VoiceSTT/kroko/buildinputs.py`
  - Add `LINUX_BASE_IMAGE`, `LINUX_BASE_IMAGE_DIGEST`
    (`python:3.12-slim-bookworm@sha256:782412e8...`, index digest resolved from
    the registry during this run), `LINUX_APT_PACKAGES`,
    `LINUX_PACKAGING_TOOLS`, `LINUX_BUILD_PYTHON_TAG`.
  - Add `linux_toolchain_declaration()` returning that pure data.
  - Bump `LINUX_BUILDER_REVISION` 1 -> 2 (the declaration becomes part of the
    Linux fingerprint, so previously stored Linux artifacts must stop matching;
    that is the W4A rule, not a regression).
  - Windows constants and `WINDOWS_BUILDER_REVISION` stay untouched, so the
    already qualified Windows artifact is not invalidated.
- `VoiceSTT/kroko/fingerprint.py`
  - `linux_toolchain_authority()` mirroring `windows_toolchain_authority()`.
  - `toolchain_identity("linux")` returns kind/definedBy/authority/inputs
    instead of `{"kind": "host-native"}`.
- `build/kroko-builder.Dockerfile`
  - `FROM` the pinned digest; install exactly the declared apt package set and
    the declared pinned pip packaging tools.
- Honest boundary: Debian apt **point versions** are still resolved against the
  live archive. Documented explicitly; not closed in this run (section 12
  forbids turning this into a hermetic-build project). The qualified artifact
  itself remains publication authority.

### WP-C — Production image identity (prompt sections 12 and 32)

- `Dockerfile`: pin both `ubuntu:24.04` stages by the already source-controlled
  digest constant.
- `tools/build_production.py`:
  - `resolve_build_date()` derives `BUILD_DATE` from the **commit timestamp**
    (`git show -s --format=%cI`), not wall clock, so a rebuild/resume of the
    same source yields the same OCI `created` value. `--build-date` override
    kept for callers that must pin it explicitly.
  - Record `buildDateSource` in the build manifest.

### WP-D — GitHub-native candidate build orchestrator

New `tools/release_candidate.py`:

- builds wheel **and sdist**;
- runs the existing `tools/build_production.py` path for `free` and `pro`;
- pushes each production image to a **private GHCR staging package** and reads
  back the pushed manifest digest;
- assembles the canonical RC manifest plus a machine-readable SHA256 inventory;
- writes everything under one output directory for upload as workflow
  artifacts.

Rationale: keeps workflow YAML thin (section 31 forbids a second release
implementation living in shell), and makes the candidate path unit-testable
with an injected runner.

### WP-E — Release state machine re-ordering (prompt sections 15, 20, 21)

`release_tooling/state.py`, `engine.py`:

New canonical order:

```text
PREPARED
-> TAGGED
-> PYPI_PUBLISHED
-> DOCKERHUB_PUBLISHED
-> GHCR_PUBLISHED
-> EXTERNAL_VERIFIED
-> ALIASES_PUBLISHED
-> GITHUB_RELEASED
-> FINAL_VERIFIED
-> COMPLETE
```

- `assert_tag_allowed` now means "no public artifact published yet"
  (state must still be `PREPARED`).
- New `assert_public_publication_allowed` (requires `TAGGED`) is asserted by
  the PyPI and registry adapters, so "tag before first public write" holds even
  if an adapter is driven out of turn.
- New `assert_aliases_allowed` (requires `EXTERNAL_VERIFIED`) and
  `assert_github_release_allowed` (now requires `ALIASES_PUBLISHED`).
- `ReleaseState` gains an optional `candidate` block (candidate id, workflow
  run id, RC manifest SHA256) so a resume proves it is resuming the exact
  qualified candidate; `ensure_same_identity` covers it.
- `run_engine(..., stop_after=STATE)` lets one workflow job advance exactly its
  own steps while the graph, order and barriers stay the single authority.

### WP-F — Registry promotion + aliases

- `release_tooling/aliases.py`: generic SemVer alias mapping
  (`2.0.0 -> 2.0, 2, latest`; `0.x.y -> 0.x, latest` with no broad `0`;
  prerelease -> no aliases).
- `remote_checks.check_registry_image` compares the **manifest digest**
  (`docker buildx imagetools inspect --format {{json .Manifest}}`), which fixes
  the pre-existing image-Id/digest confusion.
- `DockerHubAdapter`: promotes the qualified staging manifest to
  `marcosudau/voice-stt-server[-pro]:<version>` by digest.
- `GHCRAdapter`: promotes the **Docker Hub** manifest by digest to
  `ghcr.io/<owner>/voice-stt-server[-pro]:<version>`. No second production
  build anywhere.
- `AliasAdapter`: sets `2.0`, `2`, `latest` on both registries for both
  variants from the exact verified digest, then verifies each alias digest.
- `config`: Docker Hub namespace from `DOCKERHUB_USERNAME`/
  `VOICESTT_RELEASE_DOCKERHUB_NAMESPACE`; GHCR root derived from
  `GITHUB_REPOSITORY_OWNER` when present, so the operator does not have to set
  a redundant registry-root variable.

### WP-G — PyPI Trusted Publishing boundary (prompt sections 17, 31)

`twine upload` with a long-lived token is replaced, for the GitHub path, by an
explicit executor boundary:

- `DelegatedPublishAdapter` wraps a real read-only `verify()` and declares that
  the write is performed by a named external executor
  (`pypa/gh-action-pypi-publish` under OIDC). Its `publish()` performs no write;
  the engine's existing mandatory post-publish `verify()` is what advances the
  state, so the transition is based on verified external state, not on an
  action's exit code.
- The local/manual `PyPIAdapter` (twine) is retained for non-GitHub operation.
- No PyPI token is required by, or stored for, the GitHub path.

### WP-H — Workflows

- `.github/workflows/ci.yml`: unchanged behaviour, actions pinned to full
  commit SHAs, explicit `permissions`, concurrency group.
- `.github/workflows/release-candidate.yml`: `workflow_dispatch` only.
  Builds the candidate on a clean `ubuntu-24.04` runner, uses an Actions cache
  keyed by the **authoritative Kroko fingerprint** (separate keys per variant),
  revalidates every reused artifact, uploads wheel/sdist/Kroko wheels/manifests
  as artifacts, pushes private GHCR **staging** packages. Permissions:
  `contents: read`, `packages: write`. Zero public writes.
- `.github/workflows/release-publish.yml`: `workflow_dispatch` only, gated by
  the `release` GitHub Environment (required reviewer). Jobs, each advancing
  the canonical state machine with `--until`:
  `tag` (contents: write) -> `pypi` (id-token: write) ->
  `dockerhub` -> `ghcr` (packages: write) -> `verify` ->
  `aliases` (packages: write) -> `github-release` (contents: write).
  Concurrency group `release-publish-<version>` prevents racing publications.

### WP-I — Tests

New: `tests/unit/test_release_aliases.py`,
`tests/unit/test_release_workflows.py`,
`tests/unit/test_release_candidate_tool.py`,
`tests/unit/test_docs_surface.py`,
`tests/unit/test_kroko_linux_toolchain.py` (or extension of
`test_kroko_fingerprint.py`).

Updated: `test_release_state.py`, `test_release_engine.py`,
`test_release_pipeline.py`, `test_release_adapters.py`, `test_release_cli.py`,
`test_release_preflight.py`, `test_release_rc_manifest.py`,
`test_release_remote_checks.py`, `test_build_production.py`,
`test_production_docker_contract.py`, `test_kroko_fingerprint.py`.

Guard coverage required by section 25/34, including: no absolute Windows path
or operator-local dependency in workflow/build authority; workflow triggers,
permissions, pinned action SHAs, no publish on push/PR; state order; tag before
first public write; Docker Hub before GHCR; GitHub Release last; alias mapping
and ordering; conflict/unknown fail-closed; dry-run zero writes; candidate
identity binding; documentation/link guards.

### WP-J — Documentation

- `README.md`: complete rewrite from scratch.
- `git mv docs/engines/faster-whisper.md docs/faster-whisper.md`
- `git mv docs/engines/kroko-onnx.md docs/kroko-onnx.md`
- delete the remaining nine `docs/engines/*.md` and the directory.
- `docs/transcription-engines.md`: reduced to the two supported production
  engines plus an honest note that other adapters exist in source but are not
  a documented/qualified production surface.
- Link corrections in `docs/README.md`, `docs/installation.md`,
  `docs/testing.md`, `docs/troubleshooting.md`, `docs/module-map.md`,
  `docs/licenses.md`, `build/BUILD.md`, `build/vps/README.md`
  (link-only correction, allowed by section 30).
- New `docs/release-process.md`: GitHub-native release process, state order,
  candidate persistence, operator setup checklist (repository variable,
  repository secret, PyPI Trusted Publisher, `release` environment).
- `docs/.archiv/.../2026-09-08_W5_R04_UMSETZUNGSVERGLEICH.md` after
  implementation.

---

## 2. Order of execution

1. WP-A (first tracked edit).
2. WP-B, WP-C (fingerprint-affecting) — then immediately start the empty-store
   Kroko Free and Pro builds in the background, because they are the long pole.
3. WP-E, WP-F, WP-G (release engine) while builds run.
4. WP-D, WP-H (candidate tool, workflows).
5. WP-I (tests) continuously; full suites at the end.
6. WP-J (documentation).
7. Evidence, regression runs, single final commit.

## 3. Explicit non-goals

- No push, tag, GitHub Release, PyPI upload, Docker Hub push, or public GHCR
  write.
- No staging push during this local run either.
- No change to trigger/activation, protocol v2, settings, wake word, STT
  session, model management, event store, client architecture, FastAPI protocol
  shape, or `build/vps/*` beyond a link correction.
- No removal of `VoiceSTT/transcription_engines/*` implementation modules.
- No rewrite of historical `docs/.archiv` records.

## 4. Known risks

| Risk | Handling |
| --- | --- |
| Linux fingerprint change invalidates stored Kroko artifacts | Intended and correct under W4A rules; the empty-store proof rebuilds both variants from source. |
| Two full native Kroko builds are expensive | Run in background, both variants, real empty store. If one cannot complete, report the exact limitation instead of faking it. |
| Ubuntu regression run needs native ext4 | Use the established WSL2 ext4 approach; report honestly if blocked. |
| Schema change to the RC manifest | Bump `SCHEMA_VERSION` to 2 and update every producer/consumer/test in the same commit; no released manifest exists yet. |


---

# ADDENDUM A — Updated binding product/packaging authority (2026-09-08)

A follow-up operator message supersedes the original prompt wherever the two
conflict. It arrived after WP-A/WP-B/WP-C and part of WP-E were already
implemented. This addendum records the reclassification and the corrected plan.
The run continues in the same session, same workspace, same single final
commit.

## A.1 Classification of work already done at the time the authority arrived

`git status --porcelain` at that moment:

```text
 M Dockerfile
 M VoiceSTT/kroko/buildinputs.py
 M build/kroko-builder.Dockerfile
 M release_tooling/state.py
 M tools/build_production.py
?? docs/.archiv/einheitliche_triggerarchitektur/AP-SRV-070/2026-09-08_W5_R04_PLAN.md
```

| Change | Verdict under the new authority |
| --- | --- |
| `2026-09-08_W5_R04_PLAN.md` (archive plan) | **Keep**, extend with the new authority. |
| Kroko Linux builder pinned + `LINUX_BUILDER_REVISION` 1 -> 2 | **Keep unchanged.** Section 2 of the new authority explicitly keeps internal Kroko wheels as qualified intermediate artifacts, still fingerprint- and hash-bound. |
| `Dockerfile` base pinned by digest | **Keep unchanged.** Docker stays Free/Pro-split (new authority section 5). |
| Source-derived `BUILD_DATE` in `tools/build_production.py` | **Keep unchanged.** |
| `release_tooling/state.py` new state order, barriers, candidate binding | **Keep**, with one correction: `PYPI_PUBLISHED` becomes an explicitly aggregated state over **two** distributions (new authority section 6). |
| Background empty-store Kroko Free+Pro build | **Keep running.** Both native artifacts are still required — now as the embedded runtimes of the two PyPI distributions rather than only as Docker inputs. |

No change made so far assumed a single PyPI distribution, a separate public
Kroko distribution, an end-user Kroko build, or a universal wheel, so nothing
had to be reverted.

## A.2 Corrected product matrix

```text
Free:  PyPI voice-stt-server       Docker voice-stt-server
Pro:   PyPI voice-stt-server-pro   Docker voice-stt-server-pro
```

Both distributions ship the full server code **plus** the matching Kroko native
runtime, expose the same import package `voice_stt_server`, and the same
canonical CLI `voice-stt-server`. They are mutually exclusive installations.
The Pro key is a runtime credential only and never selects a runtime.

## A.3 New/changed work packages

### WP-K — Canonical public API surface

- New top-level package `voice_stt_server/` re-exporting the public API
  (`AudioToTextRecorder`, the client recorder, `AudioInput`, the realtime
  boundary types) with the same lazy `__getattr__` behaviour `VoiceSTT`
  already uses, so `from voice_stt_server import AudioToTextRecorder` works in
  both distributions.
- `VoiceSTT` remains importable: this is additive, not a compatibility break.
- New console script `voice-stt-server`; `stt-server`, `stt-server-legacy` and
  `stt` are retained as compatibility aliases.
- `stt-install-kroko` is retained as a **developer/release** helper only and is
  removed from every normal end-user installation instruction.

### WP-L — Two variant-specific distributions

- `setup.py` becomes variant-aware through `VOICESTT_DISTRIBUTION_VARIANT`
  (`free` -> `voice-stt-server`, `pro` -> `voice-stt-server-pro`); the default
  stays the historical `voicestt` name so existing development installs and the
  entire current test suite keep working.
- Mutual exclusivity is declared with `Conflicts-Dist` metadata and documented;
  the two distributions are never required together.

### WP-M — Embedded native runtime (`tools/build_distribution.py`)

The qualified Kroko wheel's payload (`kroko_onnx/`, `sherpa_onnx/` and the
top-level `_sherpa_onnx` extension module) is merged verbatim into the
VoiceSTT distribution wheel, which is then retagged as a platform wheel.
Merging the already-qualified bytes (rather than rebuilding through setuptools)
is what preserves exact artifact identity from qualification to publication.

The merged wheel records provenance in `voice_stt_server/_embedded_kroko.json`
(variant, Kroko version, fingerprint, artifact SHA256), and
`VoiceSTT.kroko.artifacts.verify_installed_runtime` resolves the installed
variant from that file first, falling back to the legacy separately installed
`kroko-onnx` distribution for developer environments.

### WP-N — Honest platform/Python matrix (new authority section 8)

The Kroko build authority produces
`kroko_onnx-1.12.9-1{free,pro}-cp312-cp312-{linux_x86_64,win_amd64}.whl`.
The supported matrix for the two public distributions is therefore exactly:

```text
CPython 3.12, linux_x86_64
CPython 3.12, win_amd64
```

`python_requires` for the two distributions becomes `>=3.12,<3.13`. The
historical `voicestt` development distribution keeps `>=3.11`. Claiming 3.11
for a distribution that embeds a cp312-only native runtime would be false
advertising, which section 8 explicitly forbids.

### WP-O — sdist decision (new authority section 9)

**No sdist is published for `voice-stt-server` / `voice-stt-server-pro`.**

Technical reason: the distribution's defining property is that it contains a
qualified native Kroko runtime. An sdist cannot carry that (it is source), so
installing from it would either fall back to a local ~30-minute native Kroko
build or silently produce an incomplete installation without a Kroko runtime.
Both outcomes violate the new authority's primary guarantee that
`pip install voice-stt-server` needs no local native build. Wheels for every
documented platform are published instead, so `pip` never needs an sdist on a
supported platform; on an unsupported platform the install fails loudly rather
than silently producing something incomplete.

The release manifest, the release engine and the tests drop the single
`sdist` binding and bind per-distribution wheel sets instead.

### WP-P — Dual-distribution release pipeline

- RC manifest schema v2 binds a `distributions` block with one entry per
  distribution: name, wheels (filename/sha256/python tag/platform tag),
  embedded Kroko variant, Kroko fingerprint and embedded artifact SHA256.
- `PYPI_PUBLISHED` is reached only when **both** distributions are verified
  present with exactly the expected filenames and hashes.
- Resume: one distribution already published, the other missing -> only the
  missing one is published. Conflicting identity on either -> hard STOP, never
  a new version.
- Trusted Publishing is configured for two PyPI projects sharing the same
  protected release environment and workflow; the operator setup documents
  both publishers exactly.

## A.4 Superseded items from the original prompt

| Original prompt item | Superseded by |
| --- | --- |
| Section 10.2 "VoiceSTT sdist" as a mandatory candidate artifact | New authority section 9 — no sdist for the two native distributions. |
| Section 10 single wheel identity, section 17 single PyPI project | New authority sections 1, 6, 7, 10 — two distributions. |
| README install instructions built around `pip install "VoiceSTT[...]"` plus `stt-install-kroko --build` | New authority sections 4 and 11 — `pip install voice-stt-server[-pro]`, no end-user Kroko build. |
