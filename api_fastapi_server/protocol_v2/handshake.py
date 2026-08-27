"""The v2 ``hello`` handshake.

A ``/ws/v2`` connection is technically accepted but has **no** admitted
session yet. The first client text message must be ``hello``; nothing else -
no audio, no manual trigger, no wake-word detection, no domain command - is
possible before ``hello.accepted``.

Three refusal stages, in this order:

1. **Envelope** - the message is not a parseable ``hello`` (bad JSON, wrong
   type, missing or ill-typed mandatory field). Closes with ``4400`` and sends
   nothing that could look like a session.
2. **Version** - the envelope is fine but no protocol version is shared. Sends
   ``protocol.incompatible`` and closes with ``4406``.
3. **Session** - protocol and envelope are fine but the requested session is
   inadmissible (no trigger source, wake word enabled without a selection,
   unknown wake word id, admission failure). Sends ``session.rejected`` with
   machine-readable ``errors[]`` and closes with ``4409``.

No ``sessionId`` exists in any of the three cases, and no domain session is
half-built.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from . import schema


@dataclass(frozen=True)
class ParsedHello:
    client_version: str
    client_commit: str
    client_run_id: str
    supported_protocol_versions: Tuple[int, ...]
    manual_trigger: bool
    wake_word_trigger: bool
    wake_word_ids: Tuple[str, ...]
    suppress_manual: bool
    suppress_wake_word: bool


@dataclass(frozen=True)
class HandshakeRefusal:
    close_code: int
    message: Optional[Dict[str, Any]] = None
    reason: str = ""


@dataclass(frozen=True)
class HandshakeResult:
    hello: Optional[ParsedHello] = None
    protocol_version: Optional[int] = None
    refusal: Optional[HandshakeRefusal] = None
    errors: Tuple[Dict[str, Any], ...] = ()

    @property
    def accepted(self):
        return self.refusal is None


def _server_identity(server_version, server_commit):
    return {
        "serverVersion": server_version,
        "serverCommit": server_commit,
        "supportedProtocolVersions": list(schema.SUPPORTED_PROTOCOL_VERSIONS),
    }


def protocol_incompatible(reason, *, server_version, server_commit):
    payload = {"type": schema.PROTOCOL_INCOMPATIBLE, "reason": reason}
    payload.update(_server_identity(server_version, server_commit))
    return payload


def session_rejected(reason, errors, *, server_version, server_commit):
    payload = {"type": schema.SESSION_REJECTED, "reason": reason}
    payload.update(_server_identity(server_version, server_commit))
    payload["errors"] = [dict(item) for item in errors]
    return payload


def parse_hello(payload, *, server_version, server_commit):
    """Validates one ``hello`` envelope and negotiates the protocol version."""
    if not isinstance(payload, dict) or payload.get("type") != schema.HELLO:
        return HandshakeResult(refusal=HandshakeRefusal(
            close_code=schema.CLOSE_INVALID_HANDSHAKE,
            reason="first_message_must_be_hello",
        ))

    versions = payload.get("supportedProtocolVersions")
    if (
        not isinstance(versions, list)
        or not versions
        or any(isinstance(item, bool) or not isinstance(item, int)
               for item in versions)
    ):
        return HandshakeResult(refusal=HandshakeRefusal(
            close_code=schema.CLOSE_INVALID_HANDSHAKE,
            reason="invalid_supported_protocol_versions",
        ))

    client_version = _non_empty_string(payload.get("clientVersion"))
    client_commit = _non_empty_string(payload.get("clientCommit"))
    if client_version is None or client_commit is None:
        return HandshakeResult(refusal=HandshakeRefusal(
            close_code=schema.CLOSE_INVALID_HANDSHAKE,
            reason="invalid_client_identity",
        ))

    client_run_id = payload.get("clientRunId")
    if not schema.is_canonical_uuid(client_run_id):
        return HandshakeResult(refusal=HandshakeRefusal(
            close_code=schema.CLOSE_INVALID_HANDSHAKE,
            reason="invalid_client_run_id",
        ))

    requested = payload.get("requestedSession")
    if not isinstance(requested, dict):
        return HandshakeResult(refusal=HandshakeRefusal(
            close_code=schema.CLOSE_INVALID_HANDSHAKE,
            reason="invalid_requested_session",
        ))
    trigger = requested.get("trigger")
    if (
        not isinstance(trigger, dict)
        or not isinstance(trigger.get("manual"), bool)
        or not isinstance(trigger.get("wakeWord"), bool)
    ):
        return HandshakeResult(refusal=HandshakeRefusal(
            close_code=schema.CLOSE_INVALID_HANDSHAKE,
            reason="invalid_requested_trigger",
        ))
    wake_word_ids = requested.get("wakeWordIds")
    if not isinstance(wake_word_ids, list) or any(
        not isinstance(item, str) or not item.strip()
        for item in wake_word_ids
    ):
        return HandshakeResult(refusal=HandshakeRefusal(
            close_code=schema.CLOSE_INVALID_HANDSHAKE,
            reason="invalid_wake_word_ids",
        ))

    suppression = payload.get("runtimeSuppression")
    if (
        not isinstance(suppression, dict)
        or not isinstance(suppression.get("manual"), bool)
        or not isinstance(suppression.get("wakeWord"), bool)
    ):
        return HandshakeResult(refusal=HandshakeRefusal(
            close_code=schema.CLOSE_INVALID_HANDSHAKE,
            reason="invalid_runtime_suppression",
        ))

    negotiated = negotiate(versions)
    if negotiated is None:
        return HandshakeResult(refusal=HandshakeRefusal(
            close_code=schema.CLOSE_PROTOCOL_INCOMPATIBLE,
            message=protocol_incompatible(
                "no_common_protocol_version",
                server_version=server_version,
                server_commit=server_commit,
            ),
            reason="no_common_protocol_version",
        ))

    hello = ParsedHello(
        client_version=client_version,
        client_commit=client_commit,
        client_run_id=client_run_id,
        supported_protocol_versions=tuple(versions),
        manual_trigger=bool(trigger["manual"]),
        wake_word_trigger=bool(trigger["wakeWord"]),
        wake_word_ids=tuple(wake_word_ids),
        suppress_manual=bool(suppression["manual"]),
        suppress_wake_word=bool(suppression["wakeWord"]),
    )
    return HandshakeResult(hello=hello, protocol_version=negotiated)


def negotiate(client_versions):
    """The highest version both sides support, or ``None``."""
    shared = [
        version for version in client_versions
        if version in schema.SUPPORTED_PROTOCOL_VERSIONS
    ]
    return max(shared) if shared else None


def validate_requested_session(hello, wake_word_port):
    """Session admission rules of the frozen contract.

    Returns the ``errors[]`` list; empty means admissible. A runtime
    suppression never replaces the selection: an unsuppressed wake word of the
    same client runtime must still have defined models.
    """
    errors, _selection = admit_requested_session(hello, wake_word_port)
    return errors


def admit_requested_session(hello, wake_word_port):
    """``(errors, selection)`` of one atomic session admission.

    The catalog is asked **once**, so the admitted selection and the errors
    describe exactly the same catalog snapshot; a concurrent catalog refresh
    can therefore never produce a half-validated session. ``selection`` is the
    internal artifact projection and is ``None`` whenever the session does not
    use wake words or was refused.
    """
    errors: List[Dict[str, Any]] = []
    selection = None
    if not hello.manual_trigger and not hello.wake_word_trigger:
        errors.append({
            "field": "requestedSession.trigger",
            "code": "activation_trigger_required",
            "message": (
                "Mindestens eine Triggerquelle muss konfiguriert sein."
            ),
        })
    if hello.wake_word_trigger and not hello.wake_word_ids:
        errors.append({
            "field": "requestedSession.wakeWordIds",
            "code": "wake_word_selection_required",
            "message": (
                "Bei aktivierter Wake-Word-Quelle muss mindestens eine "
                "Wake-Word-ID ausgewählt sein."
            ),
        })
    if not hello.wake_word_trigger and hello.wake_word_ids:
        errors.append({
            "field": "requestedSession.wakeWordIds",
            "code": "wake_word_selection_not_allowed",
            "message": (
                "Ohne aktivierte Wake-Word-Quelle darf keine Auswahl "
                "übergeben werden."
            ),
        })
    if hello.wake_word_trigger and hello.wake_word_ids:
        # AP-SRV-060: one atomic catalog admission. A single unknown, globally
        # disabled or unloadable id rejects the whole selection.
        selection, selection_errors = wake_word_port.resolve_selection(
            hello.wake_word_ids
        )
        errors.extend(selection_errors)
        if selection_errors:
            selection = None
    return errors, selection


def _non_empty_string(value):
    if not isinstance(value, str):
        return None
    return value if value.strip() else None
