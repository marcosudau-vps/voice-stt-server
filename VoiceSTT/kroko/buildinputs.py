"""The declared, source-controlled Kroko native build inputs (AP-SRV-070 W4A).

This module is the single authority for *everything that can change the bytes
of a compiled Kroko runtime*. It exists so the expensive native build can be
decoupled from the ordinary VoiceSTT build: a fingerprint computed from these
declared inputs decides whether an already-built artifact may be reused.

Two rules govern what belongs here:

**Everything in this module is a build input.** Changing any value here must
change the fingerprint, because it can change the produced binary. That is why
the upstream revision is pinned to an immutable commit rather than a branch
name: ``cross-platform-builds`` is a moving target, and a build that silently
follows a branch head is not reproducible.

**Nothing else is a build input.** The VoiceSTT product version (``VERSION`` /
``VOICESTT_BUILD_VERSION``, AP-SRV-070 W3), the FastAPI server, the wake-word
code, the docs and the README are deliberately *not* referenced here, so a
normal server change or a release version bump can never force a ~30-minute
native recompilation.
"""

from __future__ import annotations

#: The Kroko upstream repository the runtime is built from.
KROKO_UPSTREAM_REPO = "https://github.com/kroko-ai/kroko-onnx.git"

#: The immutable upstream commit this project builds and qualifies.
#:
#: AP-SRV-070 W4A pinned this from the checkout that produced the currently
#: qualified free wheel (``kroko_onnx-1.12.9-1free-cp312-cp312-win_amd64``).
#: An upstream upgrade is a deliberate edit of this constant, which changes the
#: fingerprint and therefore forces exactly one new qualified build.
KROKO_UPSTREAM_REVISION = "8657e655192623b98d7708e742a72987f953d3a2"

#: The branch the pinned revision was reachable from. Informational only: it
#: documents provenance and gives ``git clone`` a cheap starting point. It is
#: never the authority - the revision above is, and the builder checks out that
#: commit explicitly.
KROKO_UPSTREAM_BRANCH_HINT = "cross-platform-builds"

#: The upstream files VoiceSTT patches before building. Listed so the guard
#: test in ``tests/unit/test_kroko_fingerprint.py`` can prove the patch set and
#: :data:`PATCH_SET_REVISION` stay in sync, and so a reader can see exactly how
#: far this project deviates from pristine upstream.
PATCHED_UPSTREAM_SOURCES = (
    "build_windows.bat",
    "Dockerfile.windows",
    "in_windows_container.sh",
    "sherpa-onnx/csrc/license.h",
)

#: Revision of VoiceSTT's own patch set applied to the upstream checkout.
#:
#: The patches (see ``VoiceSTT/install_kroko.py``) really do change the compiled
#: output - they switch WebSocket support on, change how OpenSSL is provisioned
#: and wrap the native license logging - so the patch set is a build input.
#: Bump this whenever the *content* of those patches changes. A guard test
#: fails if the patch functions change without a bump, so this cannot silently
#: drift.
#:
#: Bumped 1 -> 2 (AP-SRV-070 W4A-C3, Root Finding J): the Windows Dockerfile
#: patch no longer emits an availability-driven OpenSSL search loop and now
#: pins every externally downloaded builder input (base image digest, apt
#: snapshot, packaging tools, CMake/xwin/Python-target/VC redistributable and
#: OpenSSL) to a declared version plus SHA-256, and the container build script
#: verifies the openfst source archive against a declared SHA-256. That really
#: does change the produced bits, so the patch set is a new revision.
#:
#: Bumped 2 -> 3 (AP-SRV-070 W4A-C4, Root Finding L/M): the Windows Dockerfile
#: patch now pins the Microsoft Channel Manifest, Package Manifest, Windows
#: SDK version, and MSVC CRT version for xwin, verifies downloaded manifests
#: against declared byte counts and source-controlled SHA-256 digests, and
#: invokes xwin with explicit --manifest, --sdk-version, and --crt-version
#: arguments without relying on unpinned upstream latest fallbacks.
PATCH_SET_REVISION = 3

#: Revision of the builder logic itself: which revision gets checked out, which
#: patches are applied, how the compiler is invoked, and which produced wheel is
#: taken as the artifact.
#:
#: This is the second half of "VoiceSTT-specific Kroko build inputs". The
#: fingerprint deliberately hashes *declared values* rather than source files,
#: so that ordinary edits to unrelated VoiceSTT code cannot invalidate a
#: 30-minute build. The flip side is that build-effective changes to the
#: builder must be declared here, or a stale artifact would be reused for a
#: build that would now produce different bytes.
#:
#: **Update obligation:** bump this whenever any function in the builder
#: surface listed by the guard test changes in a way that affects what gets
#: built or which wheel is selected. The guard test in
#: ``tests/unit/test_kroko_fingerprint.py`` hashes that surface and fails if it
#: changed without a bump, so the obligation is enforced rather than trusted.
#:
#: Bumped 1 -> 2 (AP-SRV-070 W4A-C1, Root Findings A/B/C): the guarded surface
#: grew to include the effective repo/revision now flowing into the fingerprint
#: (``fingerprint_for``), the sanitized Linux build environment (ambient
#: overrides removed, ``SHERPA_ONNX_CMAKE_ARGS``/``SHERPA_ONNX_MAKE_ARGS`` fully
#: declared rather than appended/defaulted), and the new secret-boundary
#: sanitizer shared by both platforms (``sanitize_build_subprocess_env``,
#: ``windows_build_env``).
#:
#: Bumped 2 -> 3 (AP-SRV-070 W4A-C2, Root Findings E/F): the Linux build
#: environment now declares ``KROKO_LICENSE`` explicitly instead of only
#: setting it for ``pro``, and every real build now forces the external
#: Kroko builder checkout to a pristine state (``materialize_pristine_checkout``)
#: before applying VoiceSTT's patches, so a stale patch, CMake cache or
#: build artifact from a previous run can never influence a new build.
#:
#: Bumped 3 -> 4 (AP-SRV-070 W4A-C3, Root Finding I): ``prepare_checkout``
#: now proves that a reused external builder checkout actually belongs to the
#: effective ``--repo`` authority before any fetch or build, and re-clones it
#: from that authority when it does not.
BUILDER_REVISION = 4

#: CMake flags forced for the CPU-only Linux build. Kroko's license client
#: includes websocketpp headers unconditionally, which is why WebSocket support
#: stays ON even for a CPU-only server build.
#:
#: AP-SRV-070 W4A-C2, Root Finding G.2: the pinned upstream's own CMakeLists
#: defaults ``SHERPA_ONNX_USE_PRE_INSTALLED_ONNXRUNTIME_IF_AVAILABLE`` to
#: ``ON``, so the mere presence of a host-installed ONNX Runtime could
#: silently change what a build under the *same* declared fingerprint links
#: against. Forced OFF here so the build is deterministic regardless of what
#: else happens to be installed on the host.
LINUX_CMAKE_FLAGS = (
    "-DCMAKE_BUILD_TYPE=Release "
    "-DSHERPA_ONNX_ENABLE_GPU=OFF "
    "-DSHERPA_ONNX_ENABLE_PORTAUDIO=OFF "
    "-DSHERPA_ONNX_ENABLE_WEBSOCKET=ON "
    "-DSHERPA_ONNX_ENABLE_TTS=OFF "
    "-DSHERPA_ONNX_ENABLE_SPEAKER_DIARIZATION=OFF "
    "-DSHERPA_ONNX_ENABLE_BINARY=OFF "
    "-DSHERPA_ONNX_USE_PRE_INSTALLED_ONNXRUNTIME_IF_AVAILABLE=OFF"
)

#: Parallelism for the Linux build. Build-effective only in wall-clock terms,
#: but kept declared so the recorded build inputs are complete.
LINUX_MAKE_ARGS = "-j2"

#: The environment switch that makes the upstream build produce a Pro-capable
#: runtime. This is a *build* switch, never a license key: the Pro runtime is
#: built without any key, and the key is supplied only at run time.
PRO_BUILD_ENV_NAME = "KROKO_LICENSE"
PRO_BUILD_ENV_VALUE = "ON"

#: The explicit value the Linux builder sets for a free build.
#:
#: AP-SRV-070 W4A-C2, Root Finding E: this switch must never be inherited
#: ambiently from the operator's shell. Before this fix, only the ``pro``
#: branch set it explicitly; a ``free`` build silently kept whatever
#: ``KROKO_LICENSE`` value (if any) the parent process already had, which
#: could turn a ``--variant free`` build into a licensed one. The Linux
#: builder now always declares this switch explicitly - ``ON`` for pro,
#: ``OFF`` for free - never leaving it to ambient inheritance either way.
PRO_BUILD_ENV_OFF_VALUE = "OFF"

#: Environment variable names that toggle a Kroko build *capability* rather
#: than carry a secret. Distinct from ``KROKO_LICENSE_KEY_ENV_NAMES`` in
#: ``VoiceSTT/install_kroko.py`` (the four runtime license *keys*): stripping
#: this from a build subprocess's ambient environment is about determinism
#: and the Free/Pro hard boundary, not about secrecy. Every native build
#: subprocess environment removes this ambiently and re-declares it
#: explicitly where it is meaningful (currently: the Linux build).
KROKO_CAPABILITY_SWITCH_ENV_NAMES = (PRO_BUILD_ENV_NAME,)

#: --------------------------------------------------------------------------
#: The immutable Windows cross-build toolchain (AP-SRV-070 W4A-C3, Finding J)
#: --------------------------------------------------------------------------
#:
#: The Windows wheel is cross-built inside Kroko's own Docker image. Until C3
#: the fingerprint described that toolchain only as
#: ``"definedBy": "upstream-revision+patch-set"``, which was not true: the
#: image pulled a floating ``ubuntu:24.04`` tag, resolved apt packages against
#: the live archive, installed unpinned Python packaging tools, downloaded
#: several binaries with no content hash at all, and - worst - picked whichever
#: OpenSSL version slproweb still happened to be serving. The *same* declared
#: fingerprint could therefore describe materially different compiled bytes.
#:
#: Everything below closes that hole the way the root correction demands
#: (Variant A - pin the build inputs): every externally supplied byte that can
#: reach the produced wheel is named by an exact version *and* an immutable
#: identity (a digest, a snapshot instant, or a SHA-256). All of it is plain
#: source-controlled data, so ``fingerprint_for()`` / ``describe_artifact()``
#: keep computing the Windows fingerprint offline - no Docker build, no
#: registry lookup, no network - which is what keeps an ordinary artifact
#: REUSE cheap.
#:
#: **Update obligation:** changing any constant here changes the Windows
#: toolchain authority and therefore the fingerprint, which correctly forces
#: exactly one new qualified build. If a pinned source ever disappears, the
#: build must fail loudly and the pin must be updated deliberately - never
#: silently fall back to different bits.

#: The builder base image, pinned by immutable manifest digest rather than by
#: the floating ``24.04`` tag.
WINDOWS_BASE_IMAGE = "ubuntu:24.04"
WINDOWS_BASE_IMAGE_DIGEST = (
    "sha256:33ceb71981b602c1a7443a53469e4dba065f7503eab3078a2d7a57a2ab987517"
)

#: Canonical Ubuntu archive snapshot the builder resolves *all* apt packages
#: against. This is what makes the compiler and linker themselves immutable:
#: ``apt-get install clang-19`` against the live archive silently picks up
#: whatever point release is current, so two builds under one fingerprint
#: could link against different toolchains. https://snapshot.ubuntu.com serves
#: the archive exactly as it stood at the declared instant.
WINDOWS_APT_SNAPSHOT_URI = "https://snapshot.ubuntu.com/ubuntu/20260825T000000Z"
WINDOWS_APT_SUITES = ("noble", "noble-updates", "noble-security")
WINDOWS_APT_COMPONENTS = ("main", "restricted", "universe", "multiverse")

#: Toolchain versions requested from that snapshot. Kept declared even though
#: the snapshot already fixes the resolved package version, because these are
#: what the Dockerfile actually asks for.
WINDOWS_CLANG_VERSION = "19"
WINDOWS_NSIS_VERSION = "3.10"

#: Externally downloaded builder binaries: exact version plus SHA-256. The
#: hash is verified inside the image build, so a substituted or truncated
#: download fails the build instead of quietly producing different bytes.
WINDOWS_CMAKE_VERSION = "3.30.5"
WINDOWS_CMAKE_SHA256 = (
    "f747d9b23e1a252a8beafb4ed2bc2ddf78cff7f04a8e4de19f4ff88e9b51dc9d"
)
WINDOWS_XWIN_VERSION = "0.6.5"
WINDOWS_XWIN_SHA256 = (
    "9fd53950b064d067f42428a69453b927656cae68dbd7f8d3f86dcb81c80dd22d"
)

#: Microsoft Channel Manifest (AP-SRV-070 W4A-C4, Root Finding L).
#: Pinned to the exact VisualStudio 17.14.39 (August 2026) release manifest
#: captured during W4A-C3.
WINDOWS_XWIN_MANIFEST_URL = "https://aka.ms/vs/17/release/channel"
WINDOWS_XWIN_MANIFEST_CACHE_NAME = "manifest_17.json"
WINDOWS_XWIN_MANIFEST_BYTES = 91833
WINDOWS_XWIN_MANIFEST_SHA256 = (
    "4c81e902fb7fe2acea779b828e6dc548fe0bbb693df50eda0224263c16686bdd"
)

#: Microsoft Package Manifest (.vsman) (AP-SRV-070 W4A-C4, Root Finding L/M).
#: Referenced by the Channel Manifest above. xwin 0.6.5 downloads this with
#: checksum=None; VoiceSTT explicitly verifies the actual file bytes against
#: WINDOWS_XWIN_PACKAGE_MANIFEST_SHA256 before xwin reads it.
WINDOWS_XWIN_PACKAGE_MANIFEST_URL = (
    "https://download.visualstudio.microsoft.com/download/pr/"
    "fa619120-9c0e-47e6-bfe0-3ee96fb671b2/"
    "bd98dd01efa4195cb1c11030da63b9e4a3bcec7bc406799a9db80339d6dabd79/"
    "VisualStudio.vsman"
)
WINDOWS_XWIN_PACKAGE_MANIFEST_CACHE_KEY = (
    "bd98dd01efa4195cb1c11030da63b9e4a3bcec7bc406799a9db80339d6dabd79"
)
WINDOWS_XWIN_PACKAGE_MANIFEST_CACHE_NAME = (
    "pkg_manifest_"
    + WINDOWS_XWIN_PACKAGE_MANIFEST_CACHE_KEY
    + ".vsman"
)
WINDOWS_XWIN_PACKAGE_MANIFEST_BYTES = 17955171
WINDOWS_XWIN_PACKAGE_MANIFEST_SHA256 = (
    "3891c3018a07338b3880cbb28088bb22ef7762eb9206523655b2e3972b9d527e"
)

#: Pinned Windows SDK and MSVC CRT versions (AP-SRV-070 W4A-C4, Root Finding L).
WINDOWS_XWIN_SDK_VERSION = "10.0.26100"
WINDOWS_XWIN_CRT_VERSION = "14.44.17.14"

#: The Windows CPython headers/import library the extension is compiled
#: against. Must stay on the same minor version as the image's Linux python3
#: (pybind11 enforces that), which the pinned base image fixes at 3.12.
WINDOWS_PYTHON_TARGET_VERSION = "3.12.7"
WINDOWS_PYTHON_TAG = "312"
WINDOWS_PYTHON_NUPKG_SHA256 = (
    "149dd298e0b7a82250ca019471770fff079874088a4e8501ca20922d7df3a6ac"
)

#: Microsoft's VC++ redistributable. Upstream fetched it through the rolling
#: ``aka.ms/vs/17/release`` alias, which resolves to a different build over
#: time; this is the immutable versioned URL that alias currently resolves to.
WINDOWS_VC_REDIST_URL = (
    "https://download.visualstudio.microsoft.com/download/pr/"
    "9d270333-8b7b-4f96-9458-6fcdb2ec0b25/"
    "CC0FF0EB1DC3F5188AE6300FAEF32BF5BEEBA4BDD6E8E445A9184072096B713B/"
    "VC_redist.x64.exe"
)
WINDOWS_VC_REDIST_SHA256 = (
    "cc0ff0eb1dc3f5188ae6300faef32bf5beeba4bdd6e8e445a9184072096b713b"
)

#: Windows-native OpenSSL - the single most important pin here. sherpa-onnx
#: links it unconditionally when ``SHERPA_ONNX_ENABLE_WEBSOCKET=ON``, and both
#: upstream and VoiceSTT's own earlier patch downloaded "the first version
#: slproweb still serves", which is not a build input at all but a race with a
#: third party's retention policy. conda-forge is used instead because its
#: published packages are immutable and content-addressed: this exact file
#: either is byte-identical or is gone, and "gone" must fail the build.
WINDOWS_OPENSSL_VERSION = "3.6.4"
WINDOWS_OPENSSL_CONDA_BUILD = "hf411b9b_0"
WINDOWS_OPENSSL_SHA256 = (
    "9dddb559ba49744d5d94092d8d13cb0567f5c3b3f439f3acf28433d1f4256acc"
)

#: openfst is fetched at container *run* time (in_windows_container.sh) and is
#: compiled into the produced binary, so it is just as build-effective as the
#: image-time downloads and gets the same treatment.
WINDOWS_OPENFST_TAG = "sherpa-onnx-2024-06-19"
WINDOWS_OPENFST_SHA256 = (
    "5c98e82cc509c5618502dde4860b8ea04d843850ed57e6d6b590b644b268853d"
)

#: Python packaging tools installed into the builder image. Pinned exactly
#: because they decide how the wheel is produced, tagged and repaired.
#: ``wheel`` is held below 0.46 deliberately: upstream's
#: ``cmake/cmake_extension.py`` imports ``wheel.bdist_wheel``, which 0.46
#: removed, and silently falls back to ``bdist_wheel = None`` - which changes
#: how the produced wheel is tagged.
WINDOWS_PACKAGING_TOOLS = (
    "setuptools==75.8.2",
    "wheel==0.45.1",
    "delvewheel==1.10.1",
    "pefile==2024.8.26",
)


def windows_cmake_url():
    """The pinned CMake release tarball URL."""
    return (
        "https://github.com/Kitware/CMake/releases/download/"
        "v{0}/cmake-{0}-linux-x86_64.tar.gz".format(WINDOWS_CMAKE_VERSION)
    )


def windows_xwin_url():
    """The pinned xwin release tarball URL."""
    return (
        "https://github.com/Jake-Shadle/xwin/releases/download/"
        "{0}/xwin-{0}-x86_64-unknown-linux-musl.tar.gz".format(WINDOWS_XWIN_VERSION)
    )


def windows_python_nupkg_url():
    """The pinned Windows CPython NuGet package URL."""
    return "https://www.nuget.org/api/v2/package/python/{0}".format(
        WINDOWS_PYTHON_TARGET_VERSION
    )


def windows_openssl_filename():
    """The pinned conda-forge OpenSSL package filename."""
    return "openssl-{0}-{1}.conda".format(
        WINDOWS_OPENSSL_VERSION, WINDOWS_OPENSSL_CONDA_BUILD
    )


def windows_openssl_url():
    """The pinned, immutable conda-forge OpenSSL package URL."""
    return "https://conda.anaconda.org/conda-forge/win-64/{0}".format(
        windows_openssl_filename()
    )


def windows_openfst_url():
    """The pinned openfst source archive URL."""
    return (
        "https://github.com/csukuangfj/openfst/archive/refs/tags/"
        "{0}.tar.gz".format(WINDOWS_OPENFST_TAG)
    )


def windows_toolchain_declaration():
    """The complete, immutable Windows builder toolchain declaration.

    Pure data assembled from the constants above: no probing, no network, no
    Docker. This is what the Windows fingerprint records as its toolchain
    authority, so changing any pinned input above moves the fingerprint and a
    previously stored artifact stops matching - which is exactly the property
    Root Finding J found missing.
    """
    return {
        "baseImage": WINDOWS_BASE_IMAGE,
        "baseImageDigest": WINDOWS_BASE_IMAGE_DIGEST,
        "aptSnapshot": WINDOWS_APT_SNAPSHOT_URI,
        "aptSuites": list(WINDOWS_APT_SUITES),
        "aptComponents": list(WINDOWS_APT_COMPONENTS),
        "clangVersion": WINDOWS_CLANG_VERSION,
        "nsisVersion": WINDOWS_NSIS_VERSION,
        "cmake": {
            "version": WINDOWS_CMAKE_VERSION,
            "url": windows_cmake_url(),
            "sha256": WINDOWS_CMAKE_SHA256,
        },
        "xwin": {
            "version": WINDOWS_XWIN_VERSION,
            "url": windows_xwin_url(),
            "sha256": WINDOWS_XWIN_SHA256,
            "channelManifest": {
                "url": WINDOWS_XWIN_MANIFEST_URL,
                "cacheName": WINDOWS_XWIN_MANIFEST_CACHE_NAME,
                "bytes": WINDOWS_XWIN_MANIFEST_BYTES,
                "sha256": WINDOWS_XWIN_MANIFEST_SHA256,
            },
            "packageManifest": {
                "url": WINDOWS_XWIN_PACKAGE_MANIFEST_URL,
                "cacheKey": WINDOWS_XWIN_PACKAGE_MANIFEST_CACHE_KEY,
                "cacheName": WINDOWS_XWIN_PACKAGE_MANIFEST_CACHE_NAME,
                "bytes": WINDOWS_XWIN_PACKAGE_MANIFEST_BYTES,
                "sha256": WINDOWS_XWIN_PACKAGE_MANIFEST_SHA256,
            },
            "sdkVersion": WINDOWS_XWIN_SDK_VERSION,
            "crtVersion": WINDOWS_XWIN_CRT_VERSION,
        },
        "pythonTarget": {
            "version": WINDOWS_PYTHON_TARGET_VERSION,
            "tag": WINDOWS_PYTHON_TAG,
            "url": windows_python_nupkg_url(),
            "sha256": WINDOWS_PYTHON_NUPKG_SHA256,
        },
        "vcRedist": {
            "url": WINDOWS_VC_REDIST_URL,
            "sha256": WINDOWS_VC_REDIST_SHA256,
        },
        "openssl": {
            "version": WINDOWS_OPENSSL_VERSION,
            "condaBuild": WINDOWS_OPENSSL_CONDA_BUILD,
            "url": windows_openssl_url(),
            "sha256": WINDOWS_OPENSSL_SHA256,
        },
        "openfst": {
            "tag": WINDOWS_OPENFST_TAG,
            "url": windows_openfst_url(),
            "sha256": WINDOWS_OPENFST_SHA256,
        },
        "packagingTools": list(WINDOWS_PACKAGING_TOOLS),
    }


#: The build variants this project supports.
VARIANT_FREE = "free"
VARIANT_PRO = "pro"
SUPPORTED_VARIANTS = (VARIANT_FREE, VARIANT_PRO)


def cmake_flags_for(target_platform: str) -> str:
    """The CMake flags that apply to one target platform.

    The Windows wheel is cross-built inside Kroko's own Docker image, whose
    CMake invocation lives in the patched upstream sources rather than in this
    project - so there is no separate VoiceSTT flag string for it.
    """
    if target_platform == "linux":
        return LINUX_CMAKE_FLAGS
    return ""


def normalize_variant(variant: str) -> str:
    """Validates a build variant, refusing anything but ``free``/``pro``."""
    value = str(variant).strip().lower()
    if value not in SUPPORTED_VARIANTS:
        raise ValueError(
            f"unknown Kroko build variant {variant!r}; expected one of {SUPPORTED_VARIANTS}"
        )
    return value


__all__ = [
    "BUILDER_REVISION",
    "WINDOWS_APT_COMPONENTS",
    "WINDOWS_APT_SNAPSHOT_URI",
    "WINDOWS_APT_SUITES",
    "WINDOWS_BASE_IMAGE",
    "WINDOWS_BASE_IMAGE_DIGEST",
    "WINDOWS_CLANG_VERSION",
    "WINDOWS_CMAKE_SHA256",
    "WINDOWS_CMAKE_VERSION",
    "WINDOWS_NSIS_VERSION",
    "WINDOWS_OPENFST_SHA256",
    "WINDOWS_OPENFST_TAG",
    "WINDOWS_OPENSSL_CONDA_BUILD",
    "WINDOWS_OPENSSL_SHA256",
    "WINDOWS_OPENSSL_VERSION",
    "WINDOWS_PACKAGING_TOOLS",
    "WINDOWS_PYTHON_NUPKG_SHA256",
    "WINDOWS_PYTHON_TAG",
    "WINDOWS_PYTHON_TARGET_VERSION",
    "WINDOWS_VC_REDIST_SHA256",
    "WINDOWS_VC_REDIST_URL",
    "WINDOWS_XWIN_CRT_VERSION",
    "WINDOWS_XWIN_MANIFEST_BYTES",
    "WINDOWS_XWIN_MANIFEST_CACHE_NAME",
    "WINDOWS_XWIN_MANIFEST_SHA256",
    "WINDOWS_XWIN_MANIFEST_URL",
    "WINDOWS_XWIN_PACKAGE_MANIFEST_BYTES",
    "WINDOWS_XWIN_PACKAGE_MANIFEST_CACHE_KEY",
    "WINDOWS_XWIN_PACKAGE_MANIFEST_CACHE_NAME",
    "WINDOWS_XWIN_PACKAGE_MANIFEST_SHA256",
    "WINDOWS_XWIN_PACKAGE_MANIFEST_URL",
    "WINDOWS_XWIN_SDK_VERSION",
    "WINDOWS_XWIN_SHA256",
    "WINDOWS_XWIN_VERSION",
    "windows_cmake_url",
    "windows_openfst_url",
    "windows_openssl_filename",
    "windows_openssl_url",
    "windows_python_nupkg_url",
    "windows_toolchain_declaration",
    "windows_xwin_url",
    "KROKO_CAPABILITY_SWITCH_ENV_NAMES",
    "KROKO_UPSTREAM_BRANCH_HINT",
    "KROKO_UPSTREAM_REPO",
    "KROKO_UPSTREAM_REVISION",
    "LINUX_CMAKE_FLAGS",
    "LINUX_MAKE_ARGS",
    "PATCHED_UPSTREAM_SOURCES",
    "PATCH_SET_REVISION",
    "PRO_BUILD_ENV_NAME",
    "PRO_BUILD_ENV_OFF_VALUE",
    "PRO_BUILD_ENV_VALUE",
    "SUPPORTED_VARIANTS",
    "VARIANT_FREE",
    "VARIANT_PRO",
    "cmake_flags_for",
    "normalize_variant",
]
