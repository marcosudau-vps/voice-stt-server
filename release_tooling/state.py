"""The resumable release-state contract (AP-SRV-070 W5, section 7).

The state file is not a Git authority and never carries a secret. It exists
so a partial W6 publication run can resume the *same* product version
instead of ever inventing a new one after a partial failure (section 3: "no
wasted public version numbers"). State transitions are strictly monotonic
along :data:`STATE_ORDER` - the only new-state accepted from state ``X`` is
either ``X`` again (an idempotent re-verification / resume) or the one
immediately after it. Anything else is an :class:`OrderError`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .errors import OrderError, StateError
from .redaction import assert_no_secrets

#: The fixed W6 publication order (AP-SRV-070 W5, sections 1.4 and 7).
STATE_ORDER: List[str] = [
    "PREPARED",
    "PYPI_PUBLISHED",
    "GHCR_PUBLISHED",
    "DOCKERHUB_PUBLISHED",
    "EXTERNAL_VERIFIED",
    "TAGGED",
    "GITHUB_RELEASED",
    "FINAL_VERIFIED",
    "COMPLETE",
]
STATE_INDEX: Dict[str, int] = {name: index for index, name in enumerate(STATE_ORDER)}


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class ReleaseState:
    version: str
    sourceCommit: str
    sourceTree: str
    wheel: Dict[str, str]
    sdist: Dict[str, str]
    freeImage: Dict[str, str]
    proImage: Dict[str, str]
    state: str = "PREPARED"
    history: List[Dict[str, str]] = field(default_factory=list)
    createdAtUtc: str = field(default_factory=_utcnow_iso)
    updatedAtUtc: str = field(default_factory=_utcnow_iso)

    def __post_init__(self) -> None:
        if self.state not in STATE_INDEX:
            raise StateError(f"unknown release state {self.state!r}; expected one of {STATE_ORDER}")
        if not self.history:
            self.history = [{"state": self.state, "atUtc": self.updatedAtUtc}]

    def to_json_dict(self) -> Dict[str, Any]:
        payload = {
            "version": self.version,
            "sourceCommit": self.sourceCommit,
            "sourceTree": self.sourceTree,
            "wheel": self.wheel,
            "sdist": self.sdist,
            "freeImage": self.freeImage,
            "proImage": self.proImage,
            "state": self.state,
            "history": self.history,
            "createdAtUtc": self.createdAtUtc,
            "updatedAtUtc": self.updatedAtUtc,
        }
        assert_no_secrets(payload)
        return payload

    def clone(self) -> "ReleaseState":
        """An independent copy - the engine mutates a clone during a dry-run
        so the caller's original ``ReleaseState`` (and its history list) is
        never touched unless the caller explicitly persists the result."""
        return ReleaseState.from_json_dict(self.to_json_dict())

    @classmethod
    def from_json_dict(cls, data: Dict[str, Any]) -> "ReleaseState":
        required = ("version", "sourceCommit", "sourceTree", "wheel", "sdist", "freeImage", "proImage", "state")
        missing = [key for key in required if key not in data]
        if missing:
            raise StateError(f"release state is missing required field(s): {missing}")
        return cls(
            version=data["version"],
            sourceCommit=data["sourceCommit"],
            sourceTree=data["sourceTree"],
            wheel=data["wheel"],
            sdist=data["sdist"],
            freeImage=data["freeImage"],
            proImage=data["proImage"],
            state=data["state"],
            history=list(data.get("history") or []),
            createdAtUtc=data.get("createdAtUtc", _utcnow_iso()),
            updatedAtUtc=data.get("updatedAtUtc", _utcnow_iso()),
        )


def new_state(
    *,
    version: str,
    source_commit: str,
    source_tree: str,
    wheel: Dict[str, str],
    sdist: Dict[str, str],
    free_image: Dict[str, str],
    pro_image: Dict[str, str],
) -> ReleaseState:
    """A fresh ``PREPARED`` state for one exact source/artifact identity."""
    return ReleaseState(
        version=version,
        sourceCommit=source_commit,
        sourceTree=source_tree,
        wheel=dict(wheel),
        sdist=dict(sdist),
        freeImage=dict(free_image),
        proImage=dict(pro_image),
    )


def default_state_path(repo_root: Path, version: str) -> Path:
    from .config import release_state_dir

    return release_state_dir(repo_root) / f"{version}.json"


def load_state(path: Path) -> Optional[ReleaseState]:
    """The persisted state at ``path``, or ``None`` if no state file exists yet.

    Raises :class:`StateError` if the file exists but cannot be parsed - a
    corrupted state file must never be silently treated as "no state" (that
    could let a rerun re-publish a step that already succeeded).
    """
    path = Path(path)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise StateError(f"release state at {path} is corrupted (invalid JSON): {exc}") from exc
    return ReleaseState.from_json_dict(data)


def save_state(path: Path, state: ReleaseState) -> None:
    """Atomically writes ``state`` to ``path`` (write-tmp-then-replace)."""
    payload = state.to_json_dict()  # raises SecretDetectedError if unsafe
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def ensure_same_version(state: ReleaseState, requested_version: str) -> None:
    """Hard-stops if ``requested_version`` does not match the fixed state version.

    "Version is fixed once publication begins" (AP-SRV-070 W5, section 7): a
    release run must never silently continue an existing state under a
    different version, and must never start a *new* state for a version that
    already has one recorded under a different identity.
    """
    if state.version != requested_version:
        raise StateError(
            f"release state is fixed to version {state.version!r}; "
            f"refusing to continue it as {requested_version!r} "
            "(a version becomes immutable once its release state is created)"
        )


def ensure_same_identity(state: ReleaseState, *, source_commit: str, source_tree: str, wheel: Dict[str, str], sdist: Dict[str, str], free_image: Dict[str, str], pro_image: Dict[str, str]) -> None:
    """Hard-stops if the artifact identity resuming ``state`` has drifted.

    Resuming the same version must resume the *same* qualified artifacts,
    never a silently different rebuild.
    """
    mismatches = []
    if state.sourceCommit != source_commit:
        mismatches.append(f"sourceCommit {state.sourceCommit} != {source_commit}")
    if state.sourceTree != source_tree:
        mismatches.append(f"sourceTree {state.sourceTree} != {source_tree}")
    if state.wheel != dict(wheel):
        mismatches.append(f"wheel {state.wheel} != {wheel}")
    if state.sdist != dict(sdist):
        mismatches.append(f"sdist {state.sdist} != {sdist}")
    if state.freeImage != dict(free_image):
        mismatches.append(f"freeImage {state.freeImage} != {free_image}")
    if state.proImage != dict(pro_image):
        mismatches.append(f"proImage {state.proImage} != {pro_image}")
    if mismatches:
        raise StateError(
            f"release state for version {state.version} does not match the artifact identity "
            f"being resumed: {'; '.join(mismatches)}"
        )


def advance(state: ReleaseState, target: str) -> ReleaseState:
    """Returns ``state`` moved to ``target`` if that is the current state (an
    idempotent no-op resume) or the very next state in :data:`STATE_ORDER`.

    Any other target - including skipping ahead, or moving backwards - is an
    :class:`OrderError`. This is the single place fixed-order enforcement
    lives; every barrier in ``release_tooling.pipeline`` is built on it.
    """
    if target not in STATE_INDEX:
        raise OrderError(f"unknown target state {target!r}; expected one of {STATE_ORDER}")
    current_index = STATE_INDEX[state.state]
    target_index = STATE_INDEX[target]
    if target_index == current_index:
        return state  # idempotent resume: already there, nothing to do
    if target_index != current_index + 1:
        raise OrderError(
            f"cannot advance release state from {state.state!r} to {target!r}: "
            f"the fixed order requires {STATE_ORDER[current_index + 1] if current_index + 1 < len(STATE_ORDER) else '(already complete)'!r} next"
        )
    state.state = target
    state.updatedAtUtc = _utcnow_iso()
    state.history.append({"state": target, "atUtc": state.updatedAtUtc})
    return state


def assert_tag_allowed(state: ReleaseState) -> None:
    """Raises :class:`OrderError` unless external verification has completed."""
    if STATE_INDEX[state.state] < STATE_INDEX["EXTERNAL_VERIFIED"]:
        raise OrderError(
            f"Git tag creation is blocked: release state is {state.state!r}, "
            "but PyPI/GHCR/Docker Hub external verification must complete first"
        )


def assert_github_release_allowed(state: ReleaseState) -> None:
    """Raises :class:`OrderError` unless the Git tag step has completed."""
    if STATE_INDEX[state.state] < STATE_INDEX["TAGGED"]:
        raise OrderError(
            f"GitHub Release creation is blocked: release state is {state.state!r}, "
            "but the Git tag step must complete first"
        )


__all__ = [
    "STATE_ORDER",
    "STATE_INDEX",
    "ReleaseState",
    "new_state",
    "default_state_path",
    "load_state",
    "save_state",
    "ensure_same_version",
    "ensure_same_identity",
    "advance",
    "assert_tag_allowed",
    "assert_github_release_allowed",
]
