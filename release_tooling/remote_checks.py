"""Read-only remote-artifact identity checks (AP-SRV-070 W5, section 8).

Every function here is read-only: it never uploads, pushes, tags, or
authenticates with a secret. Each accepts an injectable fetch/runner
callable so the conflict-detection logic is fully unit-tested without ever
making a real network call ("Do not use real public publishing as a test",
section 17). The default implementations do make a real, unauthenticated,
read-only call - they are what a real preflight/publish run would use - but
nothing in this repository's test suite exercises those defaults.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence

from .errors import ConflictError, VerificationUnavailableError

ABSENT = "ABSENT"
MATCH = "MATCH"

PyPIFetcher = Callable[[str], Optional[dict]]


def default_pypi_fetcher(url: str) -> Optional[dict]:
    """A real, unauthenticated ``GET`` against the public PyPI JSON API."""
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise


def check_pypi_release(
    project: str,
    version: str,
    expected_files: Dict[str, str],
    *,
    fetch: PyPIFetcher = default_pypi_fetcher,
) -> str:
    """Read-only PyPI identity check for one already-published version.

    Returns :data:`ABSENT` if ``project``/``version`` does not exist on PyPI
    yet (safe to publish), or :data:`MATCH` if every file in
    ``expected_files`` (``{filename: sha256}``) is already there with an
    identical hash (safe to resume/skip). Any other outcome - a missing
    expected file, or a hash mismatch - is a hard :class:`ConflictError`:
    PyPI releases are immutable, so a conflicting existing release can never
    be resolved by re-uploading.
    """
    url = f"https://pypi.org/pypi/{project}/{version}/json"
    payload = fetch(url)
    if payload is None:
        return ABSENT

    remote_files: Dict[str, str] = {}
    for release_file in payload.get("releases", {}).get(version, []):
        digests = release_file.get("digests") or {}
        remote_files[release_file.get("filename", "")] = digests.get("sha256", "")

    problems: List[str] = []
    for filename, expected_sha256 in expected_files.items():
        remote_sha256 = remote_files.get(filename)
        if remote_sha256 is None:
            problems.append(f"expected file {filename!r} is not present in the existing PyPI release")
        elif remote_sha256 != expected_sha256:
            problems.append(f"{filename!r} sha256 mismatch: remote {remote_sha256} != expected {expected_sha256}")
    if problems:
        raise ConflictError(
            f"PyPI already has {project} {version}, but it conflicts with the qualified release: "
            + "; ".join(problems)
        )
    return MATCH


@dataclass(frozen=True)
class CommandResult:
    args: List[str]
    returncode: int
    stdout: str
    stderr: str


RegistryRunner = Callable[[Sequence[str]], CommandResult]


def check_registry_image(
    image_ref: str,
    expected_image_id: str,
    *,
    runner: RegistryRunner,
) -> str:
    """Read-only registry identity check for one immutable version tag.

    ``image_ref`` is a full ``repo/name:tag`` reference (GHCR or Docker
    Hub). Uses ``docker manifest inspect``, which does not require a local
    pull and does not push/tag/mutate anything. Returns :data:`ABSENT` if
    the tag does not exist remotely yet, :data:`MATCH` if the remote
    manifest digest/config already matches ``expected_image_id``, and raises
    :class:`ConflictError` on any other existing-but-different manifest -
    the release must never silently overwrite a conflicting immutable
    version tag.
    """
    result = runner(["docker", "manifest", "inspect", image_ref])
    if result.returncode != 0:
        stderr = (result.stderr or "").lower()
        # Deliberately narrow and specific to real Docker/registry "this tag
        # does not exist" wording - a generic "not found"/"404" would also
        # match "docker: command not found" (the tool itself missing) and
        # wrongly report that as a safe-to-publish absence.
        absent_markers = ("no such manifest", "manifest unknown")
        if any(marker in stderr for marker in absent_markers):
            return ABSENT
        raise VerificationUnavailableError(
            f"could not check registry state for {image_ref!r} (exit {result.returncode}): {result.stderr.strip()}"
        )
    try:
        payload = json.loads(result.stdout)
    except ValueError as exc:
        raise ConflictError(f"registry returned a non-JSON manifest for {image_ref!r}") from exc

    remote_identity = (
        payload.get("config", {}).get("digest")
        or payload.get("digest")
        or payload.get("Id")
    )
    if not remote_identity:
        raise ConflictError(f"registry manifest for {image_ref!r} did not include a usable identity field")
    if remote_identity != expected_image_id:
        raise ConflictError(
            f"{image_ref!r} already exists remotely with identity {remote_identity!r}, "
            f"expected {expected_image_id!r}"
        )
    return MATCH


__all__ = [
    "ABSENT",
    "MATCH",
    "default_pypi_fetcher",
    "check_pypi_release",
    "CommandResult",
    "check_registry_image",
]
