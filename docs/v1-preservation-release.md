# V1 preservation release 1.0.0

This document is the release-facing authority for the one-time V1 preservation
release before V2 integration. `build/vps/**` is explicitly not a public
release authority.
The final cross-repository order, explicit approval gates, and selected
historical safeguards are in [v1-release-final-plan.md](v1-release-final-plan.md).
The manual publish workflow must also be present on the repository default
branch before GitHub can dispatch it; pushing only the preparation branch
does not activate publication.

## Public Python product contract

V1.0.0 has two **alternative** Python distributions built from the exact same
VoiceSTT source commit:

- `voice-stt-server==1.0.0` — VoiceSTT V1 server plus embedded Kroko **Free** native runtime.
- `voice-stt-server-pro==1.0.0` — the same VoiceSTT V1 server plus embedded Kroko **Pro** native runtime.

Each project publishes exactly two CPython 3.12 wheels:

- Linux x86_64, with a native tag at least as restrictive as the embedded Kroko runtime.
- Windows AMD64, with a native tag at least as restrictive as the embedded Kroko runtime.

The Linux Kroko intermediate is compiled inside the source-controlled,
digest-pinned Python 3.12 Debian Bookworm builder. The runtime Dockerfile uses
that same base-image digest. This is part of the artifact identity and prevents
a newer hosted-runner GLIBC from making the Linux wheel unusable in the V1
container.

No V1.0.0 public sdist is produced. No public final wheel may be
`py3-none-any`. The final product wheel contains the actual `kroko_onnx`
payload (native extension plus bundled runtime libraries/DLL payload) directly;
it does not contain a nested Kroko wheel or a second `kroko_onnx-*.dist-info`.
The product wheel RECORD is rebuilt after embedding.

Normal users therefore install only one product:

```text
pip install voice-stt-server
```

or:

```text
pip install voice-stt-server-pro
```

After that, `import VoiceSTT`, `import VoiceSTT_server.server`,
`import kroko_onnx`, and `stt-server --help` must work without compiling Kroko
or installing a separate Kroko wheel. `stt-install-kroko --build` remains a
source/developer tool only.

Kroko `.data` model files are never embedded in the product wheels.

## Baked Free/Pro identity

`VoiceSTT/_release_variant.py` is the source-controlled variant marker. The
product-wheel assembler bakes `free` or `pro` into the final wheel. Runtime
resolution uses this baked identity by default. Explicit development/container
overrides remain possible through `runtime_variant` or
`VOICESTT_KROKO_VARIANT`, but `KROKO_API_KEY` is never a variant signal.

## Model policy

Faster-Whisper automatic model download remains **off by default**. Only the
reviewed aliases `tiny`, `base`, `small`, `medium`, `large`, and
`large_turbo` may be downloaded after explicit opt-in. Local CTranslate2 model
directories remain supported.

Kroko Free uses the known Community model source/cache behavior. Kroko Pro
never auto-downloads a model and never falls back to a Community model. A
missing Pro model produces an actionable provisioning error naming the default
model directory, `VOICESTT_KROKO_MODEL_ROOT`, the runtime credential
`KROKO_API_KEY`, and the official Kroko source. The default local Kroko model
root is platform-appropriate (Windows LocalAppData or Linux/XDG user data);
containers override it to `/models/kroko`.

The product packages and Docker images include fourteen OpenWakeWord ONNX
classifiers (listed in `wake-words.md`), including `hey_jarvis`, `alexa`,
`hey_mycroft`, `hey_rhasspy`, and `computer`, plus their feature pipeline.
Their CC BY-NC-SA 4.0 terms make this bundled set a
non-commercial distribution. External OpenWakeWord catalogs remain supported
as additive overrides. No Wake Word asset is downloaded at runtime.

## Native build authority

`tools/v1_kroko_release.py` pins upstream Kroko to
`8657e655192623b98d7708e742a72987f953d3a2` and fingerprints both variant and
platform. It builds four intermediate runtimes:

- free / linux_x86_64
- pro / linux_x86_64
- free / win_amd64
- pro / win_amd64

The pinned upstream revision contains the Docker-based Windows cross-build
(`build_windows.sh`) that produces real CPython 3.12 `win_amd64` wheels. Those
Windows wheels are later installed and imported on a real `windows-latest`
runner. A developer PC is never release authority.

`tools/v1_product_wheel.py` consumes the exact VoiceSTT source tree and exactly
one matching Kroko native wheel to assemble a single final product wheel. It
copies all non-dist-info Kroko payload, preserves license/NOTICE material,
bakes the variant marker, adopts the native runtime tag, marks the wheel
non-pure, and rebuilds RECORD.

## Docker product path

`build/v1-release.Dockerfile` consumes exactly one already-qualified **Linux
product wheel**. It does not install a second Kroko wheel and does not rebuild
Kroko. Free and Pro container labels, model mounts, offline deployment flags,
health checks, and secret checks remain in force.

## Normal correction/build validation

Pushes to `release/v1.0.0-prep` run real build validation:

1. build four pinned Kroko native intermediate wheels;
2. assemble four final product wheels;
3. `twine check` each final wheel;
4. clean-install Free and Pro Linux wheels in fresh venvs;
5. clean-install Free and Pro Windows wheels on `windows-latest`/CPython 3.12;
6. import `VoiceSTT`, `VoiceSTT_server.server`, and `kroko_onnx`;
7. run `stt-server --help` and `pip check`;
8. build Free and Pro Docker images from the final Linux product wheels;
9. create `v1-correction-1-evidence` with hashes, sizes, content dumps, logs,
   variant proof, model-policy evidence, secret/license evidence, CI identity,
   no-publication guard, and remaining-risk register.

All clean-install import and CLI checks change into a temporary directory
outside the checkout first. This prevents the source tree's intentional Free
development marker from shadowing the marker embedded in an installed Pro
wheel.

## Local acceptance before Candidate

GitHub CI is the release-authoritative build evidence, but it does **not**
replace the required operator-local acceptance. Before Candidate, the exact
correction HEAD must additionally be built and tested:

- once on the Windows x64 development PC with CPython 3.12 + Docker Desktop;
- once on the Linux x86_64 VPS with CPython 3.12 and the native build prerequisites.

Use the source-controlled `tools/v1_local_acceptance.py` runner. It builds Free
and Pro native runtimes for the host platform, assembles the final product
wheels, creates a fresh venv per variant, installs only the final wheel, and
runs imports, the baked variant check, `stt-server --help`, `pip check`, and
`pip list`. These local runs are additional acceptance evidence, not release
authority.

## Candidate workflow

`.github/workflows/release-candidate.yml` remains `workflow_dispatch` only and
must **not** be started during correction review. When later authorized it
rebuilds/qualifies the four exact public wheels, performs real Linux and Windows
clean-install checks, builds the two OCI images from the final Linux wheels,
persists private GHCR staging images, and emits one immutable
`v1-release-candidate` artifact. No sdist is part of that candidate.

## Publication and first-release PyPI bootstrap

`.github/workflows/release-publish.yml` is manual-only, protected by the
`release` environment, consumes exact candidate bytes, and contains no build
step. Publication order is:

1. publish/resume `voice-stt-server` Linux + Windows wheels;
2. on the first run, wait four minutes after both Free wheels match so the Pro
   Pending Publisher can be configured;
3. publish/resume `voice-stt-server-pro` Linux + Windows wheels;
4. Docker Hub immutable tags;
5. final GHCR immutable tags;
6. aliases `1.0`, `1`, `latest`;
7. verify all four PyPI wheels and all Free/Pro immutable + alias image digests;
8. create/resume the exact Git tag `v1.0.0` only after those checks pass;
9. create/verify the GitHub Release last.

Remote Python state is classified **per file** using only `ABSENT`, `MATCH`,
`CONFLICT`, or `UNKNOWN`. Only `ABSENT` files are staged; `CONFLICT` or
`UNKNOWN` is a hard stop. A project may therefore contain one MATCH and one
ABSENT file without inventing a fifth `PARTIAL` artifact state.

For the first public V1.0.0 release, the Pending Trusted Publisher is initially
configured only for `voice-stt-server`. After both Free wheels are uploaded and
verified MATCH, the workflow announces a **240-second setup window** and waits.
During that pause, the operator can configure the Pending Trusted Publisher for
`voice-stt-server-pro` using the same repository, `release-publish.yml`, and
`release` environment. After the pause the Pro job attempts publication. If the
publisher is ready, the **same workflow run** continues. If the Pro upload fails,
inspect the error, configure/correct the publisher, and rerun the **same
candidate/version**. Already MATCH Free artifacts are not uploaded again; only
ABSENT Pro files are staged. Only after all four Python wheels MATCH may Docker
Hub, final GHCR, and aliases run. The workflow then verifies both registries
against the candidate digests before creating the Git tag; the GitHub Release
page is last. PyPI and registry publication are themselves public writes and
cannot be made reversible by delaying the Git tag. A failed later step is
resumed against the same candidate/version, never rebuilt or overwritten.

## Preparation safety lock

During correction review: no force push, rebase, branch deletion, tag, GitHub
Release, PyPI write, Docker Hub final write, final GHCR write, Candidate run, or
Publish run. Existing `main`, dirty review, clean review, V2 branches,
AP-SRV-070, `build/vps/**`, APIs, trigger architecture, logging, and unrelated
code remain untouched.
