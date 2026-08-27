"""Command identity, payload validation and replay accounting.

This module owns everything that happens *around* an activation command and
deliberately nothing that happens inside the state machine:

* :func:`prepare_activation_command` turns one transport payload into an
  immutable envelope (:class:`PreparedActivationCommand`) with a deterministic
  replay key - even when the payload itself is fachlich rejected.
* :class:`CommandReplayCache` answers whether a ``commandId`` has been seen
  before, and whether it came back with the same payload.

Two levels are deliberate (AP-SRV-030 C2):

1. **Replay-capable envelope.** As soon as a usable, non-empty string
   ``commandId`` exists, a deterministic payload key is created. This happens
   even when ``action``, ``source`` or ``activationId`` are fachlich invalid,
   so a rejected command does not lose its replay identity (F3).
2. **Semantic command validation.** Only afterwards are the action, the
   source rules, the activation-id rules and the field combination checked.

Neither level has a side effect on the foreground state. The phase matrix, the
activation-id validation and every transition stay in
:mod:`api_fastapi_server.activation`, which is the only place that holds the
foreground lock.

For **control** commands (``refresh|finish|cancel``) the ``source`` field is
not semantic. A legacy ``source=manual`` still sent during the v1 transition is
tolerated and ignored; it never becomes part of the replay key and never acts
as a control authorisation. ``activationId`` is mandatory for controls.
"""

from dataclasses import dataclass
from typing import Optional
import threading


ACTIVATE = "activate"
REFRESH = "refresh"
FINISH = "finish"
CANCEL = "cancel"

#: The four canonical semantic actions of the frozen contract.
ACTIVATION_ACTIONS = (ACTIVATE, REFRESH, FINISH, CANCEL)

#: Actions that address an already observed activation.
CONTROL_ACTIONS = frozenset({REFRESH, FINISH, CANCEL})

#: Deprecated v1 spelling of :data:`REFRESH`. It is accepted so that a client
#: built against the AP-SRV-010 baseline keeps working, but it now carries the
#: contract refresh semantics - the additive ``extensionSeconds`` behaviour is
#: gone. The alias itself is removed with the legacy cut in AP-SRV-070.
ACTION_ALIASES = {"extend": REFRESH}

MANUAL_SOURCE = "manual"
WAKE_WORD_SOURCE = "wake_word"
ACTIVATION_SOURCES = (MANUAL_SOURCE, WAKE_WORD_SOURCE)


@dataclass(frozen=True)
class ActivationCommand:
    """One semantic command, independent of its transport form.

    ``source`` is ``None`` for control commands: the field is not part of the
    semantic control contract any more. The v1 transport may still send it; it
    is tolerated and ignored there.
    """

    command_id: str
    action: str
    source: Optional[str] = None
    activation_id: Optional[str] = None

    @property
    def payload_key(self):
        """Everything that makes two commands semantically the same.

        ``activate`` is identified by ``(action, source)``; controls are
        identified by ``(action, activationId)`` and deliberately do **not**
        contain ``source``, so a legacy source field can never turn a replay
        into a conflict (F6). ``extend`` is normalised to ``refresh`` before
        the key is built, which keeps an alias replay a replay.
        """
        if self.action == ACTIVATE:
            return ("semantic", "activate", self.source)
        return ("semantic", "control", self.action, self.activation_id)


class CommandRejected(Exception):
    """A command that cannot be turned into an :class:`ActivationCommand`.

    Kept as a compatibility helper for code that predates the envelope model;
    the preferred API is :func:`prepare_activation_command`, which never
    raises and exposes both the replay key and the rejection reason.
    """

    def __init__(self, reason, command_id=""):
        super().__init__(reason)
        self.reason = reason
        self.command_id = command_id


@dataclass(frozen=True)
class PreparedActivationCommand:
    """The two-level result of parsing one transport payload.

    * ``command_id`` - the usable trimmed string, or ``""`` when no usable id
      exists (then the command is keyless and must not occupy the cache).
    * ``payload_key`` - the deterministic replay key. For a valid command it is
      the semantic key; for a rejected command with a usable ``commandId`` it
      is a type-stable freeze of the raw payload, so the rejection itself is
      replay- and conflict-safe (F3).
    * ``command`` - the semantic :class:`ActivationCommand`, or ``None``.
    * ``rejection_reason`` - the machine-readable reason, or ``None``.
    """

    command_id: str
    payload_key: tuple
    command: Optional[ActivationCommand] = None
    rejection_reason: Optional[str] = None


def _freeze_value(value):
    """Recursively turns a raw payload value into a hashable, type-stable form.

    The representation keeps the *type* of every value (``bool`` is distinct
    from ``int``, a list from a tuple), never relies on :func:`repr` and never
    depends on object addresses. Dictionaries are sorted by key so a later
    transport re-serialisation cannot reorder the identity.
    """
    if isinstance(value, dict):
        return tuple(
            ("dict", _freeze_value(str(key)), _freeze_value(item))
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        )
    if isinstance(value, (list, tuple)):
        kind = "list" if isinstance(value, list) else "tuple"
        return (kind, tuple(_freeze_value(item) for item in value))
    if isinstance(value, bool):
        return ("bool", value)
    if isinstance(value, int):
        return ("int", value)
    if isinstance(value, float):
        return ("float", value)
    if isinstance(value, str):
        return ("str", value)
    if value is None:
        return ("none",)
    return ("other", type(value).__name__)


def _raw_payload_key(data, *, control):
    """Deterministic replay key of a rejected payload.

    The ``commandId`` is the cache identity and therefore not part of the
    payload key. For control actions the legacy ``source`` field is ignored
    here as well, so a change of that field alone cannot create a conflict.
    """
    fields = {
        str(key): value
        for key, value in data.items()
        if key != "commandId" and not (
            control and key == "source"
        )
    }
    return ("raw", _freeze_value(fields))


def _normalized_action(data):
    raw_action = data.get("action")
    if raw_action is not None and not isinstance(raw_action, str):
        return None
    action = str(raw_action or "").strip().lower()
    return ACTION_ALIASES.get(action, action)


def prepare_activation_command(data):
    """Two-level parse: replay envelope first, semantic validation second.

    Never raises. Returns a :class:`PreparedActivationCommand` whose
    ``payload_key`` can be used for the session replay cache even when the
    command is rejected - a usable ``commandId`` always stays occupied (F3).
    """
    if not isinstance(data, dict):
        return PreparedActivationCommand(
            command_id="",
            payload_key=(),
            rejection_reason="invalid_payload",
        )

    raw_command_id = data.get("commandId")
    if raw_command_id is not None and not isinstance(raw_command_id, str):
        return PreparedActivationCommand(
            command_id="",
            payload_key=(),
            rejection_reason="invalid_command_id",
        )
    command_id = str(raw_command_id or "").strip()
    if not command_id:
        return PreparedActivationCommand(
            command_id="",
            payload_key=(),
            rejection_reason="missing_command_id",
        )

    action = _normalized_action(data)
    if action not in ACTIVATION_ACTIONS:
        return PreparedActivationCommand(
            command_id=command_id,
            payload_key=_raw_payload_key(data, control=False),
            rejection_reason="invalid_action",
        )

    if action == ACTIVATE:
        raw_source = data.get("source")
        if raw_source is not None and not isinstance(raw_source, str):
            return PreparedActivationCommand(
                command_id=command_id,
                payload_key=_raw_payload_key(data, control=False),
                rejection_reason="invalid_source",
            )
        source = str(raw_source or "").strip().lower()
        if source not in ACTIVATION_SOURCES:
            return PreparedActivationCommand(
                command_id=command_id,
                payload_key=_raw_payload_key(data, control=False),
                rejection_reason="invalid_source",
            )
        if data.get("activationId") is not None:
            # ``activate`` opens a new activation and must never address one.
            return PreparedActivationCommand(
                command_id=command_id,
                payload_key=_raw_payload_key(data, control=False),
                rejection_reason="invalid_payload",
            )
        command = ActivationCommand(
            command_id=command_id,
            action=action,
            source=source,
        )
        return PreparedActivationCommand(
            command_id=command_id,
            payload_key=command.payload_key,
            command=command,
        )

    # Control command: ``activationId`` is mandatory; ``source`` is ignored.
    raw_activation_id = data.get("activationId")
    if raw_activation_id is not None and not isinstance(raw_activation_id, str):
        return PreparedActivationCommand(
            command_id=command_id,
            payload_key=_raw_payload_key(data, control=True),
            rejection_reason="invalid_payload",
        )
    activation_id = str(raw_activation_id or "").strip()
    if not activation_id:
        return PreparedActivationCommand(
            command_id=command_id,
            payload_key=_raw_payload_key(data, control=True),
            rejection_reason="invalid_payload",
        )
    command = ActivationCommand(
        command_id=command_id,
        action=action,
        activation_id=activation_id,
    )
    return PreparedActivationCommand(
        command_id=command_id,
        payload_key=command.payload_key,
        command=command,
    )


def parse_activation_command(data):
    """Compatibility wrapper around :func:`prepare_activation_command`.

    Raises :class:`CommandRejected` for every rejection, carrying the reason
    and the still-usable ``commandId``.
    """
    prepared = prepare_activation_command(data)
    if prepared.command is not None:
        return prepared.command
    raise CommandRejected(prepared.rejection_reason, prepared.command_id)


MISS = "miss"
REPLAY = "replay"
CONFLICT = "conflict"


@dataclass(frozen=True)
class ReplayLookup:
    state: str
    result: object = None


class CommandReplayCache:
    """Session-scoped idempotency for ``commandId``.

    The contract requires the cache to hold for at least the whole session, so
    it is not trimmed while the session lives; :meth:`clear` is called when the
    session is torn down. A cache entry never re-applies anything - it only
    hands back the answer that was produced the first time, which is why a
    replay cannot resurrect a command against a newer activation.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._entries = {}

    def __len__(self):
        with self._lock:
            return len(self._entries)

    def lookup(self, command_id, payload_key):
        with self._lock:
            entry = self._entries.get(command_id)
        if entry is None:
            return ReplayLookup(MISS)
        stored_key, stored_result = entry
        if stored_key != payload_key:
            return ReplayLookup(CONFLICT)
        return ReplayLookup(REPLAY, stored_result)

    def store(self, command_id, payload_key, result):
        with self._lock:
            self._entries.setdefault(command_id, (payload_key, result))

    def clear(self):
        with self._lock:
            self._entries.clear()