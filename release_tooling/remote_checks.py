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
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Sequence

from .errors import ConflictError, VerificationUnavailableError
from .redaction import redact_text

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


def inspect_pypi_release(
    project: str,
    version: str,
    expected_files: Dict[str, str],
    *,
    fetch: PyPIFetcher = default_pypi_fetcher,
) -> Dict[str, Any]:
    """Inspects a PyPI release, categorizing files into MATCH, ABSENT, or CONFLICT.

    Raises :class:`VerificationUnavailableError` if the PyPI endpoint cannot be reached.
    Raises :class:`ConflictError` if any conflicting hash or unexpected file is found.
    """
    url = f"https://pypi.org/pypi/{project}/{version}/json"
    try:
        payload = fetch(url)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            payload = None
        else:
            raise VerificationUnavailableError(
                f"could not verify PyPI state for {project} {version}: HTTP {exc.code}"
            ) from exc
    except Exception as exc:
        raise VerificationUnavailableError(
            f"could not verify PyPI state for {project} {version}: {redact_text(str(exc))}"
        ) from exc

    if payload is None:
        return {
            "status": ABSENT,
            "project": project,
            "version": version,
            "matched": [],
            "absent": list(expected_files.keys()),
            "conflicts": [],
        }

    # B5: The official release-specific PyPI endpoint (https://pypi.org/pypi/<project>/<version>/json)
    # does NOT return a 'releases' dict; its files for the exact release are returned in
    # the top-level 'urls' list.
    if not isinstance(payload, dict) or "urls" not in payload or not isinstance(payload["urls"], list):
        raise VerificationUnavailableError(
            f"PyPI returned malformed release metadata for {project} {version}: "
            f"missing or invalid 'urls' list (expected according to official PyPI release API specification)"
        )

    remote_files: Dict[str, str] = {}
    for release_file in payload["urls"]:
        if not isinstance(release_file, dict):
            raise VerificationUnavailableError(
                f"PyPI returned malformed file entry for {project} {version}: {release_file!r}"
            )
        filename = release_file.get("filename")
        digests = release_file.get("digests") or {}
        sha256 = digests.get("sha256") if isinstance(digests, dict) else None
        if not filename or not sha256:
            raise VerificationUnavailableError(
                f"PyPI returned file entry with missing filename or sha256 for {project} {version}: {release_file!r}"
            )
        remote_files[filename] = str(sha256).lower()

    # Check for unexpected files in the existing PyPI release
    unexpected = [f for f in remote_files if f not in expected_files]
    problems: List[str] = []
    if unexpected:
        problems.append(
            f"PyPI release contains unexpected file(s) not in candidate manifest: {unexpected}"
        )

    matched: List[str] = []
    absent: List[str] = []
    conflicts: List[str] = list(unexpected)

    for filename, expected_sha256 in expected_files.items():
        if filename not in remote_files:
            absent.append(filename)
        else:
            remote_sha256 = remote_files[filename]
            if remote_sha256.lower() == str(expected_sha256).lower():
                matched.append(filename)
            else:
                conflicts.append(filename)
                problems.append(
                    f"{filename!r} sha256 mismatch: remote {remote_sha256} != expected {expected_sha256}"
                )

    if problems:
        raise ConflictError(
            f"PyPI already has {project} {version}, but it conflicts with the qualified release: "
            + "; ".join(problems)
        )

    if not absent:
        status = MATCH
    elif not matched:
        status = ABSENT
    else:
        status = "PARTIAL"

    return {
        "status": status,
        "project": project,
        "version": version,
        "matched": matched,
        "absent": absent,
        "conflicts": conflicts,
    }


def check_pypi_release(
    project: str,
    version: str,
    expected_files: Dict[str, str],
    *,
    fetch: PyPIFetcher = default_pypi_fetcher,
) -> str:
    """Read-only PyPI identity check for one already-published version.

    Returns :data:`MATCH` if every file in ``expected_files`` is already there
    with identical hash.
    Returns :data:`ABSENT` if the version does not exist or has not published
    all expected files yet.
    Raises :class:`ConflictError` on hash mismatch or unexpected existing files.
    """
    inspection = inspect_pypi_release(project, version, expected_files, fetch=fetch)
    return MATCH if inspection["status"] == MATCH else ABSENT


def precheck_pypi(
    manifest: Dict[str, Any],
    *,
    fetch: PyPIFetcher = default_pypi_fetcher,
) -> Dict[str, Dict[str, Any]]:
    """Runs PyPI precheck across all distributions and all required wheels.

    Fails closed (raises :class:`ConflictError` or :class:`VerificationUnavailableError`)
    if any conflict or unverifiable state is detected.
    """
    version = manifest["productVersion"]
    report: Dict[str, Dict[str, Any]] = {}
    for variant in ("free", "pro"):
        project = manifest["distributions"][variant]["name"]
        expected = {
            wheel["filename"]: wheel["sha256"]
            for wheel in manifest["distributions"][variant]["wheels"]
        }
        report[variant] = inspect_pypi_release(project, version, expected, fetch=fetch)
    return report


@dataclass(frozen=True)
class CommandResult:
    args: List[str]
    returncode: int
    stdout: str
    stderr: str


RegistryRunner = Callable[[Sequence[str]], CommandResult]


#: Registry wording that genuinely means "this reference does not exist".
#: Deliberately narrow: a generic "not found"/"404" would also match
#: "docker: command not found" (the tool itself missing) and would wrongly
#: report a missing *tool* as a safe-to-publish *absence*.
_ABSENT_MARKERS = (
    "no such manifest",
    "manifest unknown",
    "manifest_unknown",
    "name unknown",
    ": not found",
)

_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def remote_manifest_digest(
    image_ref: str,
    *,
    runner: RegistryRunner,
) -> Optional[str]:
    """The remote OCI manifest digest of ``image_ref``, or ``None`` if absent.

    Read-only: ``docker buildx imagetools inspect`` resolves a reference
    through the registry API without pulling, pushing or mutating anything.

    AP-SRV-070 W5-R04 corrected *what* is compared here. The previous
    implementation compared the remote manifest digest against the **local**
    ``docker inspect`` image ``Id``. Those are two different things - the
    config-blob digest of a local image versus the digest of the remote
    manifest - so they could never legitimately be equal, and every real
    registry verification would have raised a spurious ``CONFLICT``. The
    manifest digest is now compared against the manifest digest recorded for
    the qualified candidate, which is also exactly the identity that
    ``docker buildx imagetools create`` promotes between registries.
    """
    result = runner(
        [
            "docker", "buildx", "imagetools", "inspect", image_ref,
            "--format", "{{.Manifest.Digest}}",
        ]
    )
    if result.returncode != 0:
        stderr = (result.stderr or "").lower()
        if any(marker in stderr for marker in _ABSENT_MARKERS):
            return None
        # AP-SRV-070 W5-R04 (gate W5R4-G49): registry stderr can quote a
        # credential back at us (a rejected `docker login`/pull does exactly
        # that). This message becomes an exception, a workflow log line and
        # sometimes an evidence file, so it is redacted at the boundary rather
        # than trusting every caller to remember.
        raise VerificationUnavailableError(
            f"could not check registry state for {image_ref!r} "
            f"(exit {result.returncode}): {redact_text(result.stderr.strip())}"
        )
    digest = (result.stdout or "").strip()
    if not _DIGEST_RE.match(digest):
        raise VerificationUnavailableError(
            f"registry returned an unusable manifest digest for {image_ref!r}: {digest!r}"
        )
    return digest


def check_registry_image(
    image_ref: str,
    expected_digest: str,
    *,
    runner: RegistryRunner,
) -> str:
    """Read-only registry identity check for one immutable version tag.

    ``image_ref`` is a full ``repo/name:tag`` reference (GHCR or Docker Hub).
    Returns :data:`ABSENT` if the tag does not exist remotely yet,
    :data:`MATCH` if the remote manifest digest already equals
    ``expected_digest``, and raises :class:`ConflictError` on any other
    existing-but-different manifest - the release must never silently
    overwrite a conflicting immutable version tag.
    """
    if not _DIGEST_RE.match(str(expected_digest or "")):
        raise VerificationUnavailableError(
            f"cannot verify {image_ref!r}: the candidate records no usable "
            f"manifest digest ({expected_digest!r})"
        )
    remote_digest = remote_manifest_digest(image_ref, runner=runner)
    if remote_digest is None:
        return ABSENT
    if remote_digest != expected_digest:
        raise ConflictError(
            f"{image_ref!r} already exists remotely with manifest digest "
            f"{remote_digest!r}, expected {expected_digest!r}"
        )
    return MATCH


def check_registry_alias(
    alias_ref: str,
    expected_digest: str,
    *,
    runner: RegistryRunner,
) -> str:
    """Read-only check for one *movable* alias tag.

    An alias differs from an exact version tag in exactly one way: an alias
    that currently points somewhere else is **not** a conflict, because
    moving it is the entire point of an alias. It is simply not updated yet,
    which is :data:`ABSENT` from this step's perspective. An alias that
    already points at the expected digest is :data:`MATCH`, which is what
    makes re-running the alias step idempotent on a resume.
    """
    if not _DIGEST_RE.match(str(expected_digest or "")):
        raise VerificationUnavailableError(
            f"cannot verify alias {alias_ref!r}: no usable expected digest "
            f"({expected_digest!r})"
        )
    remote_digest = remote_manifest_digest(alias_ref, runner=runner)
    if remote_digest is None:
        return ABSENT
    return MATCH if remote_digest == expected_digest else ABSENT


__all__ = [
    "ABSENT",
    "MATCH",
    "default_pypi_fetcher",
    "check_pypi_release",
    "CommandResult",
    "remote_manifest_digest",
    "check_registry_image",
    "check_registry_alias",
]
