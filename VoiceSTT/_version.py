"""The single product version authority (AP-SRV-070).

Before this module, ``setup.py`` carried its own ``current_version`` string
and the protocol-v2 wire identity (``api_fastapi_server/protocol_v2/identity.py``)
carried a second, independently hardcoded ``SERVER_VERSION``. The two drifted
out of sync (W0 finding: ``setup.py`` said ``1.0.2`` while the already
established v2 server identity was ``2.0.0``). This module is now the only
place that decides the product version; every other consumer - package
metadata, the running server, the v2 handshake - reads through it.

Installed wheels and extracted sdists first use their validated immutable
build resource. It preserves original SemVer separately from normalized
Python package metadata; conflicting nonempty environment overrides fail.

Source checkouts ignore stale generated resources and use the explicit
``VOICESTT_BUILD_VERSION`` override, otherwise their root ``VERSION``.
Older installs without a resource use a validated override or the metadata
of the distribution that actually owns this import (legacy, Free or Pro).
An old normalized prerelease cannot recover lost original SemVer spelling.

A value that reaches this module - the override or the ``VERSION`` file
content - is always validated as SemVer 2.0.0. An invalid value is a hard
error; it is never silently swallowed or replaced by a fallback, so a typo in
the override can never masquerade as a valid release.
"""

from __future__ import annotations

import os
import pathlib
import re
from importlib import metadata as _metadata
from typing import NamedTuple

#: The distribution name registered with packaging tools (``setup.py`` /
#: PyPI), used to look up the installed metadata version.
DISTRIBUTION_NAME = "voicestt"

#: The explicit, validated build/release version override. Empty/unset means
#: "no override" - it never falls back to an invalid value silently, it is
#: simply not consulted.
BUILD_VERSION_ENV = "VOICESTT_BUILD_VERSION"

#: The official SemVer 2.0.0 grammar (see https://semver.org/, "regex"
#: section), verbatim except for named groups.
_SEMVER_RE = re.compile(
    r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+(?P<buildmetadata>[0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)

#: The three release-bump kinds ``release.py`` (W5/W6) will expose as
#: ``python release.py`` / ``--minor`` / ``--major``.
BUMP_PATCH = "patch"
BUMP_MINOR = "minor"
BUMP_MAJOR = "major"
BUMP_KINDS = (BUMP_PATCH, BUMP_MINOR, BUMP_MAJOR)


class SemVerError(ValueError):
    """A version string is not valid SemVer 2.0.0."""


class SemVer(NamedTuple):
    major: int
    minor: int
    patch: int
    prerelease: str
    build: str

    def release_str(self) -> str:
        """The plain ``MAJOR.MINOR.PATCH`` form, without prerelease/build."""
        return f"{self.major}.{self.minor}.{self.patch}"


def parse_semver(value: str) -> SemVer:
    """Parses ``value`` as SemVer 2.0.0, raising :class:`SemVerError` if not."""
    text = str(value).strip()
    match = _SEMVER_RE.match(text)
    if not match:
        raise SemVerError(f"{value!r} is not a valid SemVer 2.0.0 version")
    return SemVer(
        major=int(match.group("major")),
        minor=int(match.group("minor")),
        patch=int(match.group("patch")),
        prerelease=match.group("prerelease") or "",
        build=match.group("buildmetadata") or "",
    )


def is_valid_semver(value: str) -> bool:
    try:
        parse_semver(value)
    except SemVerError:
        return False
    return True


def validate_semver(value: str) -> str:
    """Returns ``value`` unchanged if valid; raises :class:`SemVerError` otherwise."""
    parse_semver(value)
    return str(value).strip()


def bump(version: str, kind: str) -> str:
    """The next plain release version for one bump ``kind``.

    A prerelease/build suffix on the input is accepted (a candidate is still
    a valid version to bump from) but never appears in the output: a release
    bump always produces a clean ``MAJOR.MINOR.PATCH``.

    * ``patch``: patch + 1.
    * ``minor``: minor + 1, patch reset to 0.
    * ``major``: major + 1, minor and patch reset to 0.
    """
    if kind not in BUMP_KINDS:
        raise ValueError(f"unknown bump kind {kind!r}, expected one of {BUMP_KINDS}")
    parsed = parse_semver(version)
    if kind == BUMP_MAJOR:
        return f"{parsed.major + 1}.0.0"
    if kind == BUMP_MINOR:
        return f"{parsed.major}.{parsed.minor + 1}.0"
    return f"{parsed.major}.{parsed.minor}.{parsed.patch + 1}"


def resolve_bump_kind(*, minor: bool = False, major: bool = False) -> str:
    """The bump kind for the future ``release.py`` CLI contract.

    ``--minor`` and ``--major`` are mutually exclusive; neither flag means a
    patch release. This is pure argument resolution - it never touches the
    version itself - so the eventual mutating ``release.py`` (W5/W6) can reuse
    it without re-implementing the exclusivity rule.
    """
    if minor and major:
        raise ValueError("--minor and --major are mutually exclusive")
    if major:
        return BUMP_MAJOR
    if minor:
        return BUMP_MINOR
    return BUMP_PATCH


def _version_file_path() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parent.parent / "VERSION"


def read_version_file() -> str:
    """The source-controlled baseline version, validated as SemVer."""
    path = _version_file_path()
    text = path.read_text(encoding="utf-8").strip()
    return validate_semver(text)


def _build_override() -> str:
    """The override env var, or ``""`` if unset/blank."""
    return os.environ.get(BUILD_VERSION_ENV, "").strip()


def resolve_version() -> str:
    """The one product version this build/runtime reports everywhere.

    Never derived from commit messages or branch names - only the explicit
    override/source ``VERSION``, an immutable resource, or unambiguous
    owning-distribution metadata for older stable installs.
    """
    from ._build_identity import (
        installed_distribution, package_root, validated_build_identity,
    )

    identity = validated_build_identity()
    if identity is not None:
        return identity.productVersion
    override = _build_override()
    if override:
        return validate_semver(override)
    if (package_root() / "setup.py").is_file() and _version_file_path().is_file():
        return read_version_file()
    name, version = installed_distribution()
    if name is None:
        raise _metadata.PackageNotFoundError("no distribution owns the VoiceSTT import")
    # Old normalized prereleases have lost their original SemVer spelling.
    # Reject them explicitly rather than inventing that spelling.
    return validate_semver(version)


__all__ = [
    "BUILD_VERSION_ENV",
    "BUMP_KINDS",
    "BUMP_MAJOR",
    "BUMP_MINOR",
    "BUMP_PATCH",
    "DISTRIBUTION_NAME",
    "SemVer",
    "SemVerError",
    "bump",
    "is_valid_semver",
    "parse_semver",
    "read_version_file",
    "resolve_bump_kind",
    "resolve_version",
    "validate_semver",
]
