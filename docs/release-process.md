# Release process

V2 has one public product, `voice-stt-server`, with the qualified Pro-capable
Kroko native runtime embedded. The historical `voicestt` developer distribution
is not a public V2 release surface. Native build procedures and authoritative
inputs remain in [build/BUILD.md](../build/BUILD.md).

## Release surfaces and platform matrix

| Surface | Product |
| --- | --- |
| PyPI | `voice-stt-server` |
| Docker Hub | `marcosudau/voice-stt-server` |
| GHCR | `ghcr.io/marcosudau-vps/voice-stt-server` |

Exactly one wheel per target: CPython 3.12 `linux_x86_64` and `win_amd64`.
One production image targets `linux/amd64`. No sdist is published for the public product,
because the embedded native runtime is required for a complete installation.
An unsupported interpreter/platform must fail rather than compile Kroko locally.

Community models require no key. Pro entitlement is model-specific and separate
from the installed native capability and the active model. Models and credentials
are never bundled in candidate artifacts.

## Candidate manifest schema 3

Schema 3 replaces the former two-product schema 2. `distributions` and `images`
each contain exactly one `pro` entry. This key describes the native build input;
it does not name a separate product edition. The distribution name is always
`voice-stt-server`. Schema 2 candidates are rejected rather than silently migrated.

The manifest binds the exact source commit and tree, product version, two wheel
filenames and SHA-256 hashes, interpreter/ABI/platform tags, native fingerprints
and original native-wheel hashes. Image identity is the OCI manifest digest,
with a digest-pinned private staging reference. A local Docker image ID is not
a registry manifest identity. Duplicate platforms or additional products fail.
`candidateId`, workflow run and manifest SHA-256 bind resume state to the candidate.
No artifact is substituted on resume.

`redistributionApproval` records contractual status and evidence independently
of technical `releaseReadiness`. `build/kroko-redistribution.json` is the reviewed
source of that approval. Technical qualification never changes BLOCKED into
VERIFIED. Missing rights evidence prevents a real release before any tag/write.
See [license gates](licenses.md#unified-v2-release-gate).

## Candidate workflow

`.github/workflows/release-candidate.yml` is dispatch-only. Linux resolves the
Pro native artifact using the existing fingerprint authority inside the builder
container. Windows is cross-built on Linux and qualified on Windows. Each
platform consumes only the Pro artifact cache. Cache entries are reverified;
a miss builds the pinned source with the declared toolchain. Changing product
names or Python code does not change native fingerprints.

The complete Linux product wheel is built once and used by both the image and
the candidate. The image installs no separate `kroko-onnx` distribution. Both
platform wheels retain one product `.dist-info` owner, native payload, notices
and complete provenance. Qualification includes fresh full-dependency installs,
`pip check`, native imports and real HTTP/WebSocket identity checks outside the
source checkout. Packaging tests additionally exercise real wheel/sdist paths
with explicitly synthetic native fixtures; those fixtures prove no native behavior.

The candidate workflow can push only to the private
`voice-stt-server-staging` package, when explicitly requested by dispatch. It
creates no public PyPI/registry artifact, Git tag or GitHub Release. Workflow
artifacts are retained for 90 days; an expired candidate needs a new qualified
run with a new candidate identity. Ordinary CI is read-only on Ubuntu and Windows.

Real model/native lifecycle qualification is separate from import/identity
qualification. The Linux Pro reload/shutdown path must have real process-isolated
evidence; mock tests cannot satisfy that gate. Results distinguish PASS, FAILED,
NOT_RUN and external blockers. A required NOT_RUN check does not qualify a release.

## Publication and resume

`.github/workflows/release-publish.yml` consumes the qualified candidate without
rebuilding. All jobs use the protected GitHub Environment `release` with an
explicit reviewer approval. The canonical graph lives in `release_tooling/engine.py`:

```text
PREPARED -> TAGGED -> PYPI_PUBLISHED -> DOCKERHUB_PUBLISHED
 -> GHCR_PUBLISHED -> EXTERNAL_VERIFIED -> ALIASES_PUBLISHED
 -> GITHUB_RELEASED -> FINAL_VERIFIED -> COMPLETE
```

1. Verify all qualification and redistribution gates and obtain release approval.
2. Create the immutable Git tag at the qualified source commit.
3. Publish the two qualified platform wheels to the single PyPI project.
4. Promote the qualified staging OCI manifest to Docker Hub by digest.
5. Promote that same Docker Hub manifest to GHCR without building.
6. Verify external artifact identities.
7. Publish and verify moving aliases (`2.0`, `2`, `latest` for stable 2.0.0).
8. Create the GitHub Release as the last public success marker; verify and complete.

Prereleases receive no moving aliases. `0.x.y` receives no broad `0` alias.
Read-only probes return ABSENT, MATCH, CONFLICT or UNKNOWN. MATCH skips a write;
ABSENT permits only the missing write. CONFLICT or UNKNOWN stops publication.
Existing immutable remote artifacts are never deleted, overwritten or force moved.

A failed publication resumes under the same version and candidate identity.
If one platform wheel was uploaded, only the missing wheel is staged for upload.
If Docker Hub promotion succeeded before a failure, resume verifies that digest
and continues with GHCR. State advances only after remote re-verification, not
merely because an upload command exited successfully. A partial 2.0.0 remains
2.0.0; it is not automatically renamed 2.0.1.

## Operator setup

Set repository variable `DOCKERHUB_USERNAME=marcosudau` and provide the
`DOCKERHUB_TOKEN` through the protected release environment. GHCR derives
`ghcr.io/${{ github.repository_owner }}` and uses `GITHUB_TOKEN` with job-scoped
package permissions. One PyPI Trusted Publisher belongs to `voice-stt-server`:
owner `marcosudau-vps`, repository `voice-stt-server`, workflow
`release-publish.yml`, environment `release`. No PyPI API token is stored.

The `tag` job has contents write; `pypi` has OIDC write; `registries` has package
write; `finalize` has contents/package write. Ordinary pushes, PRs and forks
cannot access these publication permissions. Native builds never require a
Kroko key. Real Pro model qualification injects runtime credentials separately.

Read-only inspection:

```bash
python release.py preflight
python release.py dry-run
python release.py dry-run --until TAGGED
python release.py manifest validate candidate/rc-manifest.json
python release.py status
```

Real `publish` requires an explicit qualified manifest, `--yes`, valid rights
evidence and passing preflight. Run the candidate workflow at the intended
commit, review its artifacts and gates, then dispatch the publish workflow with
that candidate run ID and obtain protected-environment approval. This work does
not authorize an actual publication.

## Reproducibility boundary

Native upstream revision, patch/builder revisions, Windows toolchain downloads
and checksums, builder identities, production base digest, action commits and
source-derived timestamps remain pinned. Linux system toolchain components are
probed inside the builder and enter the fingerprint. **Not pinned:** exact Linux apt package point versions remain resolved against
live repositories; a `snapshot.debian.org` pin would be needed to close that axis.
This remains a reproducibility limitation; a changed toolchain changes the fingerprint
instead of reusing mismatched native bytes. Final publication consumes only the
qualified bytes and OCI manifest.

See [testing](testing.md), [Kroko](kroko-onnx.md),
[model management](stt-model-management.md) and
[private VPS deployment](../build/vps/README.md).
