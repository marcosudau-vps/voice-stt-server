"""Movable container alias mapping (AP-SRV-070 W5-R04, section 21).

An exact version tag such as ``2.0.0`` is an immutable release identity and is
never repointed. Alongside it a release publishes *movable* aliases that later
compatible releases are allowed to take over:

.. code-block:: text

    2.0.0  ->  2.0, 2, latest
    0.5.3  ->  0.5, latest          (no broad "0")
    1.0.0-rc.1 -> (none)

The ``0.x`` rule is not cosmetic. Under SemVer, ``0.x`` releases make no
compatibility promise across minor versions, so a broad ``0`` alias would claim
a compatibility guarantee the version scheme explicitly withholds. A
pre-release gets no aliases at all for the same reason ``latest`` must never
point at a release candidate.

This module is pure computation over a version string. It performs no registry
call and knows nothing about Docker: the adapters in
``release_tooling.adapters`` decide *when* aliases may move (only after every
exact Free and Pro artifact is verified in both registries) and *how* they are
written; this module only decides *which* alias names a version owns.
"""

from __future__ import annotations

import re
from typing import Dict, List

from .errors import ReleaseError

#: ``major.minor.patch`` with an optional pre-release / build-metadata suffix.
_SEMVER_RE = re.compile(
    r"^(?P<major>0|[1-9]\d*)"
    r"\.(?P<minor>0|[1-9]\d*)"
    r"\.(?P<patch>0|[1-9]\d*)"
    r"(?:-(?P<prerelease>[0-9A-Za-z.-]+))?"
    r"(?:\+(?P<build>[0-9A-Za-z.-]+))?$"
)

#: The alias every stable release owns.
LATEST_ALIAS = "latest"


def parse_version(version: str) -> Dict[str, str]:
    """The SemVer components of ``version``.

    Raises :class:`~release_tooling.errors.ReleaseError` on anything that is
    not a valid SemVer string. Failing closed matters here: guessing alias
    names for an unparseable version could silently repoint ``latest``.
    """
    match = _SEMVER_RE.match(str(version).strip())
    if not match:
        raise ReleaseError(
            f"version {version!r} is not a valid SemVer version; "
            "refusing to derive movable aliases from it"
        )
    parts = match.groupdict()
    return {key: (value or "") for key, value in parts.items()}


def is_prerelease(version: str) -> bool:
    """True if ``version`` carries a SemVer pre-release suffix."""
    return bool(parse_version(version)["prerelease"])


def alias_tags_for(version: str) -> List[str]:
    """The movable alias tags ``version`` owns, most specific first.

    * a pre-release owns none - ``latest`` must never point at an RC;
    * ``0.x.y`` owns ``0.x`` and ``latest``, but never a broad ``0``;
    * ``>=1.0.0`` owns ``major.minor``, ``major`` and ``latest``.
    """
    parts = parse_version(version)
    if parts["prerelease"]:
        return []

    major = parts["major"]
    minor = parts["minor"]
    aliases = [f"{major}.{minor}"]
    if major != "0":
        aliases.append(major)
    aliases.append(LATEST_ALIAS)
    return aliases


def exact_tag_for(version: str) -> str:
    """The immutable exact registry tag for ``version``."""
    parse_version(version)  # validate, fail closed on nonsense
    return str(version).strip()


def git_tag_for(version: str) -> str:
    """The immutable Git tag name for ``version``."""
    return f"v{exact_tag_for(version)}"


__all__ = [
    "LATEST_ALIAS",
    "parse_version",
    "is_prerelease",
    "alias_tags_for",
    "exact_tag_for",
    "git_tag_for",
]
