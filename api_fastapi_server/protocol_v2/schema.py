"""Frozen protocol v2 vocabulary.

This module is data only. It holds the message names, enum values, result
codes and close codes of the frozen wire contract
(``PLANUNG/PROTOKOLL_V2_WIRE_SCHEMA.md``) plus the canonical UUID helpers
required by AP-SRV-040 K1.

Nothing here owns state or talks to the domain. Everything that turns a
transport payload into a decision lives in :mod:`.commands`,
:mod:`.handshake` or :mod:`.snapshot`.

Canonical identity (K1)
-----------------------

The frozen schema serialises UUIDs canonically, with hyphens. AP-SRV-040 does
**not** reformat a compact domain id at the wire boundary - that would create
a second string for one identity. Instead a v2 session generates canonical
ids at their authoritative source (:func:`new_canonical_id`) and the very
same string travels through controller, ledger, acks, events and snapshot.
The v1 transport keeps its compact ids until AP-SRV-070.
"""

import uuid


#: The protocol version this cut implements.
PROTOCOL_VERSION = 2

#: Every version a v2 endpoint can negotiate.
SUPPORTED_PROTOCOL_VERSIONS = (2,)


# -- message types -----------------------------------------------------------

HELLO = "hello"
HELLO_ACCEPTED = "hello.accepted"
PROTOCOL_INCOMPATIBLE = "protocol.incompatible"
SESSION_REJECTED = "session.rejected"
COMMAND_ACK = "command.ack"
SESSION_SNAPSHOT = "session.snapshot"

ACTIVATION_COMMAND = "activation.command"
TRIGGER_SUPPRESSION_SET = "trigger_suppression.set"
AUDIO_AVAILABILITY_SET = "audio_availability.set"
SESSION_SETTINGS_PATCH = "session_settings.patch"
SESSION_SNAPSHOT_REQUEST = "session.snapshot.request"

#: Every client command type the v2 endpoint accepts.
COMMAND_TYPES = frozenset({
    ACTIVATION_COMMAND,
    TRIGGER_SUPPRESSION_SET,
    AUDIO_AVAILABILITY_SET,
    SESSION_SETTINGS_PATCH,
    SESSION_SNAPSHOT_REQUEST,
})


# -- activation command vocabulary -------------------------------------------

ACTIVATE = "activate"
REFRESH = "refresh"
FINISH = "finish"
CANCEL = "cancel"

ACTIVATION_ACTIONS = (ACTIVATE, REFRESH, FINISH, CANCEL)

#: Actions that address an already observed activation.
CONTROL_ACTIONS = frozenset({REFRESH, FINISH, CANCEL})

MANUAL_SOURCE = "manual"
WAKE_WORD_SOURCE = "wake_word"

#: The only ``source`` a client may ever claim. ``wake_word`` is created by
#: the server-internal detection admission and is never accepted on the wire.
CLIENT_SOURCES = frozenset({MANUAL_SOURCE})

#: Every source that can appear as ``primarySource`` in events and snapshots.
PRIMARY_SOURCES = frozenset({MANUAL_SOURCE, WAKE_WORD_SOURCE})


# -- foreground phases -------------------------------------------------------

IDLE = "idle"
WAITING_FIRST_SPEECH = "waiting_first_speech"
SEGMENT_ACTIVE = "segment_active"
FOLLOWUP_WAIT = "followup_wait"
CLOSING_INPUT = "closing_input"

#: Exactly the five canonical foreground phases. ``finalizing`` is not one.
INPUT_PHASES = (
    IDLE,
    WAITING_FIRST_SPEECH,
    SEGMENT_ACTIVE,
    FOLLOWUP_WAIT,
    CLOSING_INPUT,
)

OPEN_INPUT_PHASES = frozenset(
    {WAITING_FIRST_SPEECH, SEGMENT_ACTIVE, FOLLOWUP_WAIT, CLOSING_INPUT}
)


# -- command.ack result codes ------------------------------------------------

RESULT_APPLIED = "applied"
RESULT_NO_CHANGE = "no_change"
RESULT_ACTIVATION_LOCKED = "activation_locked"
RESULT_NOT_ACTIVE = "not_active"
RESULT_INVALID_PHASE = "invalid_phase"
RESULT_CLOSING_INPUT = "closing_input"
RESULT_STALE_SESSION = "stale_session"
RESULT_STALE_ACTIVATION = "stale_activation"
RESULT_COMMAND_ID_CONFLICT = "command_id_conflict"
RESULT_INVALID_PAYLOAD = "invalid_payload"
RESULT_TRIGGER_SUPPRESSED = "trigger_suppressed"
RESULT_AUDIO_UNAVAILABLE = "audio_unavailable"
RESULT_SETTINGS_REVISION_CONFLICT = "settings_revision_conflict"
RESULT_SETTINGS_REJECTED = "settings_rejected"
RESULT_INTERNAL_ERROR = "internal_error"

#: The complete, closed set of wire result codes. No free additions.
RESULT_CODES = (
    RESULT_APPLIED,
    RESULT_NO_CHANGE,
    RESULT_ACTIVATION_LOCKED,
    RESULT_NOT_ACTIVE,
    RESULT_INVALID_PHASE,
    RESULT_CLOSING_INPUT,
    RESULT_STALE_SESSION,
    RESULT_STALE_ACTIVATION,
    RESULT_COMMAND_ID_CONFLICT,
    RESULT_INVALID_PAYLOAD,
    RESULT_TRIGGER_SUPPRESSED,
    RESULT_AUDIO_UNAVAILABLE,
    RESULT_SETTINGS_REVISION_CONFLICT,
    RESULT_SETTINGS_REJECTED,
    RESULT_INTERNAL_ERROR,
)

#: ``accepted=true`` is allowed for these two results and for nothing else.
ACCEPTED_RESULTS = frozenset({RESULT_APPLIED, RESULT_NO_CHANGE})


# -- canonical event names ---------------------------------------------------

EVENT_ACTIVATION_STARTED = "activation.started"
EVENT_ACTIVATION_PHASE_CHANGED = "activation.phase_changed"
EVENT_ACTIVATION_INPUT_CLOSED = "activation.input_closed"
EVENT_ACTIVATION_COMPLETED = "activation.completed"
EVENT_ACTIVATION_CANCELLED = "activation.cancelled"
EVENT_ACTIVATION_FAILED = "activation.failed"
EVENT_ACTIVATION_TRIGGER_SUPPRESSED = "activation.trigger_suppressed"
EVENT_SEGMENT_RECORDING_STARTED = "segment.recording_started"
EVENT_SEGMENT_RECORDING_ENDED = "segment.recording_ended"
EVENT_TRANSCRIPTION_ACCEPTED = "transcription.accepted"
EVENT_TRANSCRIPTION_COMPLETED = "transcription.completed"
EVENT_TRANSCRIPTION_DISCARDED = "transcription.discarded"
EVENT_TRANSCRIPTION_FAILED = "transcription.failed"
EVENT_WATCHDOG_WARNING = "watchdog.warning"
EVENT_WAKEWORD_DETECTED = "wakeword.detected"
EVENT_WAKEWORD_AVAILABILITY_CHANGED = "wakeword.availability_changed"
EVENT_SETTINGS_CHANGED = "settings.changed"

#: Every canonical v2 domain event name of the frozen contract.
EVENT_TYPES = (
    EVENT_ACTIVATION_STARTED,
    EVENT_ACTIVATION_PHASE_CHANGED,
    EVENT_ACTIVATION_INPUT_CLOSED,
    EVENT_ACTIVATION_COMPLETED,
    EVENT_ACTIVATION_CANCELLED,
    EVENT_ACTIVATION_FAILED,
    EVENT_ACTIVATION_TRIGGER_SUPPRESSED,
    EVENT_SEGMENT_RECORDING_STARTED,
    EVENT_SEGMENT_RECORDING_ENDED,
    EVENT_TRANSCRIPTION_ACCEPTED,
    EVENT_TRANSCRIPTION_COMPLETED,
    EVENT_TRANSCRIPTION_DISCARDED,
    EVENT_TRANSCRIPTION_FAILED,
    EVENT_WATCHDOG_WARNING,
    EVENT_WAKEWORD_DETECTED,
    EVENT_WAKEWORD_AVAILABILITY_CHANGED,
    EVENT_SETTINGS_CHANGED,
)

#: Diagnostic events that do not advance the visible domain state, so they do
#: not raise ``stateVersion`` (contract 6.3 / canonical prompt 13).
NON_STATE_EVENTS = frozenset({
    EVENT_WATCHDOG_WARNING,
    EVENT_ACTIVATION_TRIGGER_SUPPRESSED,
})


# -- websocket close codes ---------------------------------------------------

CLOSE_INVALID_HANDSHAKE = 4400
CLOSE_PROTOCOL_INCOMPATIBLE = 4406
CLOSE_HANDSHAKE_TIMEOUT = 4408
CLOSE_SESSION_REJECTED = 4409
CLOSE_INTERNAL_ERROR = 1011

#: Seconds a v2 connection may stay silent before ``hello`` arrives.
DEFAULT_HANDSHAKE_TIMEOUT_SECONDS = 10.0


# -- canonical ids -----------------------------------------------------------

def new_canonical_id():
    """A fresh canonical UUID string, hyphenated, as the frozen schema wants."""
    return str(uuid.uuid4())


def is_canonical_uuid(value):
    """Whether ``value`` is a hyphenated canonical UUID string.

    A compact 32-character hex form is deliberately refused: accepting it here
    would invite exactly the boundary reformatting K1 forbids. Upper case is
    refused as well - two spellings of one UUID would be two replay keys for
    one logical command.
    """
    if not isinstance(value, str) or len(value) != 36:
        return False
    try:
        parsed = uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        return False
    return str(parsed) == value


def normalize_command_id(value):
    """The canonical ``commandId`` string, or ``None`` when unusable.

    The client owns ``commandId``, so it is validated - never rewritten. A
    value that is not a canonical UUID has no v2 identity at all.
    """
    if not is_canonical_uuid(value):
        return None
    return value
