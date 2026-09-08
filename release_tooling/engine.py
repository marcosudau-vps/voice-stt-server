"""The one release engine: real publish and dry-run share this exact
operation graph and state machine (AP-SRV-070 W5-R01-C1, Root Review
requirement: "Dry-run must exercise the same operation graph and ordering
logic as real publication, not a separate hand-written list of intended
steps.").

Every step in :data:`STEP_DEFINITIONS` is either:

* ``PUBLISH`` - has a real write action, gated by ``verify() == ABSENT``
  and only ever executed when ``mode == ExecutionMode.REAL``;
* ``VERIFY_ONLY`` - a read-only barrier (external/final verification) that
  can never write anything, ever;
* ``LOCAL`` - the terminal ``COMPLETE`` transition, which has no external
  counterpart to check.

:func:`run_engine` is the single function both ``release.py dry-run`` and
``release.py publish`` call; the only difference between them is the
``mode`` argument and which adapters get wired in. This is what makes "the
same operation graph" a structural guarantee rather than a convention two
separate implementations have to remember to keep in sync.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from .errors import (
    ConflictError,
    ManifestError,
    ReleaseError,
    VerificationUnavailableError,
)
from .remote_checks import ABSENT, MATCH
from .state import STATE_INDEX, STATE_ORDER, ReleaseState, advance


class ExecutionMode(str, Enum):
    REAL = "REAL"
    DRY_RUN = "DRY_RUN"


class StepKind(str, Enum):
    PUBLISH = "PUBLISH"
    VERIFY_ONLY = "VERIFY_ONLY"
    LOCAL = "LOCAL"


@dataclass(frozen=True)
class StepDefinition:
    key: str
    from_state: str
    to_state: str
    description: str
    kind: StepKind


#: The fixed publication order (AP-SRV-070 W5-R04, sections 15/20/21), as the
#: one graph both dry-run and real publish walk.
#:
#: Three orderings here are load-bearing and are each enforced twice - once
#: structurally by this tuple, and once defensively by a barrier the adapter
#: asserts itself (see ``release_tooling.state``):
#:
#: 1. ``git_tag`` is **first**. Once 2.0.0 exists on PyPI or in a registry the
#:    version is publicly reserved, so the immutable source anchor has to exist
#:    before the first irreversible public write, not after it.
#: 2. ``dockerhub`` precedes ``ghcr``, because GHCR is a promotion of the exact
#:    Docker Hub manifest by digest rather than a second independent push.
#: 3. ``aliases`` sits behind ``external_verification``, so a movable tag such
#:    as ``latest`` can never point at an incomplete or failed release, and
#:    ``github_release`` sits behind ``aliases``, so the GitHub Release stays
#:    the last public success marker.
STEP_DEFINITIONS: tuple = (
    StepDefinition("git_tag", "PREPARED", "TAGGED", "Create and push the immutable Git version tag for the qualified source commit", StepKind.PUBLISH),
    StepDefinition("pypi", "TAGGED", "PYPI_PUBLISHED", "Publish the qualified voice-stt-server and voice-stt-server-pro wheels to PyPI", StepKind.PUBLISH),
    StepDefinition("dockerhub", "PYPI_PUBLISHED", "DOCKERHUB_PUBLISHED", "Publish the qualified Free + Pro exact images to Docker Hub", StepKind.PUBLISH),
    StepDefinition("ghcr", "DOCKERHUB_PUBLISHED", "GHCR_PUBLISHED", "Promote the exact Docker Hub manifests by digest to GHCR", StepKind.PUBLISH),
    StepDefinition("external_verification", "GHCR_PUBLISHED", "EXTERNAL_VERIFIED", "Verify every externally retrievable PyPI/Docker Hub/GHCR artifact", StepKind.VERIFY_ONLY),
    StepDefinition("aliases", "EXTERNAL_VERIFIED", "ALIASES_PUBLISHED", "Move the SemVer aliases in both registries onto the verified digests", StepKind.PUBLISH),
    StepDefinition("github_release", "ALIASES_PUBLISHED", "GITHUB_RELEASED", "Create the GitHub Release - the last public success marker", StepKind.PUBLISH),
    StepDefinition("final_verification", "GITHUB_RELEASED", "FINAL_VERIFIED", "Run final end-to-end verification of every published surface", StepKind.VERIFY_ONLY),
    StepDefinition("complete", "FINAL_VERIFIED", "COMPLETE", "Mark the release COMPLETE", StepKind.LOCAL),
)

assert [s.from_state for s in STEP_DEFINITIONS] == STATE_ORDER[:-1]
assert [s.to_state for s in STEP_DEFINITIONS] == STATE_ORDER[1:]


def plan_from(current_state: str, stop_after: Optional[str] = None) -> List[StepDefinition]:
    """Every remaining step from ``current_state``, up to ``stop_after``.

    ``stop_after`` is the boundary that lets one GitHub Actions job advance
    exactly its own portion of the release while the graph, the order and the
    barriers stay in this one place (AP-SRV-070 W5-R04, section 31). It can
    only ever *shorten* the plan: it never reorders a step, never skips one,
    and never permits a transition the fixed order forbids. A job that is
    handed a ``stop_after`` it has already passed simply plans nothing.
    """
    if current_state not in STATE_INDEX:
        raise ValueError(f"unknown state {current_state!r}; expected one of {STATE_ORDER}")
    steps = list(STEP_DEFINITIONS[STATE_INDEX[current_state]:])
    if stop_after is None:
        return steps
    if stop_after not in STATE_INDEX:
        raise ValueError(f"unknown stop_after state {stop_after!r}; expected one of {STATE_ORDER}")
    return [step for step in steps if STATE_INDEX[step.to_state] <= STATE_INDEX[stop_after]]


@dataclass(frozen=True)
class StepOutcome:
    stepKey: str
    fromState: str
    toState: str
    remoteStatus: str  # ABSENT / MATCH / UNKNOWN / N/A
    action: str  # resumed / published / planned / verified / pending / unavailable / advanced
    executed: bool  # True only if a real write happened

    def to_json_dict(self) -> Dict[str, Any]:
        return {
            "stepKey": self.stepKey,
            "from": self.fromState,
            "to": self.toState,
            "remoteStatus": self.remoteStatus,
            "action": self.action,
            "executed": self.executed,
        }


@dataclass(frozen=True)
class EngineRunResult:
    mode: str
    version: str
    startingState: str
    finalState: ReleaseState
    outcomes: List[StepOutcome]
    stoppedEarly: bool = False
    stopReason: Optional[str] = None

    def to_json_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "version": self.version,
            "startingState": self.startingState,
            "finalState": self.finalState.state,
            "sideEffectFree": self.mode == ExecutionMode.DRY_RUN.value,
            "stoppedEarly": self.stoppedEarly,
            "stopReason": self.stopReason,
            "plannedSteps": [o.to_json_dict() for o in self.outcomes],
        }


PersistFn = Callable[[ReleaseState], None]


def run_engine(
    state: ReleaseState,
    manifest: Dict[str, Any],
    *,
    mode: ExecutionMode,
    adapters: Dict[str, Any],
    persist: Optional[PersistFn] = None,
    stop_after: Optional[str] = None,
) -> EngineRunResult:
    """Walks :data:`STEP_DEFINITIONS` from ``state.state`` to ``COMPLETE``.

    ``adapters`` maps each :class:`StepDefinition` ``key`` (``"git_tag"``,
    ``"pypi"``, ``"dockerhub"``, ``"ghcr"``, ``"external_verification"``,
    ``"aliases"``, ``"github_release"``, ``"final_verification"``) to an object exposing
    ``verify(manifest, state)``/``publish(manifest, state)`` - see
    ``release_tooling.adapters``. The ``"complete"`` step needs no adapter.

    ``stop_after`` bounds how far this invocation may advance (see
    :func:`plan_from`). It is how the GitHub publish workflow gives each job
    only the credentials and permissions its own steps need without ever
    forking the operation graph.

    In :data:`ExecutionMode.REAL`, a conflict, an unavailable verification,
    or a ``VERIFY_ONLY`` step that is not yet satisfied all stop the run
    immediately (:class:`ReleaseError`/subclasses propagate). In
    :data:`ExecutionMode.DRY_RUN`, every step is still evaluated (each
    adapter's ``verify()`` is independent of the others), a genuine
    :class:`~release_tooling.errors.ConflictError` still stops the plan
    early (a real run would hit the same wall), but an unmet
    ``VERIFY_ONLY``/``ABSENT`` step is reported as "planned"/"pending" and
    the walk continues so the operator sees the full remaining sequence.
    Nothing is ever persisted in dry-run mode: ``persist`` is only ever
    consulted when ``mode == REAL``.
    """
    if mode == ExecutionMode.REAL:
        readiness = manifest.get("releaseReadiness")
        if readiness != "QUALIFIED":
            raise ManifestError(
                f"Candidate manifest readiness is {readiness!r}; only 'QUALIFIED' "
                "candidates can be published."
            )
        qual = manifest.get("qualification") or {}
        evidence_ref = qual.get("evidenceRef")
        if not evidence_ref or str(evidence_ref).strip() == "" or evidence_ref == "none":
            raise ManifestError(
                "Candidate manifest lacks valid qualification evidenceRef; cannot publish without qualification evidence."
            )
        if state.sourceCommit != manifest.get("sourceCommit"):
            raise ManifestError(
                f"ReleaseState sourceCommit {state.sourceCommit} does not match manifest sourceCommit {manifest.get('sourceCommit')}"
            )
        if state.sourceTree != manifest.get("sourceTree"):
            raise ManifestError(
                f"ReleaseState sourceTree {state.sourceTree} does not match manifest sourceTree {manifest.get('sourceTree')}"
            )

    working = state.clone()
    outcomes: List[StepOutcome] = []

    for step in plan_from(working.state, stop_after):
        if step.kind == StepKind.LOCAL:
            if mode == ExecutionMode.REAL:
                working = advance(working, step.to_state)
                if persist is not None:
                    persist(working)
                outcomes.append(StepOutcome(step.key, step.from_state, step.to_state, "N/A", "advanced", True))
            else:
                outcomes.append(StepOutcome(step.key, step.from_state, step.to_state, "N/A", "planned", False))
            continue

        adapter = adapters[step.key]
        try:
            status = adapter.verify(manifest, working)
        except VerificationUnavailableError as exc:
            outcomes.append(StepOutcome(step.key, step.from_state, step.to_state, "UNKNOWN", "unavailable", False))
            if mode == ExecutionMode.REAL:
                return EngineRunResult(mode.value, manifest["productVersion"], state.state, working, outcomes, True, str(exc))
            continue  # dry-run: report and keep walking the rest of the graph
        except ConflictError as exc:
            # A genuine conflict fails closed in both modes: a real run must
            # stop immediately, and a dry-run must report the exact wall a
            # real run would hit rather than optimistically planning past it.
            outcomes.append(StepOutcome(step.key, step.from_state, step.to_state, "CONFLICT", "conflict", False))
            return EngineRunResult(mode.value, manifest["productVersion"], state.state, working, outcomes, True, str(exc))

        if step.kind == StepKind.VERIFY_ONLY:
            if status == MATCH:
                if mode == ExecutionMode.REAL:
                    working = advance(working, step.to_state)
                    if persist is not None:
                        persist(working)
                    outcomes.append(StepOutcome(step.key, step.from_state, step.to_state, status, "verified", True))
                else:
                    outcomes.append(StepOutcome(step.key, step.from_state, step.to_state, status, "verified", False))
            else:
                reason = f"{step.key} is not yet satisfied: required artifacts are not all verified"
                if mode == ExecutionMode.REAL:
                    outcomes.append(StepOutcome(step.key, step.from_state, step.to_state, status, "pending", False))
                    return EngineRunResult(mode.value, manifest["productVersion"], state.state, working, outcomes, True, reason)
                outcomes.append(StepOutcome(step.key, step.from_state, step.to_state, status, "pending", False))
            continue

        # StepKind.PUBLISH
        if status == MATCH:
            if mode == ExecutionMode.REAL:
                working = advance(working, step.to_state)
                if persist is not None:
                    persist(working)
                outcomes.append(StepOutcome(step.key, step.from_state, step.to_state, status, "resumed", False))
            else:
                outcomes.append(StepOutcome(step.key, step.from_state, step.to_state, status, "resumed", False))
        elif status == ABSENT:
            if mode == ExecutionMode.REAL:
                adapter.publish(manifest, working)
                try:
                    reverified = adapter.verify(manifest, working)
                except (ConflictError, VerificationUnavailableError) as exc:
                    reason = f"{step.key} publish succeeded but post-publish verification failed: {exc}"
                    outcomes.append(StepOutcome(step.key, step.from_state, step.to_state, "UNKNOWN", "publish_unverified", True))
                    return EngineRunResult(mode.value, manifest["productVersion"], state.state, working, outcomes, True, reason)
                if reverified != MATCH:
                    reason = f"{step.key} publish did not result in a verified matching identity"
                    outcomes.append(StepOutcome(step.key, step.from_state, step.to_state, reverified, "publish_unverified", True))
                    return EngineRunResult(mode.value, manifest["productVersion"], state.state, working, outcomes, True, reason)
                working = advance(working, step.to_state)
                if persist is not None:
                    persist(working)
                outcomes.append(StepOutcome(step.key, step.from_state, step.to_state, status, "published", True))
            else:
                outcomes.append(StepOutcome(step.key, step.from_state, step.to_state, status, "planned", False))
        else:  # pragma: no cover - adapters raise ConflictError directly instead of returning this
            raise ReleaseError(f"unexpected remote status {status!r} for step {step.key!r}")

    return EngineRunResult(mode.value, manifest["productVersion"], state.state, working, outcomes)


__all__ = [
    "ExecutionMode",
    "StepKind",
    "StepDefinition",
    "STEP_DEFINITIONS",
    "plan_from",
    "StepOutcome",
    "EngineRunResult",
    "run_engine",
]
