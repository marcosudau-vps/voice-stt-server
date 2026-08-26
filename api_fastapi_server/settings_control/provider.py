"""Activation settings port and adapter.

SRV-030 latches the six trigger timings when an activation starts. This module
provides the narrow port (:class:`ActivationSettingsProvider`) and a session
adapter that reads the confirmed millisecond values from a
:class:`SessionSettingsState` and converts them to the second-based values the
:class:`ActivationController` expects - exact, central, without float drift.

Wiring the provider into the real controller construction stays a
``REQUIRES_FINAL_SRV_030_BINDING``; the existing seconds-based session
admission keeps its current behaviour in this prep branch.
"""

from typing import Mapping, Protocol, runtime_checkable

from .session import SessionSettingsState


def milliseconds_to_seconds(value):
    """Exact conversion; the contract raises no float drift on the schema."""
    return float(value) / 1000.0


@runtime_checkable
class ActivationSettingsProvider(Protocol):
    """Port consumed when an activation starts."""

    def activation_timings_seconds(self) -> Mapping[str, float]:
        """Seconds-based timings for the ActivationController."""
        ...

    def freeze(self) -> Mapping[str, object]:
        """Immutable effective settings snapshot for activation projection."""
        ...


class SessionActivationSettingsProvider:
    """Adapter that projects a session's next-activation freeze to seconds."""

    _TIMING_MAP = {
        "activation.initialSpeechTimeoutMs": "initial_speech_timeout",
        "activation.followupTimeoutMs": "followup_timeout",
        "activation.segmentWatchdogInitialMs": "segment_watchdog_initial",
        "activation.segmentWatchdogRefreshMs": "segment_watchdog_refresh",
        "activation.segmentWatchdogWarningMs": "segment_watchdog_warning",
        "activation.closingRecoveryTimeoutMs": "closing_recovery_timeout",
    }

    def __init__(self, session_state: SessionSettingsState):
        self._session_state = session_state

    def activation_timings_seconds(self) -> Mapping[str, float]:
        frozen = self._session_state.freeze_activation()
        return {
            controller_name: milliseconds_to_seconds(frozen[wire_key])
            for wire_key, controller_name in self._TIMING_MAP.items()
            if wire_key in frozen
        }

    def freeze(self) -> Mapping[str, object]:
        return self._session_state.freeze_activation()