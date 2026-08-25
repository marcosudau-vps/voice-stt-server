"""Server-authoritative foreground activation state machine.

One session owns exactly one controller. The controller serialises trigger
commands, recorder callbacks and timeout callbacks and exposes the five
canonical foreground phases. Final transcription work is deliberately not a
phase of this machine: after input has been closed safely, the foreground is
idle and may admit the next activation while older work drains in the
background.

``activationSequence`` (also exposed as the compatibility field
``generation``) increases only when a new activation is admitted. ``version``
increases on every state change and invalidates stale timeout callbacks.
Deadlines are monotonic.
"""

from copy import deepcopy
from dataclasses import dataclass
import threading
import time
from types import MappingProxyType
import uuid


IDLE = "idle"
WAITING_FIRST_SPEECH = "waiting_first_speech"
SEGMENT_ACTIVE = "segment_active"
FOLLOWUP_WAIT = "followup_wait"
CLOSING_INPUT = "closing_input"

# Compatibility import for callers that used the old constant name. It is an
# alias, not a sixth phase value.
INACTIVE = IDLE

#: Phases in which the recorder gate must be open.
OPEN_WINDOW_PHASES = frozenset(
    {WAITING_FIRST_SPEECH, SEGMENT_ACTIVE, FOLLOWUP_WAIT}
)

MANUAL_SOURCE = "manual"
WAKE_WORD_SOURCE = "wake_word"
ACTIVATION_SOURCES = frozenset({MANUAL_SOURCE, WAKE_WORD_SOURCE})


def _freeze(value):
    """Returns a recursively immutable, detached settings value."""
    if isinstance(value, dict):
        return MappingProxyType(
            {key: _freeze(item) for key, item in value.items()}
        )
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, set):
        return frozenset(_freeze(item) for item in value)
    return deepcopy(value)


def _thaw(value):
    """Returns a defensive plain-data copy of a frozen settings value."""
    if isinstance(value, MappingProxyType):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    if isinstance(value, frozenset):
        return {_thaw(item) for item in value}
    return deepcopy(value)


@dataclass(frozen=True)
class ActivationDecision:
    accepted: bool
    reason: str
    snapshot: dict
    changed: bool = False


class ActivationController:
    """Thread-safe authority for one session's foreground activation."""

    def __init__(
        self,
        *,
        manual_trigger_enabled=None,
        wake_word_trigger_enabled=None,
        initial_speech_timeout=15.0,
        followup_timeout=3.0,
        extension_seconds=5.0,
        clock=None,
        id_factory=None,
    ):
        if manual_trigger_enabled is None and wake_word_trigger_enabled is None:
            manual_trigger_enabled = True
            wake_word_trigger_enabled = False

        manual_trigger_enabled = bool(manual_trigger_enabled)
        wake_word_trigger_enabled = bool(wake_word_trigger_enabled)
        if not manual_trigger_enabled and not wake_word_trigger_enabled:
            raise ValueError("at least one activation trigger must be enabled")

        self.manual_trigger_enabled = manual_trigger_enabled
        self.wake_word_trigger_enabled = wake_word_trigger_enabled
        self.initial_speech_timeout = self._positive(
            "initial_speech_timeout", initial_speech_timeout
        )
        self.followup_timeout = self._positive(
            "followup_timeout", followup_timeout
        )
        self.extension_seconds = self._positive(
            "extension_seconds", extension_seconds
        )
        self._clock = clock or time.monotonic
        self._id_factory = id_factory or (lambda: uuid.uuid4().hex)
        self._lock = threading.RLock()

        self._activation_sequence = 0
        self._version = 0
        self._activation_id = None
        self._primary_source = None
        self._effective_settings = _freeze({})
        self._phase = IDLE
        self._deadline = None
        self._pending_extension = 0.0
        self._segment_count = 0
        self._close_reason = None

    @staticmethod
    def _positive(name, value):
        number = float(value)
        if number <= 0:
            raise ValueError(f"{name} must be > 0")
        return number

    @property
    def manual_enabled(self):
        return self.manual_trigger_enabled

    @property
    def wake_word_enabled(self):
        return self.wake_word_trigger_enabled

    @property
    def window_open(self):
        with self._lock:
            return self._phase in OPEN_WINDOW_PHASES

    def _source_enabled(self, source):
        if source == MANUAL_SOURCE:
            return self.manual_trigger_enabled
        if source == WAKE_WORD_SOURCE:
            return self.wake_word_trigger_enabled
        return False

    def _snapshot_locked(self):
        sources = [self._primary_source] if self._primary_source else []
        return {
            "activationId": self._activation_id,
            "activationSequence": self._activation_sequence,
            # Gate generation is retained until the v2 wire migration. It is
            # the same session-increasing activation identity.
            "generation": self._activation_sequence,
            "version": self._version,
            "primarySource": self._primary_source,
            "sources": sources,
            "effectiveSettings": _thaw(self._effective_settings),
            "phase": self._phase,
            "state": self._phase,
            "deadline": self._deadline,
            "pendingExtensionSeconds": self._pending_extension,
            "segments": self._segment_count,
            "windowOpen": self._phase in OPEN_WINDOW_PHASES,
            "active": self._phase != IDLE,
        }

    def snapshot(self):
        with self._lock:
            return self._snapshot_locked()

    def activate(self, source, effective_settings=None):
        """Admits a new activation only while the foreground is idle."""
        with self._lock:
            if source not in ACTIVATION_SOURCES:
                return ActivationDecision(
                    False, "trigger_disabled", self._snapshot_locked()
                )
            if self._phase != IDLE:
                return ActivationDecision(
                    False, "activation_locked", self._snapshot_locked()
                )
            if not self._source_enabled(source):
                return ActivationDecision(
                    False, "trigger_disabled", self._snapshot_locked()
                )

            self._activation_id = self._id_factory()
            self._activation_sequence += 1
            self._primary_source = source
            self._effective_settings = _freeze(effective_settings or {})
            self._phase = WAITING_FIRST_SPEECH
            self._deadline = self._clock() + self.initial_speech_timeout
            self._pending_extension = 0.0
            self._segment_count = 0
            self._close_reason = None
            self._version += 1
            return ActivationDecision(
                True, "activated", self._snapshot_locked(), True
            )

    def extend(self, source):
        with self._lock:
            if not self._source_enabled(source):
                return ActivationDecision(
                    False, "trigger_disabled", self._snapshot_locked()
                )
            if self._phase not in OPEN_WINDOW_PHASES:
                return ActivationDecision(
                    False, "not_active", self._snapshot_locked()
                )
            if self._phase == SEGMENT_ACTIVE:
                self._pending_extension += self.extension_seconds
            else:
                now = self._clock()
                base = self._deadline if self._deadline is not None else now
                self._deadline = max(now, base) + self.extension_seconds
            self._version += 1
            return ActivationDecision(
                True, "extended", self._snapshot_locked(), True
            )

    def recording_started(self):
        with self._lock:
            if self._phase not in OPEN_WINDOW_PHASES:
                return ActivationDecision(
                    False, "not_active", self._snapshot_locked()
                )
            if self._phase == SEGMENT_ACTIVE:
                return ActivationDecision(
                    True, "already_recording", self._snapshot_locked()
                )
            self._phase = SEGMENT_ACTIVE
            self._deadline = None
            self._segment_count += 1
            self._version += 1
            return ActivationDecision(
                True, "recording_started", self._snapshot_locked(), True
            )

    def recording_ended(self):
        with self._lock:
            if self._phase == CLOSING_INPUT:
                return ActivationDecision(
                    True, "input_closing", self._snapshot_locked()
                )
            if self._phase != SEGMENT_ACTIVE:
                return ActivationDecision(
                    False, "not_active", self._snapshot_locked()
                )
            timeout = self.followup_timeout + self._pending_extension
            self._pending_extension = 0.0
            self._phase = FOLLOWUP_WAIT
            self._deadline = self._clock() + timeout
            self._version += 1
            return ActivationDecision(
                True, "followup_started", self._snapshot_locked(), True
            )

    def finish(self, source):
        return self._begin_input_close(source, "finished")

    def cancel(self, source):
        return self._begin_input_close(source, "cancelled")

    def _begin_input_close(self, source, reason):
        with self._lock:
            if not self._source_enabled(source):
                return ActivationDecision(
                    False, "trigger_disabled", self._snapshot_locked()
                )
            if self._phase not in OPEN_WINDOW_PHASES:
                return ActivationDecision(
                    False, "not_active", self._snapshot_locked()
                )
            self._phase = CLOSING_INPUT
            self._deadline = None
            self._pending_extension = 0.0
            self._close_reason = reason
            self._version += 1
            snapshot = self._snapshot_locked()
            snapshot["closeReason"] = reason
            return ActivationDecision(True, reason, snapshot, True)

    def input_closed(self):
        """Completes the close barrier after gate/recorder input is closed."""
        with self._lock:
            if self._phase != CLOSING_INPUT:
                return ActivationDecision(
                    False, "not_closing_input", self._snapshot_locked()
                )
            snapshot = self._clear_locked(close_reason=self._close_reason)
            return ActivationDecision(True, "input_closed", snapshot, True)

    def expire(self, expected_version):
        with self._lock:
            if expected_version != self._version:
                return ActivationDecision(
                    False, "stale_timer", self._snapshot_locked()
                )
            if self._phase not in OPEN_WINDOW_PHASES or self._deadline is None:
                return ActivationDecision(
                    False, "not_expirable", self._snapshot_locked()
                )
            if self._clock() < self._deadline:
                return ActivationDecision(
                    False, "not_due", self._snapshot_locked()
                )
            self._phase = CLOSING_INPUT
            self._deadline = None
            self._pending_extension = 0.0
            self._close_reason = "timed_out"
            self._version += 1
            snapshot = self._snapshot_locked()
            snapshot["closeReason"] = self._close_reason
            return ActivationDecision(True, "timed_out", snapshot, True)

    def reset(self):
        """Drops foreground state during stop, close or reconnect."""
        with self._lock:
            if self._phase == IDLE:
                return ActivationDecision(
                    True, "already_idle", self._snapshot_locked()
                )
            snapshot = self._clear_locked()
            return ActivationDecision(True, "reset", snapshot, True)

    def _clear_locked(self, close_reason=None):
        closed_id = self._activation_id
        closed_primary = self._primary_source
        closed_settings = _thaw(self._effective_settings)
        closed_segments = self._segment_count
        closed_sequence = self._activation_sequence

        self._activation_id = None
        self._primary_source = None
        self._effective_settings = _freeze({})
        self._phase = IDLE
        self._deadline = None
        self._pending_extension = 0.0
        self._segment_count = 0
        self._close_reason = None
        self._version += 1

        snapshot = self._snapshot_locked()
        snapshot.update(
            {
                "closedActivationId": closed_id,
                "closedActivationSequence": closed_sequence,
                "closedPrimarySource": closed_primary,
                "closedSources": [closed_primary] if closed_primary else [],
                "closedEffectiveSettings": closed_settings,
                "closedSegments": closed_segments,
            }
        )
        if close_reason:
            snapshot["closeReason"] = close_reason
        return snapshot
