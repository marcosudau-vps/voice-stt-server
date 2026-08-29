"""Projection of AP-SRV-030 lifecycle events onto the frozen v2 event names.

Every domain event of a controlled session already funnels through exactly one
place - ``RecorderBackedRealtimeSession._publish_timeline_event``. AP-SRV-040
subscribes to that single funnel instead of building its own emitters, which
is what makes ``activation.input_closed`` exactly-once *by construction*: the
AP-SRV-030 close seam reserves one logical close record, publishes it once,
and this projector turns that one publication into one v2 event.

The projector holds no authority. It reads authoritative values (phase,
deadline, ledger counts) that the domain has already decided and numbers them
through :class:`~.session.ProtocolSessionState`. The only state it keeps is a
memo of already observed segment identities, because a legacy
``recording_ended`` is published after the session has already released the
segment context that carries ``segmentSequence``.

Phase changes
-------------

AP-SRV-030 has no dedicated "phase changed" event; the phase is carried by the
lifecycle events themselves. ``activation.phase_changed`` is therefore derived
from the authoritative phase observed at emission time: when the phase moved
since the last projected event and the mapped event does not already announce
the new phase, one ``activation.phase_changed`` is emitted first. A refresh
that moved a deadline is published as a same-phase ``activation.phase_changed``
- the frozen contract has no other carrier for a confirmed new deadline.
"""

import threading
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from . import schema


@dataclass(frozen=True)
class ProjectionContext:
    """Authoritative values read once, at the moment an event is published."""

    phase: str = schema.IDLE
    activation_id: Optional[str] = None
    activation_sequence: Optional[int] = None
    primary_source: Optional[str] = None
    deadline_at_unix_ms: Optional[int] = None
    remaining_ms: Optional[int] = None
    effective_settings: Dict[str, Any] = field(default_factory=dict)
    active_segment_id: Optional[str] = None
    active_segment_sequence: Optional[int] = None


#: Legacy lifecycle event -> canonical v2 event. Anything absent is not part
#: of the frozen v2 domain contract and is dropped instead of leaking a legacy
#: name onto a v2 connection.
LEGACY_EVENT_TYPES = {
    "activation_started": schema.EVENT_ACTIVATION_STARTED,
    "activation_refreshed": schema.EVENT_ACTIVATION_PHASE_CHANGED,
    "activation_closed": schema.EVENT_ACTIVATION_INPUT_CLOSED,
    "recording_started": schema.EVENT_SEGMENT_RECORDING_STARTED,
    "recording_ended": schema.EVENT_SEGMENT_RECORDING_ENDED,
    "transcription_started": schema.EVENT_TRANSCRIPTION_ACCEPTED,
    "final_transcript": schema.EVENT_TRANSCRIPTION_COMPLETED,
    "final_transcript_discarded": schema.EVENT_TRANSCRIPTION_DISCARDED,
    # The frozen event list has no ``transcription.cancelled``; a deliberate
    # cancel is a discard whose machine-readable ``reason`` says so.
    "final_transcript_cancelled": schema.EVENT_TRANSCRIPTION_DISCARDED,
    "final_transcript_failed": schema.EVENT_TRANSCRIPTION_FAILED,
    "watchdog_warning": schema.EVENT_WATCHDOG_WARNING,
    "wakeword_detected": schema.EVENT_WAKEWORD_DETECTED,
    "wakeword_availability_changed": schema.EVENT_WAKEWORD_AVAILABILITY_CHANGED,
    # ``activation_drained`` fans out by its terminal state, see below.
    "activation_drained": None,
}

#: Ledger terminal -> canonical activation terminal event.
ACTIVATION_TERMINAL_TYPES = {
    "completed": schema.EVENT_ACTIVATION_COMPLETED,
    "cancelled": schema.EVENT_ACTIVATION_CANCELLED,
    "failed": schema.EVENT_ACTIVATION_FAILED,
}

#: Events that already state the phase they established, so no separate
#: ``activation.phase_changed`` is projected in front of them.
_PHASE_ANNOUNCING = frozenset({
    schema.EVENT_ACTIVATION_STARTED,
    schema.EVENT_ACTIVATION_INPUT_CLOSED,
    schema.EVENT_ACTIVATION_PHASE_CHANGED,
})

#: Catalog-level events. They describe the server's wake-word build, not one
#: session's foreground phase, so they must never derive a phase change.
_CATALOG_LEVEL = frozenset({schema.EVENT_WAKEWORD_AVAILABILITY_CHANGED})


class EventProjector:
    """Turns one legacy lifecycle publication into zero or more v2 events."""

    def __init__(self, state):
        self._state = state
        self._lock = threading.RLock()
        self._phase = schema.IDLE
        #: segmentId -> (segmentSequence, activationId), learned from the
        #: authoritative context while it is still available.
        self._segments = {}

    # -- public API ----------------------------------------------------------

    def project(self, legacy_event, payload, context):
        """The v2 events for one legacy publication, in wire order."""
        if legacy_event == "activation_drained":
            return self._project_drained(payload)

        event_type = LEGACY_EVENT_TYPES.get(legacy_event)
        if event_type is None:
            return []

        self._remember_segment(payload, context)

        events = []
        phase_event = self._phase_change_event(event_type, payload, context)
        if phase_event is not None:
            events.append(phase_event)

        builder = _BUILDERS[event_type]
        fields = builder(self, payload, context)
        if fields is None:
            return events

        envelope = self._state.mint_event(
            event_type,
            logical_key=self._logical_key(legacy_event, payload, context),
            occurred_at_unix_ms=_timestamp_ms(payload),
        )
        envelope.update(fields)
        events.append(envelope)
        if event_type not in _CATALOG_LEVEL:
            self._observe_phase(event_type, context)
        return events

    def observed_phase(self):
        with self._lock:
            return self._phase

    # -- phase handling ------------------------------------------------------

    def _phase_change_event(self, event_type, payload, context):
        if event_type in _PHASE_ANNOUNCING or event_type in _CATALOG_LEVEL:
            return None
        phase = context.phase
        if phase not in schema.INPUT_PHASES:
            return None
        with self._lock:
            previous = self._phase
            if previous == phase:
                return None
            self._phase = phase
        envelope = self._state.mint_event(
            schema.EVENT_ACTIVATION_PHASE_CHANGED,
            occurred_at_unix_ms=_timestamp_ms(payload),
        )
        envelope.update({
            "activationId": context.activation_id,
            "previousPhase": previous,
            "inputPhase": phase,
            "deadlineAtUnixMs": context.deadline_at_unix_ms,
            "remainingMs": context.remaining_ms,
        })
        return envelope

    def _observe_phase(self, event_type, context):
        if event_type == schema.EVENT_ACTIVATION_STARTED:
            with self._lock:
                self._phase = schema.WAITING_FIRST_SPEECH
            return
        if event_type == schema.EVENT_ACTIVATION_INPUT_CLOSED:
            # The input side is closed; the foreground slot is free again.
            # Background draining is reported by the activation terminals.
            with self._lock:
                self._phase = schema.IDLE
            return
        if context.phase in schema.INPUT_PHASES:
            with self._lock:
                self._phase = context.phase

    # -- segment identity memo ----------------------------------------------

    def _remember_segment(self, payload, context):
        segment_id = payload.get("segmentId")
        if segment_id is None:
            return
        sequence = payload.get("segmentSequence")
        if sequence is None and context.active_segment_id == segment_id:
            sequence = context.active_segment_sequence
        activation_id = payload.get("activationId") or context.activation_id
        if sequence is None:
            return
        with self._lock:
            self._segments[segment_id] = (int(sequence), activation_id)

    def _segment_fields(self, payload, context):
        segment_id = payload.get("segmentId")
        if segment_id is None:
            return None
        sequence = payload.get("segmentSequence")
        activation_id = payload.get("activationId")
        with self._lock:
            remembered = self._segments.get(segment_id)
        if remembered is not None:
            if sequence is None:
                sequence = remembered[0]
            if activation_id is None:
                activation_id = remembered[1]
        if sequence is None:
            return None
        return {
            "activationId": activation_id or context.activation_id,
            "segmentId": str(segment_id),
            "segmentSequence": int(sequence),
        }

    # -- logical identity ----------------------------------------------------

    @staticmethod
    def _logical_key(legacy_event, payload, context):
        """The key that makes a transport retry re-send one logical event.

        Only events with a stable natural identity get a key. Everything else
        is minted fresh, because the domain publishes it exactly once anyway.
        """
        if legacy_event == "activation_closed":
            activation_id = payload.get("activationId") or context.activation_id
            return ("activation.input_closed", str(activation_id))
        if legacy_event in {
            "final_transcript",
            "final_transcript_discarded",
            "final_transcript_cancelled",
            "final_transcript_failed",
        }:
            segment_id = payload.get("segmentId")
            if segment_id is not None:
                return ("transcription.terminal", str(segment_id))
        return None

    # -- per-event field builders -------------------------------------------

    def _build_activation_started(self, payload, context):
        return {
            "activationId": payload.get("activationId") or context.activation_id,
            "activationSequence": _int_or_none(
                payload.get("activationSequence"), context.activation_sequence
            ),
            "primarySource": (
                payload.get("primarySource") or context.primary_source
            ),
            "inputPhase": schema.WAITING_FIRST_SPEECH,
            "effectiveSettings": dict(context.effective_settings),
        }

    def _build_phase_changed(self, payload, context):
        # Reached through ``activation_refreshed``: same phase, new deadline.
        phase = context.phase if context.phase in schema.INPUT_PHASES else None
        if phase is None:
            return None
        return {
            "activationId": payload.get("activationId") or context.activation_id,
            "previousPhase": phase,
            "inputPhase": phase,
            "deadlineAtUnixMs": context.deadline_at_unix_ms,
            "remainingMs": context.remaining_ms,
        }

    def _build_input_closed(self, payload, context):
        return {
            "activationId": payload.get("activationId") or context.activation_id,
            "reason": payload.get("reason") or "input_closed",
            # Null for every close that no accepted finish/cancel caused -
            # timer, watchdog, device, session and recovery included.
            "causedByCommandId": payload.get("causedByCommandId"),
            "acceptedSegmentCount": int(payload.get("acceptedSegmentCount") or 0),
        }

    def _build_segment_recording_started(self, payload, context):
        return self._segment_fields(payload, context)

    def _build_segment_recording_ended(self, payload, context):
        fields = self._segment_fields(payload, context)
        if fields is None:
            return None
        fields["reason"] = payload.get("reason") or "recording_stop"
        return fields

    def _build_transcription_accepted(self, payload, context):
        return self._segment_fields(payload, context)

    def _build_transcription_completed(self, payload, context):
        fields = self._segment_fields(payload, context)
        if fields is None:
            return None
        fields["text"] = str(payload.get("text") or "")
        return fields

    def _build_transcription_discarded(self, payload, context):
        fields = self._segment_fields(payload, context)
        if fields is None:
            return None
        fields["reason"] = payload.get("reason") or "discarded"
        return fields

    def _build_transcription_failed(self, payload, context):
        fields = self._segment_fields(payload, context)
        if fields is None:
            return None
        fields["reason"] = payload.get("reason") or "failed"
        return fields

    def _build_watchdog_warning(self, payload, context):
        fields = self._segment_fields(payload, context)
        if fields is None:
            fields = {
                "activationId": (
                    payload.get("activationId") or context.activation_id
                ),
                "segmentId": None,
                "segmentSequence": None,
            }
        fields["deadlineAtUnixMs"] = context.deadline_at_unix_ms
        fields["remainingMs"] = context.remaining_ms
        return fields

    def _build_wakeword_detected(self, payload, context):
        # AP-SRV-060: the canonical id, the score and the activation the very
        # same hit opened come from the wake admission coordinator. Raw scores
        # never reach this projector - only accepted detections do.
        return {
            "activationId": payload.get("activationId") or context.activation_id,
            "wakeWordId": payload.get("wakeWordId") or payload.get("wakeWord"),
            "score": payload.get("score"),
            "primarySource": schema.WAKE_WORD_SOURCE,
        }

    def _build_wakeword_availability_changed(self, payload, context):
        # Catalog level, not activation level: it carries the catalog revision
        # and the currently available ids, never an activation id.
        revision = payload.get("catalogRevision")
        available = payload.get("availableWakeWordIds")
        if revision is None or not isinstance(available, (list, tuple)):
            return None
        return {
            "catalogRevision": int(revision),
            "availableWakeWordIds": list(available),
        }

    # -- activation terminals ------------------------------------------------

    def _project_drained(self, payload):
        state = payload.get("state")
        event_type = ACTIVATION_TERMINAL_TYPES.get(state)
        if event_type is None:
            return []
        activation_id = payload.get("activationId")
        envelope = self._state.mint_event(
            event_type,
            logical_key=("activation.terminal", str(activation_id)),
            occurred_at_unix_ms=_timestamp_ms(payload),
        )
        envelope.update({
            "activationId": activation_id,
            "acceptedSegmentCount": int(
                payload.get("acceptedSegmentCount") or 0
            ),
            "terminalSegmentCount": int(
                payload.get("terminalSegmentCount") or 0
            ),
        })
        if event_type != schema.EVENT_ACTIVATION_COMPLETED:
            envelope["reason"] = payload.get("reason") or str(state)
        return [envelope]


_BUILDERS = {
    schema.EVENT_ACTIVATION_STARTED: EventProjector._build_activation_started,
    schema.EVENT_ACTIVATION_PHASE_CHANGED: EventProjector._build_phase_changed,
    schema.EVENT_ACTIVATION_INPUT_CLOSED: EventProjector._build_input_closed,
    schema.EVENT_SEGMENT_RECORDING_STARTED: (
        EventProjector._build_segment_recording_started
    ),
    schema.EVENT_SEGMENT_RECORDING_ENDED: (
        EventProjector._build_segment_recording_ended
    ),
    schema.EVENT_TRANSCRIPTION_ACCEPTED: (
        EventProjector._build_transcription_accepted
    ),
    schema.EVENT_TRANSCRIPTION_COMPLETED: (
        EventProjector._build_transcription_completed
    ),
    schema.EVENT_TRANSCRIPTION_DISCARDED: (
        EventProjector._build_transcription_discarded
    ),
    schema.EVENT_TRANSCRIPTION_FAILED: (
        EventProjector._build_transcription_failed
    ),
    schema.EVENT_WATCHDOG_WARNING: EventProjector._build_watchdog_warning,
    schema.EVENT_WAKEWORD_DETECTED: EventProjector._build_wakeword_detected,
    schema.EVENT_WAKEWORD_AVAILABILITY_CHANGED: (
        EventProjector._build_wakeword_availability_changed
    ),
}


def _timestamp_ms(payload):
    timestamp = payload.get("timestamp")
    if timestamp is None:
        return None
    try:
        return int(round(float(timestamp) * 1000))
    except (TypeError, ValueError):
        return None


def _int_or_none(value, fallback=None):
    for candidate in (value, fallback):
        if candidate is None or isinstance(candidate, bool):
            continue
        try:
            return int(candidate)
        except (TypeError, ValueError):
            continue
    return None
