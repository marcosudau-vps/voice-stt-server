"""Strict v2 command envelope and the domain-reason projection (K3/K4).

Two responsibilities, deliberately separated from the AP-SRV-030 command
authority:

1. :func:`parse_command` validates the **v2 envelope** before anything is
   dispatched. The frozen schema is stricter than the transport-neutral
   AP-SRV-030 parser: a client may only ever claim ``source=manual``, the
   deprecated ``extend`` alias does not exist, and ``source`` is forbidden on
   control actions. AP-SRV-030 keeps its v1 tolerance untouched; the strict
   rules live here.

2. :func:`map_domain_reason` projects one AP-SRV-030 decision reason onto one
   of the fifteen frozen ``command.ack`` result codes. The table is
   exhaustive: an unmapped known reason raises :class:`UnmappedDomainReason`
   so it fails visibly in tests instead of silently degrading to
   ``internal_error``.

Replay identity (K3)
--------------------

A command rejected by the v2 envelope keeps its replay identity. The rejection
is stored in the *same* session-scoped replay cache that AP-SRV-030 already
owns, so there is exactly one replay authority. The key is a deterministic,
type-stable freeze of the whole v2 payload minus ``commandId`` - in particular
it keeps ``source`` on control actions, because a forbidden ``source`` is part
of what makes that payload invalid and must not be normalised away by the
legacy v1 tolerance.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

from ..activation_commands import freeze_payload_value
from . import schema


class UnmappedDomainReason(LookupError):
    """A known domain reason without an explicit wire projection."""


@dataclass(frozen=True)
class ParsedCommand:
    """One transport payload after strict v2 envelope validation.

    ``command_id`` is ``None`` when no usable canonical ``commandId`` exists.
    Such a payload has no v2 identity and therefore receives no ack at all -
    the frozen contract promises exactly one ack per recognisable command
    *with a usable commandId*.

    ``rejection`` is already a frozen result code, never a domain reason.
    """

    type: Optional[str]
    command_id: Optional[str] = None
    payload_key: Tuple = ()
    rejection: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)

    @property
    def rejected(self):
        return self.rejection is not None


def freeze_payload(payload):
    """Deterministic, type-stable replay key of a whole v2 payload.

    ``commandId`` is the cache identity and therefore excluded. Every other
    field - including ``source`` on control actions - is part of the key, so
    two payloads that differ in any way cannot share one replay answer.
    """
    fields = {
        str(key): value
        for key, value in payload.items()
        if key != "commandId"
    }
    return ("protocol_v2_raw", freeze_payload_value(fields))


def _reject(payload, command_id, result):
    return ParsedCommand(
        type=payload.get("type") if isinstance(payload, dict) else None,
        command_id=command_id,
        payload_key=freeze_payload(payload) if isinstance(payload, dict) else (),
        rejection=result,
        payload=dict(payload) if isinstance(payload, dict) else {},
    )


def parse_command(payload, *, session_id):
    """Validates one v2 command envelope against the frozen schema.

    Returns ``None`` when the payload is not a recognisable v2 command at all
    (unknown or missing message type). The frozen schema forbids treating an
    unknown message type as a known state change, so such a payload is
    ignored rather than acknowledged.
    """
    if not isinstance(payload, dict):
        return None

    message_type = payload.get("type")
    if not isinstance(message_type, str) or message_type not in schema.COMMAND_TYPES:
        return None

    command_id = schema.normalize_command_id(payload.get("commandId"))
    if command_id is None:
        # No usable canonical identity: no replay slot and no ack.
        return ParsedCommand(
            type=message_type,
            command_id=None,
            payload_key=freeze_payload(payload),
            rejection=schema.RESULT_INVALID_PAYLOAD,
            payload=dict(payload),
        )

    version = payload.get("protocolVersion")
    if isinstance(version, bool) or version != schema.PROTOCOL_VERSION:
        return _reject(payload, command_id, schema.RESULT_INVALID_PAYLOAD)

    raw_session = payload.get("sessionId")
    if not schema.is_canonical_uuid(raw_session):
        return _reject(payload, command_id, schema.RESULT_INVALID_PAYLOAD)
    if raw_session != session_id:
        # A well formed but foreign/older session id is never reinterpreted as
        # a new session; it is refused without effect.
        return _reject(payload, command_id, schema.RESULT_STALE_SESSION)

    validator = _VALIDATORS[message_type]
    error = validator(payload)
    if error is not None:
        return _reject(payload, command_id, error)

    return ParsedCommand(
        type=message_type,
        command_id=command_id,
        payload_key=freeze_payload(payload),
        payload=dict(payload),
    )


# -- per-type field validation ------------------------------------------------

def _validate_activation_command(payload):
    action = payload.get("action")
    if action not in schema.ACTIVATION_ACTIONS:
        # ``extend`` is a v1 alias only; the canonical v2 parser has no legacy
        # exception.
        return schema.RESULT_INVALID_PAYLOAD

    has_source = "source" in payload
    has_activation_id = "activationId" in payload

    if action == schema.ACTIVATE:
        if has_activation_id:
            # ``activate`` opens a new activation and never addresses one.
            return schema.RESULT_INVALID_PAYLOAD
        source = payload.get("source")
        if not isinstance(source, str) or source not in schema.CLIENT_SOURCES:
            # ``wake_word`` is server-internal and can never be claimed here.
            return schema.RESULT_INVALID_PAYLOAD
        return None

    if has_source:
        return schema.RESULT_INVALID_PAYLOAD
    if not schema.is_canonical_uuid(payload.get("activationId")):
        return schema.RESULT_INVALID_PAYLOAD
    return None


def _validate_trigger_suppression(payload):
    for name in ("manual", "wakeWord"):
        if not isinstance(payload.get(name), bool):
            return schema.RESULT_INVALID_PAYLOAD
    return None


def _validate_audio_availability(payload):
    if not isinstance(payload.get("audioAvailable"), bool):
        return schema.RESULT_INVALID_PAYLOAD
    return None


def _validate_session_settings_patch(payload):
    revision = payload.get("baseSettingsRevision")
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 0:
        return schema.RESULT_INVALID_PAYLOAD
    changes = payload.get("changes")
    if not isinstance(changes, dict) or not changes:
        return schema.RESULT_INVALID_PAYLOAD
    return None


def _validate_snapshot_request(payload):
    return None


_VALIDATORS = {
    schema.ACTIVATION_COMMAND: _validate_activation_command,
    schema.TRIGGER_SUPPRESSION_SET: _validate_trigger_suppression,
    schema.AUDIO_AVAILABILITY_SET: _validate_audio_availability,
    schema.SESSION_SETTINGS_PATCH: _validate_session_settings_patch,
    schema.SESSION_SNAPSHOT_REQUEST: _validate_snapshot_request,
}


# -- domain reason projection (K4) --------------------------------------------

#: Every AP-SRV-030 reason that can reach a ``command.ack``, and the single
#: frozen result code it projects onto. The mapping is data, not logic: the
#: domain vocabulary stays intact internally, the wire stays closed.
DOMAIN_REASON_RESULTS = {
    # effective transitions
    "activated": schema.RESULT_APPLIED,
    "refreshed": schema.RESULT_APPLIED,
    "finished": schema.RESULT_APPLIED,
    "cancelled": schema.RESULT_APPLIED,
    "input_closing": schema.RESULT_APPLIED,
    "applied": schema.RESULT_APPLIED,
    # successful idempotent no-ops
    "no_change": schema.RESULT_NO_CHANGE,
    "already_idle": schema.RESULT_NO_CHANGE,
    "already_recording": schema.RESULT_NO_CHANGE,
    # phase / identity refusals
    "activation_locked": schema.RESULT_ACTIVATION_LOCKED,
    "not_active": schema.RESULT_NOT_ACTIVE,
    "invalid_phase": schema.RESULT_INVALID_PHASE,
    "closing_input": schema.RESULT_CLOSING_INPUT,
    "stale_activation": schema.RESULT_STALE_ACTIVATION,
    "command_id_conflict": schema.RESULT_COMMAND_ID_CONFLICT,
    # policy refusals
    "audio_unavailable": schema.RESULT_AUDIO_UNAVAILABLE,
    "trigger_disabled": schema.RESULT_TRIGGER_SUPPRESSED,
    "trigger_suppressed": schema.RESULT_TRIGGER_SUPPRESSED,
    # payload refusals of the AP-SRV-030 parser
    "invalid_payload": schema.RESULT_INVALID_PAYLOAD,
    "invalid_action": schema.RESULT_INVALID_PAYLOAD,
    "invalid_source": schema.RESULT_INVALID_PAYLOAD,
    "invalid_command_id": schema.RESULT_INVALID_PAYLOAD,
    "missing_command_id": schema.RESULT_INVALID_PAYLOAD,
    # Session states a v2 connection cannot reach: admission requires the
    # controlled activation mode and starts streaming atomically, and after a
    # session close the v2 transport is gone before a command can be answered.
    # They are mapped explicitly rather than falling through.
    "controlled_activation_disabled": schema.RESULT_INTERNAL_ERROR,
    "session_closed": schema.RESULT_INTERNAL_ERROR,
    "stream_not_started": schema.RESULT_INTERNAL_ERROR,
}

#: AP-SRV-030 reasons that describe recorder/timer transitions and never
#: appear in an ack. Listed so the exhaustiveness test can tell "not mapped
#: on purpose" from "forgotten".
NON_COMMAND_REASONS = frozenset({
    "closing_recovery_due",
    "followup_started",
    "input_closed",
    "not_closing_input",
    "not_due",
    "not_expirable",
    "recording_started",
    "reset",
    "stale_timer",
    "watchdog_warning",
})


def map_domain_reason(reason):
    """The frozen result code for one AP-SRV-030 reason.

    Raises :class:`UnmappedDomainReason` for anything not in the table, so a
    forgotten reason is a loud test failure rather than a silent
    ``internal_error`` on the wire.
    """
    try:
        return DOMAIN_REASON_RESULTS[reason]
    except KeyError:
        raise UnmappedDomainReason(reason) from None


def is_accepted(result):
    """``accepted`` for one result code - true only for the two frozen ones."""
    return result in schema.ACCEPTED_RESULTS
