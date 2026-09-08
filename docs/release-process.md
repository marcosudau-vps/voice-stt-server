# Release process

How a VoiceSTT release is produced and published, and what an operator has to
configure once.

The governing principle:

> A release is produced by GitHub-hosted automation from an exact source
> commit. The same bytes and OCI manifests that were qualified are later
> published without rebuilding. The release has a durable Git identity before
> the first public write, resumes safely under the same version after a
> failure, and fails closed on conflicting or unverifiable remote state.

No operator machine is part of the release authority. There is no step that
needs a local artifact store, a locally built wheel, a local image, local
registry credentials or a local `.env`.

---

## 1. What a release consists of

| Surface | Free | Pro |
| --- | --- | --- |
| PyPI distribution | `voice-stt-server` | `voice-stt-server-pro` |
| Docker Hub | `marcosudau/voice-stt-server` | `marcosudau/voice-stt-server-pro` |
| GHCR | `ghcr.io/marcosudau-vps/voice-stt-server` | `ghcr.io/marcosudau-vps/voice-stt-server-pro` |

Every surface is published for **both** variants. "One variant published" is
never a completed step.

### Why there is no sdist

The defining property of these two distributions is that each one *contains* a
qualified native Kroko runtime, so that `pip install voice-stt-server` needs no
local build. An sdist is source: it cannot carry that runtime. Publishing one
would mean that on any machine where pip preferred it, the install would either
trigger a ~30-minute native Kroko build or silently produce an installation with
no Kroko runtime at all. Both outcomes break the guarantee the distributions
exist to provide.

A wheel is therefore published for every documented platform, and no sdist is
published for `voice-stt-server` / `voice-stt-server-pro`. On a supported target
pip never needs one; on an unsupported target the install fails loudly instead
of quietly producing something incomplete.

### Supported platform matrix

The embedded native runtime is built and qualified for:

```text
CPython 3.12, linux_x86_64
CPython 3.12, win_amd64
```

That is exactly what the packaging claims (`python_requires = >=3.12,<3.13`).
Advertising a Python version the shipped runtime does not exist for would be a
promise the distribution cannot keep.

---

## 2. The two workflows

### `release-candidate.yml` — build and qualify

`workflow_dispatch` only. On a clean `ubuntu-24.04` runner it:

1. checks out the exact commit and proves the tree is clean;
2. resolves the authoritative Kroko fingerprint per variant **inside the
   builder container** and uses it as the Actions cache key;
3. builds or validly reuses the Kroko Free and Pro native artifacts;
4. builds both production images;
5. merges each qualified Kroko runtime into its distribution wheel;
6. pushes both images to **private GHCR staging** packages and records their
   exact manifest digests;
7. writes the canonical RC manifest and a SHA-256 inventory;
8. uploads everything as workflow artifacts.

Permissions: `contents: read`, `packages: write`. The `packages: write` grant
exists solely for the private staging packages. This workflow performs **no**
public write: no PyPI upload, no Docker Hub push, no public GHCR tag, no Git
tag, no GitHub Release.

**Kroko artifact reuse.** The Actions cache is an optimisation, never an
authority. Free and Pro have separate cache keys and separate store namespaces,
every reused artifact is revalidated against the fingerprint/artifact authority
before use, and a cache miss simply builds from source. The first build on an
empty cache works.

**Staging retention.** Candidate images live in private GHCR packages tagged by
candidate id; workflow artifacts are retained for 90 days. A candidate older
than that must be rebuilt (which produces a new candidate id and a new manifest
hash — a resume against it fails closed rather than silently continuing).

### `release-publish.yml` — publish

`workflow_dispatch` only, and every job runs in the protected `release`
GitHub Environment. It builds nothing; it consumes the qualified candidate.

Each job advances only its own portion of the canonical release state machine
via `release.py publish --until <STATE>`, so each job holds only the
credentials and permissions its own steps need:

| Job | Advances to | Permissions |
| --- | --- | --- |
| `tag` | `TAGGED` | `contents: write` |
| `pypi` | `PYPI_PUBLISHED` | `id-token: write` |
| `registries` | `EXTERNAL_VERIFIED` | `contents: read`, `packages: write` |
| `finalize` | `COMPLETE` | `contents: write`, `packages: write` |

---

## 3. The canonical order

```text
PREPARED
  -> TAGGED
  -> PYPI_PUBLISHED          (voice-stt-server AND voice-stt-server-pro)
  -> DOCKERHUB_PUBLISHED     (Free AND Pro, exact version tag)
  -> GHCR_PUBLISHED          (promotion of the exact Docker Hub manifest)
  -> EXTERNAL_VERIFIED
  -> ALIASES_PUBLISHED       (2.0, 2, latest — both registries, both variants)
  -> GITHUB_RELEASED
  -> FINAL_VERIFIED
  -> COMPLETE
```

This order lives in exactly one place, `release_tooling/engine.py`, and is used
identically by a dry run, a real publication and a resume. The workflow supplies
a boundary; it never re-implements the order.

Four properties are worth calling out:

**The tag comes first.** Once `2.0.0` exists on PyPI or in a registry the
version is publicly reserved. The immutable Git tag therefore exists *before*
the first irreversible public write, so a partially published version always has
a source anchor. The tag is created only after every deterministic build,
test and qualification gate has passed, and it points at the exact qualified
commit.

**Docker Hub before GHCR.** GHCR is a promotion of the *same* manifest by
digest (`docker buildx imagetools create`), not a second independent build.
There is no second production build anywhere in the graph.

**Aliases move last, and only after verification.** `2.0`, `2` and `latest` are
updated only once the exact Free and Pro artifacts are verified in both
registries, and each alias digest is verified after being set. `latest` can
never point at a release candidate or an incomplete release. For `0.x.y`
versions no broad `0` alias is created, because `0.x` promises no compatibility
across minor versions. A pre-release gets no aliases at all.

**The GitHub Release is the last public marker.** It is created only after
every artifact and every alias is published and verified.

### Resume and failure

Publication is resumable under the **same version**. If PyPI succeeded and
Docker Hub failed, the next attempt verifies what already exists, skips it, and
completes the rest. If `voice-stt-server` published and `voice-stt-server-pro`
did not, only Pro is uploaded.

A partially published `2.0.0` never becomes `2.0.1`.

State transitions are based on *verified external state*, not on a command's
exit code. Every publishing step re-verifies after writing, and only then
advances.

Two conditions stop a real publication immediately:

- **`CONFLICT`** — a remote artifact for this version exists with a different
  identity. Nothing is deleted, overwritten, force-pushed or repointed.
- **`UNKNOWN`** — the remote state could not be verified at all. "Cannot check"
  is never treated as "safe to publish".

---

## 4. Operator setup

This is the complete list. Anything that can be derived safely is derived.

### 4.1 Repository variable

```text
DOCKERHUB_USERNAME = marcosudau
```

A variable, not a secret: it is not sensitive, and making it a secret would only
hide it from the logs where it is useful.

The GHCR root is **not** configured — it is derived as
`ghcr.io/${{ github.repository_owner }}`.

### 4.2 Repository secret

```text
DOCKERHUB_TOKEN = <Docker Hub personal access token>
```

Needs publish (read/write) capability. It does **not** need Delete: the release
never deletes or repoints an exact version tag.

### 4.3 GHCR

Nothing to configure. The workflows authenticate with the automatically
provided `GITHUB_TOKEN` and the per-job `packages: write` permission. No
long-lived GHCR PAT exists.

### 4.4 PyPI Trusted Publishing

Two PyPI projects, therefore **two Trusted Publishers**. Configure each in the
project's *Publishing* settings on PyPI:

| Field | `voice-stt-server` | `voice-stt-server-pro` |
| --- | --- | --- |
| Owner | `marcosudau-vps` | `marcosudau-vps` |
| Repository | `voice-stt-server` | `voice-stt-server` |
| Workflow name | `release-publish.yml` | `release-publish.yml` |
| Environment name | `release` | `release` |

Both distributions are published by the same workflow and the same protected
environment, which is supported by Trusted Publishing.

No PyPI API token is stored anywhere in the repository.

### 4.5 GitHub Environment

Create an environment named `release`:

- **Required reviewers:** at least one. This is the approval boundary between
  qualification and the first irreversible public publication. Until it is
  approved, no publish job starts.
- **Secrets belonging to it:** `DOCKERHUB_TOKEN` (it may equally live as a
  repository secret; the environment is what gates access to it in practice,
  since only environment-bound jobs publish).
- **Gated jobs:** all four jobs of `release-publish.yml`.

Because every publishing job is bound to this environment, a normal push, a
pull request, or a pull request from a fork can never reach a release secret or
a package-write permission.

### 4.6 Optional: Pro runtime qualification

If GitHub-hosted *runtime* qualification of a Pro model is ever added:

```text
VOICESTT_KROKO_ONNX_KEY = <runtime-only key>
```

This is **not** a build secret. The Pro native runtime is built without any
license key; the key is only a runtime credential. No workflow uses it as a
build input, and a guard test fails if one ever does.

---

## 5. Running a release

```bash
# 1. Build and qualify a candidate from the exact commit.
#    Actions -> "Release candidate" -> Run workflow

# 2. Review the candidate artifacts (rc-manifest.json, sha256-inventory.json).

# 3. Publish, naming the candidate run.
#    Actions -> "Release publish" -> Run workflow
#      candidate_run_id: <run id from step 1>
#      version: 2.0.0
#    then approve the `release` environment when prompted.
```

Locally, the same engine can be inspected without writing anything:

```bash
python release.py preflight
python release.py dry-run
python release.py dry-run --until TAGGED
python release.py manifest validate candidate/rc-manifest.json
python release.py status
```

`dry-run` walks the real operation graph with zero writes. `publish` requires an
explicit `--manifest` and `--yes`, and refuses to run against a placeholder
identity or a failing preflight.

---

## 6. Reproducibility boundary

Stated honestly rather than overclaimed.

**Pinned:** the Kroko Linux builder container (base image by digest, declared
apt package set, exactly pinned `pip`/`setuptools`/`wheel`); the production
image base (`ubuntu:24.04` by manifest digest); the Kroko upstream revision;
VoiceSTT's patch set and builder revisions; every third-party GitHub Action (by
full commit SHA); and the OCI `created` timestamp, which is derived from the
commit rather than the wall clock so a rebuild of the same source keeps the same
image identity.

**Not pinned:** the exact Debian point-versions of the builder's apt packages,
which are still resolved against the live bookworm archive. Closing that would
require a `snapshot.debian.org` pin, which is deliberately out of scope.

This is not a silent gap. A Linux Kroko fingerprint includes the real
`cmake`/`cc`/`c++`/OpenSSL identity probed inside the builder container, so a
materially different toolchain produces a *different fingerprint* and forces a
rebuild rather than reusing a mismatched artifact. The build fails closed on the
unpinned axis instead of pretending it does not exist — and the qualified
artifact itself, bound by SHA-256 in the RC manifest, is what becomes
publication authority.

---

## 7. Related documentation

- [`build/BUILD.md`](../build/BUILD.md) — build matrix, Kroko variants, local builds
- [`docs/kroko-onnx.md`](kroko-onnx.md) — the Kroko engine and Free/Pro models
- [`docs/stt-model-management.md`](stt-model-management.md) — offline model resolution
- [`build/vps/README.md`](../build/vps/README.md) — the separate private VPS deployment
