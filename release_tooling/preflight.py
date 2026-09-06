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
from VoiceSTT._version import read_version_file, DISTRIBUTION_NAME  # noqa: E402

PASS = "PASS"
FAIL = "FAIL"
WARN = "WARN"


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


def _check_tool_availability() -> List[CheckResult]:
    results = []
    for tool in ("git", "docker", "twine"):
        found = shutil.which(tool) is not None
        results.append(CheckResult(f"tool_available_{tool}", PASS if found else WARN, f"{tool} on PATH: {found}"))
    return results


def _check_registry_identifiers() -> List[CheckResult]:
    ghcr = config.ghcr_repo_root()
    dockerhub = config.dockerhub_repo_root()
    results = [
        CheckResult(
            "ghcr_repo_configured",
            PASS if ghcr else FAIL,
            f"{config.GHCR_REPO_ENV}={'<set>' if ghcr else '<unset>'}",
        ),
        CheckResult(
            "dockerhub_repo_configured",
            PASS if dockerhub else FAIL,
            f"{config.DOCKERHUB_REPO_ENV}={'<set>' if dockerhub else '<unset>'}",
        ),
        CheckResult("pypi_project_name", PASS, f"pypi project = {DISTRIBUTION_NAME}"),
    ]
    return results


def _check_credentials() -> List[CheckResult]:
    presence = config.credential_presence()
    return [
        CheckResult(f"credential_{name}", PASS if present else WARN, f"{name}={present}")
        for name, present in presence.items()
    ]


def _check_no_state_conflict(repo_root: Path, version: str) -> CheckResult:
    state_path = default_state_path(repo_root, version)
    try:
        state = load_state(state_path)
    except Exception as exc:  # noqa: BLE001
        return CheckResult("no_state_conflict", FAIL, f"existing release state at {state_path} is unusable: {exc}")
    if state is None:
        return CheckResult("no_state_conflict", PASS, f"no existing release state at {state_path} (fresh release)")
    return CheckResult("no_state_conflict", PASS, f"existing release state at {state_path} is state={state.state}, resumable")


def run_preflight(
    *,
    repo_root: Path,
    expected_version: str,
    expected_commit: Optional[str] = None,
    expected_tree: Optional[str] = None,
    rc_manifest_path: Optional[Path] = None,
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
    checks.extend(_check_tool_availability())
    checks.extend(_check_registry_identifiers())
    checks.extend(_check_credentials())
    checks.append(_check_no_state_conflict(repo_root, expected_version))
    return PreflightReport(checks=checks)


__all__ = ["PASS", "FAIL", "WARN", "CheckResult", "PreflightReport", "run_preflight"]
