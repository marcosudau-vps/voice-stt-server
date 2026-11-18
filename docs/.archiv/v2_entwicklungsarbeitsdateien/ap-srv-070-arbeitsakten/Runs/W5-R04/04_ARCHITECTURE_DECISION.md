# W5-R04 — 04 Architecture Decision

The decisions this run made, why, and what was rejected. Where the original
prompt and the later binding product/packaging authority conflict, the later
authority governs (see `02_IMPLEMENTATION_PLAN.md`, Addendum A).

---

## AD-1 — Two complete alternative distributions, not one plus a build step

**Decision.** VoiceSTT publishes `voice-stt-server` (Kroko Free runtime) and
`voice-stt-server-pro` (Kroko Pro runtime). Each wheel *contains* its native
runtime. Both expose the import package `voice_stt_server` and the CLI
`voice-stt-server`.

**Why.** Free and Pro Kroko are different native runtimes and cannot be swapped
at runtime. The previous model asked the end user to run
`stt-install-kroko --build`, i.e. a ~30-minute native compile, or to install a
separate wheel by hand. That is not an installable product.

**Rejected alternatives.**

* *One distribution plus a public `kroko-onnx-free`/`-pro` package.* Explicitly
  forbidden by the authority, and it would push the Free/Pro decision into
  dependency resolution, where a wrong resolution silently produces the wrong
  runtime.
* *One distribution with an extra that compiles Kroko.* Same 30-minute build,
  same failure mode, and it makes `pip install` non-deterministic.
* *Renaming `VoiceSTT` to `voice_stt_server`.* A large, unrelated compatibility
  break. `voice_stt_server` is added as a thin lazy re-export instead, so both
  names work and there is still exactly one implementation.

**Consequence.** The two distributions are mutually exclusive. This is
documented in the README, `docs/installation.md` and `docs/release-process.md`,
and the packaging expresses it by both distributions providing the same import
package (installing both into one environment would collide on files).

---

## AD-2 — Merge the qualified Kroko wheel, do not rebuild it

**Decision.** `tools/build_distribution.py` unpacks the *qualified* Kroko wheel
and copies its payload (`kroko_onnx/`, `sherpa_onnx/`, the top-level
`_sherpa_onnx…` extension module) verbatim into the VoiceSTT wheel, then
retags the result for the concrete interpreter/platform.

**Why.** The Kroko artifact is qualified by fingerprint and SHA-256. Release
authority requires that the exact qualified bytes reach the user, so they are
copied, not regenerated. The merged wheel records the source artifact's SHA-256,
which keeps the chain `Kroko artifact → distribution wheel → PyPI` checkable
end to end.

**Rejected alternative.** Letting setuptools vendor the runtime via
`package_dir`. That would rebuild the payload through a second toolchain, break
the identity chain, and handle the root-level extension module awkwardly.

**Detail.** The foreign `kroko_onnx-*.dist-info` is deliberately *not* shipped:
it would make `pip`/`importlib.metadata` believe a `kroko-onnx` distribution is
installed that pip never installed and cannot uninstall. The runtime identity is
carried by `voice_stt_server/_embedded_kroko.json` instead, and Kroko's licence
text is copied into our own `dist-info/licenses/` so redistribution stays
correct.

**Verified.** The merge was exercised against the real 8.3 MB Kroko payload and
is byte-reproducible across runs.

---

## AD-3 — The installed distribution decides the runtime

**Decision.** `VoiceSTT.kroko.artifacts.verify_installed_runtime` resolves the
installed variant from the distribution's own embedded provenance first, and
only falls back to a separately installed `kroko-onnx` distribution for a
developer environment.

**Why.** The authority forbids `if key exists: use pro`. A licence key is a
runtime credential for an already-installed Pro runtime; it must never select
one. Reading the variant from the installed distribution makes that structural.

---

## AD-4 — Honest platform matrix, and no sdist

**Decision.** `python_requires = ">=3.12,<3.13"` for the two public
distributions; supported targets are CPython 3.12 on `linux_x86_64` and
`win_amd64`. No sdist is published for them. The historical development
distribution (`voicestt`) keeps `>=3.11`.

**Why.** The Kroko build authority produces cp312-only wheels for exactly those
two platforms. Claiming Python 3.11 would advertise a target on which the
shipped runtime does not exist.

An sdist cannot carry a native runtime. Publishing one would mean that wherever
pip preferred it, the install would either trigger a local native build or
silently produce an installation with no Kroko runtime — both of which break the
guarantee these distributions exist to provide. A wheel is published for every
documented platform, so pip never needs an sdist on a supported target; on an
unsupported target the install fails loudly instead of quietly producing
something incomplete.

This supersedes the original prompt's section 10 sdist requirement, under the
later authority's section 9, and is recorded in `08_DEVIATIONS.md`.

---

## AD-5 — Tag first, then PyPI, then Docker Hub, then GHCR

**Decision.** The canonical order becomes:

```text
PREPARED → TAGGED → PYPI_PUBLISHED → DOCKERHUB_PUBLISHED → GHCR_PUBLISHED
        → EXTERNAL_VERIFIED → ALIASES_PUBLISHED → GITHUB_RELEASED
        → FINAL_VERIFIED → COMPLETE
```

**Why.**

* *Tag first:* once `2.0.0` exists on PyPI or in a registry the version is
  publicly reserved, so the immutable source anchor must already exist during
  any partial publication.
* *Docker Hub before GHCR:* GHCR is a promotion of the exact Docker Hub manifest
  by digest, so Docker Hub must exist first. There is no second production build
  anywhere in the graph.
* *Aliases after external verification:* `latest` must never point at a release
  candidate, a failed release or a half-published one.
* *GitHub Release last:* it is the public success marker, so it must be the last
  thing that happens.

**Enforced twice.** Structurally by `STEP_DEFINITIONS`, and defensively by
barriers the adapters assert themselves (`assert_tag_allowed`,
`assert_public_publication_allowed`, `assert_aliases_allowed`,
`assert_github_release_allowed`), so the order holds even if an adapter is ever
driven by something other than the engine.

---

## AD-6 — One graph, bounded per job (`--until`)

**Decision.** `run_engine(..., stop_after=STATE)`. Each publish job runs
`release.py publish --until <STATE>` and passes the release state to the next
job as a workflow artifact.

**Why.** Least privilege requires separate jobs (`id-token: write` only on the
PyPI job, `contents: write` only where a tag/release happens). Splitting the
*graph* across jobs would have created exactly the "release.py says one order,
the workflow says another" failure the prompt forbids. `stop_after` can only
shorten a plan — it never reorders, skips, or permits a forbidden transition —
so the order, the barriers and the fail-closed semantics stay in one place.

**Rejected alternative.** One job holding every credential. Simpler, but it
would hand `id-token: write`, `contents: write` and `packages: write` to a
single step.

---

## AD-7 — PyPI Trusted Publishing as an explicit executor boundary

**Decision.** On the GitHub path the upload is performed by
`pypa/gh-action-pypi-publish` under OIDC. The engine does not *perform* that
write — it **verifies** it, and only then advances to `PYPI_PUBLISHED`. The
`ExternalUploader` refuses loudly rather than falling back to another credential
path. The local Twine path is retained for manual operation.

**Why.** The state machine has to stay authoritative rather than decorative. A
state transition driven by an action's exit code would mean the release state
records "published" on the strength of a process's return value; instead it
records it on the strength of the exact expected filenames and SHA-256 hashes
being verifiably present on PyPI. No PyPI token exists anywhere in the
repository.

---

## AD-8 — Private GHCR staging as candidate persistence

**Decision.** Qualified images are pushed to private GHCR staging packages
tagged by candidate id and referenced by digest. Wheels and manifests are
GitHub Actions artifacts (90-day retention).

**Why.** The approval boundary sits between qualification and publication, so
the qualified OCI manifests must survive across workflow runs without being
rebuilt. A digest-pinned staging reference is what lets publication promote the
*same* manifest.

**Rejected alternative.** OCI archives as workflow artifacts. Two multi-hundred-MB
tarballs per candidate, slower, and they would still have to be re-imported and
re-pushed — which would change the digest and defeat the purpose.

**Fails closed.** A candidate whose staging push did not happen has no digest,
and RC-manifest assembly refuses it rather than accepting a candidate that only
looks complete.

---

## AD-9 — Registry identity is the manifest digest

**Decision.** `remote_checks` compares the remote **OCI manifest digest**, via
`docker buildx imagetools inspect --format {{.Manifest.Digest}}`, against the
digest recorded in the candidate manifest.

**Why.** This corrects a real pre-existing defect: the previous code compared
the remote manifest digest against the *local* `docker inspect` image `Id`.
Those are different things (a local config-blob digest versus a remote manifest
digest) and can never legitimately be equal, so every real registry verification
would have raised a spurious `CONFLICT`. The manifest digest is also exactly the
identity `docker buildx imagetools create` promotes between registries.

**Aliases are checked differently on purpose.** An alias pointing elsewhere is
*not* a conflict — moving it is the point — so alias checks return `ABSENT`
rather than raising, which makes the alias step idempotent on a resume. Only
exact version tags are immutable.

---

## AD-10 — Derive what is safe, ask for what is not

**Decision.** The GHCR root is derived as `ghcr.io/<repository owner>`. The
Docker Hub namespace stays operator-configured (`DOCKERHUB_USERNAME`, a
repository *variable*), and preflight fails closed when it is missing.

**Why.** A GHCR package always lives under the repository owner, and the owner
is known — deriving it is a fact, not a guess. A Docker Hub namespace has no
relationship to the GitHub owner, so guessing one could publish into somebody
else's account. Operator configuration is therefore one variable and one secret.

---

## AD-11 — Pin the Linux Kroko builder container; do not build a hermetic-build project

**Decision.** The Linux builder container becomes a declared, source-controlled
authority (base image by digest, declared apt package set, exactly pinned
`pip`/`setuptools`/`wheel`), `LINUX_BUILDER_REVISION` is bumped 1 → 2, and a
guard test hashes the declaration together with the Dockerfile so neither can
drift without a revision bump.

**Why.** A finding of this run: `fingerprint.toolchain_identity("linux")`
returns `{"kind": "host-native"}` — but the Linux fingerprint is *not* actually
blind, because `install_kroko.fingerprint_for` passes a probed toolchain
identity (real `cmake`/`cc`/`c++`/OpenSSL) on Linux. So the pre-existing state
was **not** a correctness hole the way Windows Finding J was: a different
toolchain already produced a different fingerprint and failed closed.

It was a *stability* hole. A floating `python:3.12-slim-bookworm` tag makes the
fingerprint drift for reasons nobody declared, which destroys artifact reuse on
a fresh runner. Pinning the container fixes that. Pinning `setuptools`/`wheel`
is genuinely build-effective (it decides how the wheel is built and tagged —
the same reasoning already applied to `WINDOWS_PACKAGING_TOOLS`), which is why
the revision bump is correct rather than cosmetic.

**Honest boundary.** The exact Debian point-versions of the builder's apt
packages are still resolved against the live archive. Closing that needs a
`snapshot.debian.org` pin, which the prompt explicitly declines to turn into a
hermetic-build project. This is documented in `buildinputs.py`, in
`docs/release-process.md` §6, and it fails closed rather than silently: a
changed compiler or CMake version is probed and moves the fingerprint.

**Windows untouched.** `WINDOWS_BUILDER_REVISION` stays 4, so the already
qualified Windows artifact is not invalidated by a Linux-only correction.

---

## AD-12 — Source-derived build timestamp

**Decision.** `BUILD_DATE` comes from the commit's committer date, not the wall
clock. `--build-date` remains as an explicit override.

**Why.** Two builds of the identical commit previously produced images with
different metadata and therefore different digests. That is harmless for a
one-shot build but hostile to a model where publication consumes an
already-qualified candidate and a resume must re-derive rather than re-invent
one. It is still a correct `org.opencontainers.image.created` value — the
instant the source came into existence — and it is a pure function of the
commit, so it is identical on every runner.

---

## AD-13 — Fail closed on a `--dist-dir` the Dockerfile cannot read

**Decision.** `tools/build_production.py` validates up front that `--dist-dir`
is the repository's own `dist/`.

**Why.** Found while proving the empty-artifact-store path: the production
Dockerfile copies staged wheels with literal `COPY dist/...` instructions
relative to the repository-root build context, so a `--dist-dir` anywhere else
can never work. Before this guard the orchestrator ran a full ~25-minute native
Kroko build and only then failed at the image step with an opaque
`lstat /dist/voicestt: no such file or directory`. The option now refuses
immediately and explains why, instead of advertising flexibility the build
contract does not have.

---

## AD-14 — Documentation tells the truth about the product surface

**Decision.** README fully rewritten. `docs/engines/` removed; the two retained
guides moved to `docs/faster-whisper.md` and `docs/kroko-onnx.md`.
`docs/transcription-engines.md` reduced to the two supported production
engines, with an explicit statement that the other adapters are
internal/experimental. New `docs/release-process.md`. No engine implementation
module was deleted.

**Why.** The source still contains lazily-loaded adapters for other engine
families. Deleting them would be an unrelated compatibility break the prompt
forbids; advertising them as production support would be untrue. Naming them
honestly as internal and unqualified is the only option that is both accurate
and non-breaking.

The README claims no PyPI, Docker Hub or GHCR URL and carries no badge, because
`2.0.0` is not published yet. Guard tests enforce that, that every relative link
resolves, and that no maintained document links into the removed tree.
