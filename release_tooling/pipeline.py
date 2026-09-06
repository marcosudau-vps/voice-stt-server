"""Backward-compatible facade over ``release_tooling.engine`` (AP-SRV-070
W5-R01-C1).

W5-R01 originally had its own hand-written plan list here, separate from
whatever would eventually execute a real publish. Root Review rejected
that split: "Dry-run must exercise the same operation graph and ordering
logic as real publication, not a separate hand-written list of intended
steps." ``release_tooling.engine`` is now the one place that graph lives;
this module only re-exports it under the names other code already uses and
adds :func:`dry_run` as a convenience wrapper around
``engine.run_engine(..., mode=ExecutionMode.DRY_RUN)``.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .engine import (
    STEP_DEFINITIONS,
    EngineRunResult,
    ExecutionMode,
    StepDefinition,
    StepKind,
    StepOutcome,
    plan_from,
    run_engine,
)
from .state import ReleaseState

#: Kept for anything that still wants the plain
#: ``(from_state, to_state, description)`` shape.
PIPELINE_STEPS = tuple((s.from_state, s.to_state, s.description) for s in STEP_DEFINITIONS)


def dry_run(
    state: ReleaseState,
    manifest: Dict[str, Any],
    adapters: Optional[Dict[str, Any]] = None,
) -> EngineRunResult:
    """Walks the real release engine in :data:`ExecutionMode.DRY_RUN`.

    Uses the real, W6-capable adapter bundle by default (their ``verify()``
    calls are read-only; ``publish()`` is never invoked in this mode - see
    ``release_tooling.engine.run_engine``), so the exact operation graph and
    ordering logic real publication would use is what gets reported here.
    Pass ``adapters`` explicitly (as every test in
    ``tests/unit/test_release_pipeline.py``/``test_release_engine.py``
    does) to exercise this without touching the network/Docker/git/gh.
    """
    if adapters is None:
        from .adapters import build_default_adapters

        adapters = build_default_adapters()
    return run_engine(state, manifest, mode=ExecutionMode.DRY_RUN, adapters=adapters)


__all__ = [
    "STEP_DEFINITIONS",
    "PIPELINE_STEPS",
    "StepDefinition",
    "StepKind",
    "StepOutcome",
    "EngineRunResult",
    "ExecutionMode",
    "plan_from",
    "run_engine",
    "dry_run",
]
