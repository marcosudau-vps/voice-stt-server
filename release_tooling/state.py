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

#: The fixed W6 publication order (AP-SRV-070 W5-R04, section 15).
#:
#: W5-R01..R03 created the Git tag *after* every public artifact. W5-R04
#: supersedes that: once ``2.0.0`` exists on PyPI or in a registry the version
#: is already publicly reserved, so the immutable Git tag must already exist as
#: the source identity anchor during any partial publication. The tag is
#: therefore the first publishing step, and it happens only after every
#: deterministic build/test/qualification gate has passed.
#:
#: Two further W5-R04 corrections are encoded here:
#:
#: * Docker Hub now precedes GHCR, because GHCR is a *promotion of the exact
#:   Docker Hub manifest by digest* rather than an independent second push
#:   (section 20). The previous order made that promotion impossible.
#: * ``ALIASES_PUBLISHED`` is a real state, not an afterthought: the movable
#:   ``2.0``/``2``/``latest`` tags may only move once the exact Free and Pro
#:   artifacts are verified in *both* registries (section 21), which is exactly
#:   what reaching ``EXTERNAL_VERIFIED`` means.
STATE_ORDER: List[str] = [
    "PREPARED",
    "TAGGED",
    "PYPI_PUBLISHED",
    "DOCKERHUB_PUBLISHED",
    "GHCR_PUBLISHED",
    "EXTERNAL_VERIFIED",
    "ALIASES_PUBLISHED",
    "GITHUB_RELEASED",
    "FINAL_VERIFIED",
    "COMPLETE",
]

#: The first state in which any irreversible *public package/registry* artifact
#: may exist. Everything at or after this index requires the Git tag.
FIRST_PUBLIC_ARTIFACT_STATE = "PYPI_PUBLISHED"
STATE_INDEX: Dict[str, int] = {name: index for index, name in enumerate(STATE_ORDER)}


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class ReleaseState:
    version: str
    sourceCommit: str
    sourceTree: str
    #: ``{variant: {"name": <pypi distribution>, "wheels": "<file>=<sha256>;..."}}``
    #: for both public distributions. AP-SRV-070 W5-R04 replaced the old
    #: single ``wheel``/``sdist`` pair: VoiceSTT now publishes two complete
    #: alternative distributions, each embedding a different native Kroko
    #: runtime, and there is no sdist at all (an sdist cannot carry a native
    #: runtime, so it could not honour the "no local build" guarantee).
    distributions: Dict[str, Dict[str, str]]
    #: ``{variant: {"tag": ..., "digest": "sha256:..."}}`` - the OCI manifest
    #: digest, which is the identity a registry can actually be checked
    #: against and the identity that gets promoted between registries.
    images: Dict[str, Dict[str, str]]
    #: The exact qualified candidate this release state belongs to
    #: (AP-SRV-070 W5-R04, section 13). Carries the candidate id, the workflow
    #: run that produced it, and the SHA-256 of the RC manifest itself, so a
    #: resume can prove it is continuing *that* candidate rather than a
    #: look-alike rebuild. Empty for a locally driven release that has no
    #: GitHub candidate run behind it.
    candidate: Dict[str, str] = field(default_factory=dict)
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
            "distributions": self.distributions,
            "images": self.images,
            "candidate": self.candidate,
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
        required = ("version", "sourceCommit", "sourceTree", "distributions", "images", "state")
        missing = [key for key in required if key not in data]
        if missing:
            raise StateError(f"release state is missing required field(s): {missing}")
        return cls(
            version=data["version"],
            sourceCommit=data["sourceCommit"],
            sourceTree=data["sourceTree"],
            distributions=data["distributions"],
            images=data["images"],
            candidate=dict(data.get("candidate") or {}),
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
    distributions: Dict[str, Dict[str, str]],
    images: Dict[str, Dict[str, str]],
    candidate: Optional[Dict[str, str]] = None,
) -> ReleaseState:
    """A fresh ``PREPARED`` state for one exact source/artifact identity."""
    return ReleaseState(
        version=version,
        sourceCommit=source_commit,
        sourceTree=source_tree,
        distributions={k: dict(v) for k, v in distributions.items()},
        images={k: dict(v) for k, v in images.items()},
        candidate=dict(candidate or {}),
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


def ensure_same_identity(state: ReleaseState, *, source_commit: str, source_tree: str, distributions: Dict[str, Dict[str, str]], images: Dict[str, Dict[str, str]], candidate: Optional[Dict[str, str]] = None) -> None:
    """Hard-stops if the artifact identity resuming ``state`` has drifted.

    Resuming the same version must resume the *same* qualified artifacts,
    never a silently different rebuild.
    """
    mismatches = []
    if state.sourceCommit != source_commit:
        mismatches.append(f"sourceCommit {state.sourceCommit} != {source_commit}")
    if state.sourceTree != source_tree:
        mismatches.append(f"sourceTree {state.sourceTree} != {source_tree}")
    expected_distributions = {k: dict(v) for k, v in distributions.items()}
    if state.distributions != expected_distributions:
        mismatches.append(
            f"distributions {state.distributions} != {expected_distributions}"
        )
    expected_images = {k: dict(v) for k, v in images.items()}
    if state.images != expected_images:
        mismatches.append(f"images {state.images} != {expected_images}")
    # AP-SRV-070 W5-R04, section 13: "resume does not silently build a
    # replacement candidate" and "ambiguity between multiple candidate runs
    # fails closed". A state that was created from a named candidate may only
    # ever be resumed from that same candidate; a state created without one
    # (a purely local release) may not silently acquire one mid-flight either.
    if candidate is not None and state.candidate != dict(candidate):
        mismatches.append(f"candidate {state.candidate} != {candidate}")
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
    """Raises :class:`OrderError` unless no public artifact has been published.

    AP-SRV-070 W5-R04, section 15 inverted this barrier. The tag is now the
    *first* publishing step, so what has to be guarded is the opposite of
    before: the tag must be created while the version is still publicly
    unreserved. Reaching this barrier in any state past ``PREPARED`` means a
    public artifact already exists without a source anchor, which is exactly
    the situation the new order exists to prevent.
    """
    if STATE_INDEX[state.state] > STATE_INDEX["PREPARED"]:
        raise OrderError(
            f"Git tag creation is blocked: release state is {state.state!r}, "
            "but the tag must be created while the release is still PREPARED - "
            "before the first irreversible public package/registry publication"
        )


def assert_public_publication_allowed(state: ReleaseState, surface: str) -> None:
    """Raises :class:`OrderError` unless the Git tag already exists.

    The single barrier every irreversible public package/registry write sits
    behind (PyPI, Docker Hub, GHCR, aliases). Asserted defensively inside the
    adapters as well as structurally by the engine's fixed order, so "tag
    before the first public artifact" holds even if an adapter is driven out
    of turn by something other than :func:`release_tooling.engine.run_engine`.
    """
    if STATE_INDEX[state.state] < STATE_INDEX["TAGGED"]:
        raise OrderError(
            f"{surface} publication is blocked: release state is {state.state!r}, "
            "but the immutable Git tag must exist before the first irreversible "
            "public package/registry publication"
        )


def assert_aliases_allowed(state: ReleaseState) -> None:
    """Raises :class:`OrderError` unless every exact artifact is verified.

    AP-SRV-070 W5-R04, section 21: movable aliases may only be updated after
    the exact Free *and* Pro artifacts have been verified in *both* registries,
    which is precisely what ``EXTERNAL_VERIFIED`` records. This is what keeps
    ``latest`` from ever pointing at an incomplete or failed release.
    """
    if STATE_INDEX[state.state] < STATE_INDEX["EXTERNAL_VERIFIED"]:
        raise OrderError(
            f"alias publication is blocked: release state is {state.state!r}, "
            "but the exact Free and Pro artifacts must be verified in both "
            "registries (EXTERNAL_VERIFIED) before any movable alias moves"
        )


def assert_github_release_allowed(state: ReleaseState) -> None:
    """Raises :class:`OrderError` unless the aliases are already published.

    The GitHub Release is the last public success marker (section 22), so it
    sits behind the last publishing step rather than behind the tag.
    """
    if STATE_INDEX[state.state] < STATE_INDEX["ALIASES_PUBLISHED"]:
        raise OrderError(
            f"GitHub Release creation is blocked: release state is {state.state!r}, "
            "but every exact artifact and every movable alias must be published "
            "and verified first - the GitHub Release is the last public marker"
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
    "assert_public_publication_allowed",
    "assert_aliases_allowed",
    "assert_github_release_allowed",
    "FIRST_PUBLIC_ARTIFACT_STATE",
]
