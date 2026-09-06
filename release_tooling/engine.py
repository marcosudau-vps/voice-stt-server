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

from .errors import ConflictError, ReleaseError, VerificationUnavailableError
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


#: The fixed W6 publication order (AP-SRV-070 W5, section 1.4), now as the
#: one graph both dry-run and real publish walk.
STEP_DEFINITIONS: tuple = (
    StepDefinition("pypi", "PREPARED", "PYPI_PUBLISHED", "Publish the qualified wheel + sdist to PyPI", StepKind.PUBLISH),
    StepDefinition("ghcr", "PYPI_PUBLISHED", "GHCR_PUBLISHED", "Push the qualified Free + Pro images to GHCR", StepKind.PUBLISH),
    StepDefinition("dockerhub", "GHCR_PUBLISHED", "DOCKERHUB_PUBLISHED", "Push the qualified Free + Pro images to Docker Hub", StepKind.PUBLISH),
    StepDefinition("external_verification", "DOCKERHUB_PUBLISHED", "EXTERNAL_VERIFIED", "Verify the externally retrievable PyPI/GHCR/Docker Hub artifacts", StepKind.VERIFY_ONLY),
    StepDefinition("git_tag", "EXTERNAL_VERIFIED", "TAGGED", "Create and push the Git version tag", StepKind.PUBLISH),
    StepDefinition("github_release", "TAGGED", "GITHUB_RELEASED", "Create the GitHub Release", StepKind.PUBLISH),
    StepDefinition("final_verification", "GITHUB_RELEASED", "FINAL_VERIFIED", "Run final end-to-end verification of every published surface", StepKind.VERIFY_ONLY),
    StepDefinition("complete", "FINAL_VERIFIED", "COMPLETE", "Mark the release COMPLETE", StepKind.LOCAL),
)

assert [s.from_state for s in STEP_DEFINITIONS] == STATE_ORDER[:-1]
assert [s.to_state for s in STEP_DEFINITIONS] == STATE_ORDER[1:]


def plan_from(current_state: str) -> List[StepDefinition]:
    """Every remaining step definition from ``current_state`` through ``COMPLETE``."""
    if current_state not in STATE_INDEX:
        raise ValueError(f"unknown state {current_state!r}; expected one of {STATE_ORDER}")
    return list(STEP_DEFINITIONS[STATE_INDEX[current_state]:])


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
) -> EngineRunResult:
    """Walks :data:`STEP_DEFINITIONS` from ``state.state`` to ``COMPLETE``.

    ``adapters`` maps each :class:`StepDefinition` ``key`` (``"pypi"``,
    ``"ghcr"``, ``"dockerhub"``, ``"external_verification"``, ``"git_tag"``,
    ``"github_release"``, ``"final_verification"``) to an object exposing
    ``verify(manifest, state)``/``publish(manifest, state)`` - see
    ``release_tooling.adapters``. The ``"complete"`` step needs no adapter.

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
    working = state.clone()
    outcomes: List[StepOutcome] = []

    for step in plan_from(working.state):
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
