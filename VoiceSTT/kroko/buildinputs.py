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
PATCH_SET_REVISION = 1

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
BUILDER_REVISION = 3

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
