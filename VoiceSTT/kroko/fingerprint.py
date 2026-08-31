"""The canonical Kroko build fingerprint (AP-SRV-070 W4A).

The fingerprint answers exactly one question: *may an already-built Kroko
artifact be reused, or does this configuration need its own native build?*

It is computed from the declared inputs in :mod:`VoiceSTT.kroko.buildinputs`
plus the target description (variant, platform, architecture, Python ABI,
toolchain identity). Nothing is auto-discovered from the working tree, so an
edit to the FastAPI server, the wake-word code, the docs or the product
``VERSION`` cannot change it - that decoupling is the whole point of W4A.

The serialization is deterministic (sorted keys, no insignificant whitespace)
so the same inputs always produce the same hash, on any machine and in any
process. The full input document stays human-readable and is stored next to
every artifact; the short hex id derived from it is what names directories and
cache keys.
"""

from __future__ import annotations

import hashlib
import json
import platform
import sys
from typing import Any, Dict, Mapping, Optional

from . import buildinputs

#: Version of the fingerprint document itself. Bumping it deliberately
#: invalidates every previously stored artifact, which is the correct behavior
#: when the meaning of the inputs changes.
FINGERPRINT_SCHEMA_VERSION = 1

#: Length of the short hex id used for directory and cache-key naming. 16 hex
#: characters (64 bits) is far beyond collision risk for a per-machine artifact
#: store while staying readable in a path.
FINGERPRINT_ID_LENGTH = 16


def canonical_json(document: Mapping[str, Any]) -> str:
    """Deterministic serialization of a fingerprint document."""
    return json.dumps(
        document,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def detect_target_platform() -> str:
    """The build target platform of the running interpreter."""
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform.startswith("linux"):
        return "linux"
    if sys.platform == "darwin":
        return "darwin"
    return sys.platform


def detect_architecture() -> str:
    """The normalized CPU architecture of the running interpreter."""
    machine = platform.machine().lower()
    if machine in ("amd64", "x86_64"):
        return "amd64"
    if machine in ("arm64", "aarch64"):
        return "arm64"
    return machine or "unknown"


def detect_python_tag() -> str:
    """The CPython implementation/version tag, e.g. ``cp312``."""
    return "cp{0}{1}".format(sys.version_info.major, sys.version_info.minor)


def toolchain_identity(target_platform: str) -> Dict[str, Any]:
    """The build-effective toolchain identity for one target platform.

    Windows wheels are cross-built inside Kroko's own Docker image, so the
    compiler, CMake and OpenSSL that actually produce the binary are fixed by
    the pinned upstream revision plus VoiceSTT's patch set - not by whatever
    happens to be installed on the host. Recording host tool versions there
    would make the fingerprint differ between machines that produce byte-wise
    equivalent wheels, so the Windows identity is deliberately host-independent.

    A Linux build compiles natively against host tools, so the host toolchain
    genuinely is a build input. Callers pass concrete versions in; this
    function only declares the *shape*, so nothing here silently depends on
    what is installed while a test runs.
    """
    if target_platform == "windows":
        return {
            "kind": "kroko-docker-windows-crossbuild",
            "definedBy": "upstream-revision+patch-set",
        }
    return {"kind": "host-native"}


def build_fingerprint_document(
    *,
    variant: str,
    target_platform: Optional[str] = None,
    architecture: Optional[str] = None,
    python_tag: Optional[str] = None,
    abi_tag: Optional[str] = None,
    toolchain: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """The full, human-readable fingerprint input document.

    Every argument that is omitted is detected from the running interpreter,
    which is what a normal local build wants. CI and cross-builds pass explicit
    values so the fingerprint describes the *target*, not the builder host.
    """
    normalized_variant = buildinputs.normalize_variant(variant)
    resolved_platform = target_platform or detect_target_platform()
    resolved_python_tag = python_tag or detect_python_tag()
    resolved_toolchain = (
        dict(toolchain) if toolchain is not None
        else toolchain_identity(resolved_platform)
    )

    return {
        "schemaVersion": FINGERPRINT_SCHEMA_VERSION,
        "upstream": {
            "repo": buildinputs.KROKO_UPSTREAM_REPO,
            "revision": buildinputs.KROKO_UPSTREAM_REVISION,
        },
        "variant": normalized_variant,
        "target": {
            "platform": resolved_platform,
            "architecture": architecture or detect_architecture(),
        },
        "python": {
            "tag": resolved_python_tag,
            "abi": abi_tag or resolved_python_tag,
        },
        "build": {
            "cmakeFlags": buildinputs.cmake_flags_for(resolved_platform),
            "makeArgs": (
                buildinputs.LINUX_MAKE_ARGS if resolved_platform == "linux" else ""
            ),
            # The Pro switch is a build-time capability flag, never a key.
            "proLicenseEnabled": normalized_variant == buildinputs.VARIANT_PRO,
            # The two declared revisions covering VoiceSTT's own build-effective
            # logic: what we change in the upstream sources, and how we invoke
            # the build. Both are guarded against silent drift by a source-digest
            # test - see VoiceSTT/kroko/buildinputs.py for the update obligation.
            "patchSetRevision": buildinputs.PATCH_SET_REVISION,
            "builderRevision": buildinputs.BUILDER_REVISION,
        },
        "toolchain": resolved_toolchain,
    }


def fingerprint_id(document: Mapping[str, Any]) -> str:
    """The short, stable hex id of one fingerprint document."""
    digest = hashlib.sha256(canonical_json(document).encode("utf-8")).hexdigest()
    return digest[:FINGERPRINT_ID_LENGTH]


def compute_fingerprint(**kwargs: Any) -> Dict[str, Any]:
    """The fingerprint document plus its id, as one machine-readable result.

    This is the entry point W4B/CI use: it is pure computation, touches no
    network and no build tree, and never needs a Kroko checkout.
    """
    document = build_fingerprint_document(**kwargs)
    return {
        "fingerprint": fingerprint_id(document),
        "inputs": document,
        "canonical": canonical_json(document),
    }


__all__ = [
    "FINGERPRINT_ID_LENGTH",
    "FINGERPRINT_SCHEMA_VERSION",
    "build_fingerprint_document",
    "canonical_json",
    "compute_fingerprint",
    "detect_architecture",
    "detect_python_tag",
    "detect_target_platform",
    "fingerprint_id",
    "toolchain_identity",
]
