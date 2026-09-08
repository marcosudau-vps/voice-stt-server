"""Read-only release preflight (AP-SRV-070 W5, section 9).

Preflight never publishes, tags, commits, bumps ``VERSION``, or rewrites
release state as though a publish succeeded - every check here only reads
the filesystem, the local Git metadata, environment variable *presence*,
and (best-effort, tolerant of no network) the public registries.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from . import config, gitinfo, rc_manifest
from .errors import ManifestError
from .state import default_state_path, load_state
from VoiceSTT._version import read_version_file  # noqa: E402

PASS = "PASS"
FAIL = "FAIL"
WARN = "WARN"

#: A drive-letter path (``P:\\...``/``C:/...``) is the concrete shape of the
#: "release depends on Marco's PC" failure mode section 9 forbids.
#: The leading word boundary matters: without it this also matches the ``s:/``
#: inside every ``https://`` URL, which would reject a perfectly portable
#: manifest merely for naming its own upstream repository. A drive letter is a
#: *single* letter, so a word boundary before it is exactly the distinction.
_WINDOWS_ABSOLUTE_PATH_RE = re.compile(r"\b[A-Za-z]:[\\/][^\"\s]*")


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str
    detail: str


@dataclass(frozen=True)
class PreflightReport:
    checks: List[CheckResult]

    @property
    def passed(self) -> bool:
        return all(check.status != FAIL for check in self.checks)

    def to_json_dict(self) -> dict:
        return {
            "passed": self.passed,
            "checks": [
                {"name": c.name, "status": c.status, "detail": c.detail}
                for c in self.checks
            ],
        }


def _check_version(expected_version: str) -> CheckResult:
    try:
        current = read_version_file()
    except Exception as exc:  # noqa: BLE001 - surfaced as a FAIL, not a crash
        return CheckResult("version_matches_expected", FAIL, f"could not read VERSION: {exc}")
    if current != expected_version:
        return CheckResult(
            "version_matches_expected", FAIL,
            f"VERSION={current!r} does not match the requested release version {expected_version!r}",
        )
    return CheckResult("version_matches_expected", PASS, f"VERSION={current}")


def _check_release_notes(repo_root: Path, version: str) -> CheckResult:
    path = repo_root / "RELEASE_NOTES.md"
    if not path.is_file():
        return CheckResult("release_notes_prepared", FAIL, f"{path} does not exist")
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(rf"^##\s+{re.escape(version)}\b", re.MULTILINE)
    if not pattern.search(text):
        return CheckResult(
            "release_notes_prepared", FAIL,
            f"RELEASE_NOTES.md has no dated '## {version}' section yet",
        )
    return CheckResult("release_notes_prepared", PASS, f"RELEASE_NOTES.md has a '## {version}' section")


def _check_git(repo_root: Path, expected_commit: Optional[str], expected_tree: Optional[str]) -> List[CheckResult]:
    results: List[CheckResult] = []
    try:
        identity = gitinfo.resolve_identity(repo_root)
    except gitinfo.GitError as exc:
        return [CheckResult("git_identity", FAIL, str(exc))]

    if identity.dirty:
        results.append(CheckResult("git_clean_tree", FAIL, "working tree is not clean (git status --porcelain is non-empty)"))
    else:
        results.append(CheckResult("git_clean_tree", PASS, "working tree is clean"))

    if expected_commit and identity.commit != expected_commit:
        results.append(CheckResult("git_exact_commit", FAIL, f"HEAD is {identity.commit}, expected {expected_commit}"))
    else:
        results.append(CheckResult("git_exact_commit", PASS, f"HEAD is {identity.commit}"))

    if expected_tree and identity.tree != expected_tree:
        results.append(CheckResult("git_exact_tree", FAIL, f"tree is {identity.tree}, expected {expected_tree}"))
    else:
        results.append(CheckResult("git_exact_tree", PASS, f"tree is {identity.tree}"))

    return results


def _check_tag_absence(repo_root: Path, version: str, expected_commit: Optional[str]) -> CheckResult:
    tag_name = f"v{version}"
    existing_commit = gitinfo.local_tag_commit(repo_root, tag_name)
    if existing_commit is None:
        return CheckResult("git_tag_absent_or_compatible", PASS, f"local tag {tag_name!r} does not exist yet")
    if expected_commit and existing_commit == expected_commit:
        return CheckResult("git_tag_absent_or_compatible", PASS, f"local tag {tag_name!r} already points at the expected commit")
    return CheckResult(
        "git_tag_absent_or_compatible", FAIL,
        f"local tag {tag_name!r} already exists and points at {existing_commit}, "
        f"which is not the expected commit {expected_commit}",
    )


def _check_manifest(manifest_path: Optional[Path]) -> CheckResult:
    if manifest_path is None:
        return CheckResult("rc_manifest_complete", WARN, "no RC manifest path given (expected before a real W6 publish)")
    try:
        rc_manifest.load_rc_manifest(manifest_path)
    except ManifestError as exc:
        return CheckResult("rc_manifest_complete", FAIL, str(exc))
    return CheckResult("rc_manifest_complete", PASS, f"RC manifest at {manifest_path} is complete and valid")


def _check_manifest_version(
    manifest_path: Optional[Path],
    expected_version: str,
) -> CheckResult:
    """Verifies that candidate manifest productVersion equals the expected version (B6)."""
    if manifest_path is None:
        return CheckResult("rc_manifest_version_matches", WARN, "no RC manifest given")
    try:
        manifest = rc_manifest.load_rc_manifest(manifest_path)
    except ManifestError as exc:
        return CheckResult("rc_manifest_version_matches", FAIL, f"unreadable manifest: {exc}")
    product_version = manifest.get("productVersion")
    if product_version != expected_version:
        return CheckResult(
            "rc_manifest_version_matches",
            FAIL,
            f"candidate manifest productVersion {product_version!r} does not match expected {expected_version!r}",
        )
    return CheckResult(
        "rc_manifest_version_matches",
        PASS,
        f"candidate manifest productVersion {product_version!r} matches expected {expected_version!r}",
    )


def _check_tool_availability() -> List[CheckResult]:
    results = []
    # ``twine`` is deliberately no longer in this list: the GitHub release path
    # uses PyPI Trusted Publishing (OIDC) and holds no token, so requiring a
    # local uploader would report a missing tool the release does not use.
    for tool in ("git", "docker"):
        found = shutil.which(tool) is not None
        results.append(CheckResult(f"tool_available_{tool}", PASS if found else WARN, f"{tool} on PATH: {found}"))
    return results


def _check_registry_identifiers() -> List[CheckResult]:
    """Where the release will publish, and whether that is fully determined.

    AP-SRV-070 W5-R04 removed one of the two mandatory operator variables. The
    GHCR root is *derived* (``ghcr.io/<owner>``) because a GHCR package always
    lives under the repository owner and the owner is known - that is a fact,
    not a guess. The Docker Hub namespace genuinely cannot be derived from
    anything the repository knows, so it stays operator-configured and this
    check fails closed when it is missing instead of assuming one.
    """
    ghcr = config.ghcr_repo_root()
    dockerhub = config.dockerhub_repo_root()
    results = [
        CheckResult(
            "ghcr_repo_derived",
            PASS if ghcr else FAIL,
            f"ghcr root = {ghcr or '<unresolved>'}",
        ),
        CheckResult(
            "dockerhub_repo_configured",
            PASS if dockerhub else FAIL,
            f"{config.DOCKERHUB_NAMESPACE_ENV}="
            f"{dockerhub or '<unset>'} (required: it cannot be derived)",
        ),
    ]
    for variant in sorted(config.DISTRIBUTION_NAMES):
        results.append(
            CheckResult(
                f"pypi_project_{variant}",
                PASS,
                f"pypi project ({variant}) = {config.distribution_name_for(variant)}",
            )
        )
        results.append(
            CheckResult(
                f"image_name_{variant}",
                PASS,
                f"image ({variant}) = {config.image_name_for(variant)}",
            )
        )
    return results


def _check_credentials() -> List[CheckResult]:
    """Boolean-only credential readiness. No secret value is ever read.

    These are WARN rather than FAIL because preflight also runs in contexts
    that legitimately hold no credentials at all - a dry-run, or the
    qualification workflow, which must be able to prove it *cannot* publish.
    The adapters themselves fail closed when a real write is attempted
    without the credential the underlying tool needs.
    """
    presence = config.credential_presence()
    return [
        CheckResult(f"credential_{name}", PASS if present else WARN, f"{name}={present}")
        for name, present in sorted(presence.items())
    ]


def _check_no_local_path_dependency(rc_manifest_path: Optional[Path]) -> CheckResult:
    """Refuses a candidate manifest that carries an operator-local path.

    AP-SRV-070 W5-R04, section 9: release authority must not depend on a
    specific machine. A manifest that recorded, say, a ``P:\\...`` wheel path
    would make the candidate unpublishable from anywhere else, so it is
    rejected here rather than at the moment publication needs the file.
    """
    if rc_manifest_path is None:
        return CheckResult("no_local_path_dependency", WARN, "no RC manifest given")
    try:
        text = Path(rc_manifest_path).read_text(encoding="utf-8")
    except OSError as exc:
        return CheckResult("no_local_path_dependency", FAIL, f"unreadable manifest: {exc}")
    offenders = _WINDOWS_ABSOLUTE_PATH_RE.findall(text)
    if offenders:
        return CheckResult(
            "no_local_path_dependency", FAIL,
            f"RC manifest contains operator-local absolute path(s): {sorted(set(offenders))[:3]}",
        )
    return CheckResult(
        "no_local_path_dependency", PASS, "RC manifest carries no absolute local path"
    )


def _check_no_state_conflict(repo_root: Path, version: str) -> CheckResult:
    state_path = default_state_path(repo_root, version)
    try:
        state = load_state(state_path)
    except Exception as exc:  # noqa: BLE001
        return CheckResult("no_state_conflict", FAIL, f"existing release state at {state_path} is unusable: {exc}")
    if state is None:
        return CheckResult("no_state_conflict", PASS, f"no existing release state at {state_path} (fresh release)")
    return CheckResult("no_state_conflict", PASS, f"existing release state at {state_path} is state={state.state}, resumable")


def _check_qualification(
    manifest_path: Optional[Path],
    require_qualified: bool = False,
) -> CheckResult:
    if manifest_path is None:
        return CheckResult("candidate_qualification", WARN, "no RC manifest given")
    try:
        manifest = rc_manifest.load_rc_manifest(manifest_path)
    except ManifestError as exc:
        return CheckResult("candidate_qualification", FAIL, f"unreadable manifest: {exc}")

    readiness = manifest.get("releaseReadiness")
    evidence_ref = (manifest.get("qualification") or {}).get("evidenceRef")

    if readiness == rc_manifest.READINESS_QUALIFIED:
        if not evidence_ref or str(evidence_ref).strip() == "" or evidence_ref == "none":
            return CheckResult(
                "candidate_qualification",
                FAIL,
                "manifest is marked QUALIFIED but lacks valid qualification.evidenceRef",
            )
        return CheckResult(
            "candidate_qualification",
            PASS,
            f"candidate is QUALIFIED (evidenceRef: {evidence_ref})",
        )

    if require_qualified:
        return CheckResult(
            "candidate_qualification",
            FAIL,
            f"candidate releaseReadiness={readiness!r} is not QUALIFIED (cannot publish)",
        )
    return CheckResult(
        "candidate_qualification",
        WARN,
        f"candidate releaseReadiness={readiness!r} is not QUALIFIED",
    )


def run_preflight(
    *,
    repo_root: Path,
    expected_version: str,
    expected_commit: Optional[str] = None,
    expected_tree: Optional[str] = None,
    rc_manifest_path: Optional[Path] = None,
    require_qualified: bool = False,
) -> PreflightReport:
    """Runs every read-only preflight check and returns the aggregate report.

    Never mutates ``repo_root``, never touches the network by itself (only
    ``docker``/``git`` presence and local metadata are read), and never
    prints or stores a secret value - only boolean presence flags.
    """
    checks: List[CheckResult] = [_check_version(expected_version)]
    checks.append(_check_release_notes(repo_root, expected_version))
    checks.extend(_check_git(repo_root, expected_commit, expected_tree))
    checks.append(_check_tag_absence(repo_root, expected_version, expected_commit))
    checks.append(_check_manifest(rc_manifest_path))
    checks.append(_check_manifest_version(rc_manifest_path, expected_version))
    checks.append(_check_qualification(rc_manifest_path, require_qualified=require_qualified))
    checks.append(_check_no_local_path_dependency(rc_manifest_path))
    checks.extend(_check_tool_availability())
    checks.extend(_check_registry_identifiers())
    checks.extend(_check_credentials())
    checks.append(_check_no_state_conflict(repo_root, expected_version))
    return PreflightReport(checks=checks)


__all__ = ["PASS", "FAIL", "WARN", "CheckResult", "PreflightReport", "run_preflight"]
