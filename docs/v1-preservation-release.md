# V1 preservation release 1.0.0

This document defines the one-time preservation release of the historical V1
line before V2 integration. It is deliberately narrower than the later V2
release architecture.

## Fixed product identity

The release source version is **1.0.0** and the Git tag is **v1.0.0**.

V1 has exactly one Python distribution:

- PyPI: `voice-stt-server==1.0.0`
- wheel: `voice_stt_server-1.0.0-py3-none-any.whl`
- sdist: `voice_stt_server-1.0.0.tar.gz`

The historical Python imports and entry points stay unchanged (`VoiceSTT`,
`VoiceSTT_server`, `stt-server`, `stt-install-kroko`, ...). Kroko is still a
separately built native runtime. There is **no** V1
`voice-stt-server-pro` Python distribution.

V1 does have two explicit container/Kroko build variants from the same source
release:

- Free: `voice-stt-server`
- Pro: `voice-stt-server-pro`

A Kroko API/license key is a runtime credential. It is never required to build
the Pro runtime and must not enter candidate build inputs, image history,
manifests, logs, or release artifacts.

## Source and build authorities

`VERSION` is the release version authority for Python packaging.

The historical V1 Kroko build behaviour remains in
`VoiceSTT/install_kroko.py`. The release helper
`tools/v1_kroko_release.py` adds only release concerns around that builder:

- upstream repository pinned to an immutable commit;
- separate Free/Pro fingerprints and caches;
- fingerprint binding to the V1 installer and standalone builder Dockerfile;
- SHA-256 verification of cached/built wheels;
- rejection of `KROKO_API_KEY` as a build input.

`build/v1-kroko-builder.Dockerfile` is the standalone Linux/AMD64 native build
environment. `build/v1-release.Dockerfile` is the production-image path. The
production image consumes already-built Python and Kroko wheels; it never
recompiles Kroko and never installs VoiceSTT editable from a source checkout.
Its runtime paths, CPU defaults, model aliases, healthcheck and command remain
V1-compatible.

`build/vps/**` is explicitly not a public release authority.

## Workflows

### 1. Normal preparation CI

`.github/workflows/v1-release-prep-ci.yml` runs on pushes to the disposable
preparation branch. It performs only read/build/test work and checks, on Linux
and Windows:

- V1 version and source identity;
- one wheel plus one sdist;
- `twine check`;
- historical package/import/entry-point shape;
- absence of an embedded Kroko runtime in the Python wheel;
- Kroko fingerprint/cache rules;
- candidate manifest rules;
- publication conflict/UNKNOWN handling;
- workflow trigger/permission/rebuild guards.

This workflow publishes nothing.

### 2. Candidate workflow

`.github/workflows/release-candidate.yml` is `workflow_dispatch` only.

It builds the exact candidate once:

1. `voice-stt-server` wheel and sdist;
2. pinned Kroko Free and Pro Linux wheels in separate fingerprint caches;
3. Free and Pro production images from those exact inputs;
4. import/identity/secret smoke checks;
5. private GHCR staging pushes for immutable image persistence;
6. one canonical `v1-release-candidate` Actions artifact containing the Python
   artifacts, Kroko artifacts, OCI digest records, `rc-manifest.json`, and a
   SHA-256 inventory.

The workflow requires the operator to confirm that the two
`*-v1-staging` GHCR packages are private before it will proceed. Candidate
staging is not a final/public release surface. The candidate workflow does not
create `v1.0.0`, upload to PyPI, write Docker Hub final tags, write final GHCR
tags, move public aliases, or create a GitHub Release.

### 3. Publication workflow

`.github/workflows/release-publish.yml` is `workflow_dispatch` only and consumes
one existing `v1-release-candidate` by Candidate workflow run ID. It contains no
Python or Docker rebuild.

It must be dispatched from the exact source commit recorded in the candidate.
Every job that can perform an irreversible/public write uses the protected
GitHub Environment `release`.

Publication order is fixed:

1. create/resume immutable Git tag `v1.0.0`;
2. publish/resume `voice-stt-server==1.0.0` on PyPI;
3. promote the exact Free and Pro candidate OCI manifests to Docker Hub
   `:1.0.0`;
4. promote the same digests from Docker Hub to final GHCR `:1.0.0`;
5. after exact identities match in both registries, move aliases `1.0`, `1`,
   and `latest` for both variants;
6. create the GitHub Release last;
7. read back PyPI, tag, release assets, exact image tags and all aliases.

The final workflow emits `v1-release-complete` only after those readbacks
succeed.

## Resume and conflict semantics

Before a public write, the workflow checks the relevant remote identity:

- **ABSENT**: the exact artifact/tag is not present; publication may proceed.
- **MATCH**: the already-published identity is byte/digest-equivalent; resume
  without republishing it.
- **CONFLICT**: the same public version/tag exists with a different identity;
  hard stop.
- **UNKNOWN**: remote state cannot be established safely; hard stop.

A partially uploaded PyPI `1.0.0` is resumable only when every already-present
file hash matches the candidate; only absent candidate files are staged for the
next upload. A partial public release therefore continues **1.0.0** rather than
inventing a replacement version.

## Required GitHub / registry configuration before candidate qualification

Before running `release-candidate.yml`:

- verify the GHCR candidate packages
  `voice-stt-server-v1-staging` and `voice-stt-server-pro-v1-staging` are
  private candidate storage;
- confirm GitHub Actions has package write permission for those staging
  packages.

Before running `release-publish.yml`:

- configure/protect the GitHub Environment named `release` and require the
  desired human approval there;
- keep the PyPI Trusted Publisher for project `voice-stt-server` bound to this
  repository, workflow filename `release-publish.yml`, and environment
  `release`;
- set repository/environment variable `DOCKERHUB_USERNAME`;
- set secret `DOCKERHUB_TOKEN` with package push permission (delete permission
  is not required);
- ensure the workflow's `GITHUB_TOKEN` can read candidate artifacts and
  read/write the required GHCR packages;
- do **not** configure or use a V1 `voice-stt-server-pro` PyPI publisher.

## Operator sequence

The preparation branch is intentionally disposable. Once review is complete,
create one clean release-prep commit from the verified V1 base plus the
approved release changes. Run normal CI on that exact commit.

Then, without changing source bytes:

1. dispatch `release-candidate.yml` on that exact commit and record its run ID;
2. inspect the run evidence and canonical candidate artifact;
3. only after qualification, dispatch `release-publish.yml` on the **same
   commit** with that candidate run ID and version `1.0.0`;
4. if publication stops, fix only the operational cause and resume the same
   version/candidate. Do not rebuild a substitute candidate after public
   publication has begun.

During preparation and review, do not create the public tag, PyPI release,
Docker Hub final tags, final GHCR tags/aliases, or GitHub Release.
