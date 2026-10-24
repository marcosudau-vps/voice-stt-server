"""Owner-process supervision for the unified Kroko runtime (AP-KR-020).

Exactly one native owner process generation is active at a time. A runtime-,
key- or entitlement-relevant model change starts a new generation; the old
generation is terminated and its exit is confirmed before the fallback or the
successor takes over. Results (readiness, status, jobs) of superseded
generations are discarded, never applied to the new one.

This module is native-import-free and secret-free: it spawns and watches
processes but never imports ``kroko_onnx`` and never receives key material.
Child configuration is identified by :func:`config_fingerprint` over
non-secret fields only (presence flags, opaque credential revisions, model
ids). Retries are bounded per configuration generation with backoff, so an
unchanged broken configuration can never spin a crash loop.
"""

from __future__ import annotations

import os
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Mapping, Optional

from .license_runtime import config_fingerprint

#: Environment marker echoed by the owner child in its readiness report, so
#: stale readiness messages of previous generations can be discarded.
OWNER_GENERATION_ENV = "VOICESTT_KROKO_OWNER_GENERATION"


class SupervisorError(RuntimeError):
    """Base error of owner-process supervision."""


class StartDeadlineExceeded(SupervisorError):
    """The candidate owner did not become ready before the start deadline."""


class RetryBudgetExhausted(SupervisorError):
    """The bounded retry budget for one configuration generation is spent."""


class UnconfirmedExit(SupervisorError):
    """An owner process did not terminate even after kill (must not happen)."""


@dataclass(frozen=True)
class OwnerSpec:
    """How to spawn one owner-process candidate."""

    argv: list
    env: Mapping[str, str] = field(default_factory=dict)
    start_deadline_seconds: float = 30.0
    graceful_shutdown_seconds: float = 10.0

    def __post_init__(self):
        if not self.argv:
            raise ValueError("OwnerSpec.argv must not be empty")
        if self.start_deadline_seconds <= 0:
            raise ValueError("start_deadline_seconds must be positive")
        if self.graceful_shutdown_seconds < 0:
            raise ValueError("graceful_shutdown_seconds must not be negative")


@dataclass
class OwnerHandle:
    """A started owner-process generation."""

    generation: int
    process: "subprocess.Popen[bytes]"
    started_monotonic: float
    config_fingerprint: str


class OwnerSupervisor:
    """Manages exactly one active native owner-process generation.

    All blocking waits use injectable clocks/sleepers so the retry, deadline
    and invalidation behavior is deterministically testable with synthetic
    child processes.
    """

    def __init__(
        self,
        *,
        max_attempts: int = 3,
        backoff_base_seconds: float = 2.0,
        backoff_max_seconds: float = 30.0,
        time_fn: Callable[[], float] = time.monotonic,
        sleep_fn: Callable[[float], None] = time.sleep,
        popen_factory: Callable[..., Any] = subprocess.Popen,
    ):
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if backoff_base_seconds < 0 or backoff_max_seconds < 0:
            raise ValueError("backoff bounds must not be negative")
        self._max_attempts = int(max_attempts)
        self._backoff_base = float(backoff_base_seconds)
        self._backoff_max = float(backoff_max_seconds)
        self._time_fn = time_fn
        self._sleep_fn = sleep_fn
        self._popen_factory = popen_factory
        self._lock = threading.RLock()
        self._lifecycle_lock = threading.RLock()
        self._generation = 0
        self._current: Optional[OwnerHandle] = None
        self._last_fingerprint: Optional[str] = None
        self._attempts_for_fingerprint = 0
        self._last_exit_code: Optional[int] = None

    # -- introspection --------------------------------------------------------

    @property
    def current_generation(self) -> int:
        """The active generation (0 = none started yet)."""
        with self._lock:
            return self._generation

    @property
    def last_exit_code(self) -> Optional[int]:
        """Exit code of the most recently terminated owner (or ``None``)."""
        with self._lock:
            return self._last_exit_code

    def is_current(self, generation: int) -> bool:
        """Whether a generation is still the active one."""
        with self._lock:
            return (int(generation) == self._generation and self._current is not None
                    and self._current.process.poll() is None)

    def accept_event(self, generation: int, payload: Any) -> Optional[Any]:
        """Returns readiness/status/job results only for the active generation.

        Results of superseded generations are discarded (``None``) so late
        old events can never authorize the new generation.
        """
        with self._lock:
            if not self.is_current(generation):
                return None
            return payload

    # -- lifecycle ------------------------------------------------------------

    def _backoff_for_attempt(self, attempt_index: int) -> float:
        delay = self._backoff_base * (2.0 ** max(0, attempt_index - 1))
        return min(delay, self._backoff_max)

    def start(self, spec: OwnerSpec, *, config: Mapping[str, Any],
              wait_ready=None) -> OwnerHandle:
        # Serialize the whole stop/spawn/readiness transaction, not just counters.
        with self._lifecycle_lock:
            return self._start(spec, config=config, wait_ready=wait_ready)

    def _start(
        self,
        spec: OwnerSpec,
        *,
        config: Mapping[str, Any],
        wait_ready: Optional[Callable[[float], bool]] = None,
    ) -> OwnerHandle:
        """Starts a new owner generation, terminating the previous one first.

        ``config`` must be free of secret material; its fingerprint resets the
        retry budget when the configuration changed (new runtime, key, mode or
        model selection). When the budget for an unchanged configuration is
        spent, :class:`RetryBudgetExhausted` is raised instead of spawning
        another crash loop. ``wait_ready`` receives the absolute monotonic
        deadline and reports candidate readiness; without it, only early
        process exit counts as failure.
        """
        fingerprint = config_fingerprint(dict(config or {}))
        deadline_window = float(spec.start_deadline_seconds)
        with self._lock:
            if fingerprint != self._last_fingerprint:
                self._last_fingerprint = fingerprint
                self._attempts_for_fingerprint = 0
            if self._attempts_for_fingerprint >= self._max_attempts:
                raise RetryBudgetExhausted(
                    "retry budget spent for this configuration generation; "
                    "change runtime, key, mode or model selection to retry"
                )
            if self._attempts_for_fingerprint > 0:
                delay = self._backoff_for_attempt(self._attempts_for_fingerprint)
            else:
                delay = 0.0
            self._attempts_for_fingerprint += 1
            self._generation += 1
            generation = self._generation
        if delay > 0:
            self._sleep_fn(delay)
        self._terminate_current(
            graceful_seconds=float(spec.graceful_shutdown_seconds))
        env = dict(os.environ)
        env.update(dict(spec.env or {}))
        env[OWNER_GENERATION_ENV] = str(generation)
        try:
            process = self._popen_factory(list(spec.argv), env=env)
        except Exception as exc:
            raise SupervisorError("owner process could not be spawned") from None
        handle = OwnerHandle(
            generation=generation,
            process=process,
            started_monotonic=self._time_fn(),
            config_fingerprint=fingerprint,
        )
        with self._lock:
            self._current = handle
        deadline = self._time_fn() + deadline_window
        try:
            if wait_ready is not None:
                ready = bool(wait_ready(deadline))
            else:
                ready = process.poll() is None
            if not ready or self._time_fn() >= deadline:
                raise StartDeadlineExceeded(
                    f"owner generation {generation} missed its start deadline "
                    f"of {deadline_window:.1f}s"
                )
            if process.poll() is not None:
                raise StartDeadlineExceeded(
                    f"owner generation {generation} exited during startup "
                    f"(code {process.returncode})"
                )
        except Exception:
            self._terminate_current(
                graceful_seconds=float(spec.graceful_shutdown_seconds))
            raise
        return handle

    def _terminate_current(self, graceful_seconds: float) -> Optional[int]:
        """Terminates the active owner and confirms its exit. Idempotent."""
        with self._lock:
            handle = self._current
        if handle is None:
            return None
        process = handle.process
        if process.poll() is not None:
            with self._lock:
                if self._current is handle:
                    self._current = None
            self._record_exit(process.returncode)
            return process.returncode
        try:
            process.terminate()
        except (OSError, ProcessLookupError):
            pass
        try:
            exit_code = process.wait(
                timeout=max(0.0, float(graceful_seconds)))
        except (subprocess.TimeoutExpired, Exception):
            exit_code = None
        if exit_code is None:
            try:
                process.kill()
            except (OSError, ProcessLookupError):
                pass
            try:
                exit_code = process.wait(timeout=30.0)
            except Exception as exc:
                raise UnconfirmedExit(
                    "owner process exit could not be confirmed even after kill"
                ) from exc
        with self._lock:
            if self._current is handle:
                self._current = None
        self._record_exit(exit_code)
        return exit_code

    def _record_exit(self, exit_code: Optional[int]) -> None:
        with self._lock:
            self._last_exit_code = exit_code

    def stop(self, graceful_seconds: float = 10.0) -> Optional[int]:
        """Controlled shutdown with confirmed process end."""
        with self._lifecycle_lock:
            return self._terminate_current(graceful_seconds=float(graceful_seconds))

    # -- config surface ---------------------------------------------------------

    def status(self) -> Dict[str, Any]:
        """Redacted supervisor status (no argv secrets, no environment)."""
        with self._lock:
            current = self._current
            running = current is not None and current.process.poll() is None
            return {
                "generation": self._generation,
                "running": running,
                "attemptsForConfig": self._attempts_for_fingerprint,
                "maxAttempts": self._max_attempts,
                "lastExitCode": self._last_exit_code,
            }


__all__ = [
    "OWNER_GENERATION_ENV",
    "SupervisorError",
    "StartDeadlineExceeded",
    "RetryBudgetExhausted",
    "UnconfirmedExit",
    "OwnerSpec",
    "OwnerHandle",
    "OwnerSupervisor",
]
