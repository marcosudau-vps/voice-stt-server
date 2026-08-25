"""Command identity, payload validation and replay accounting.

This module owns everything that happens *around* an activation command and
deliberately nothing that happens inside the state machine:

* :func:`parse_activation_command` turns one transport payload into an
  immutable :class:`ActivationCommand` or a machine-readable rejection reason.
* :class:`CommandReplayCache` answers whether a ``commandId`` has been seen
  before, and whether it came back with the same payload.

Neither has a side effect on the foreground state. The phase matrix, the
activation-id validation and every transition stay in
:mod:`api_fastapi_server.activation`, which is the only place that holds the
foreground lock. Keeping the split this way is what makes "a replay has no
second effect" a property of the code rather than of a review.

The public wire form of these commands (protocol v2, ``activation.command``
and ``command.ack``) belongs to AP-SRV-040. This layer is the server-internal
command/policy surface that the current v1 ``trigger`` message feeds.
"""

from dataclasses import dataclass
import threading
from typing import Optional


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
    """One logical activation command, independent of its transport form."""

    command_id: str
    action: str
    source: str
    activation_id: Optional[str] = None

    @property
    def payload_key(self):
        """Everything that makes two commands semantically the same.

        A replay is only a replay if every semantic field matches. The
        transport spelling does not take part: ``extend`` and ``refresh``
        normalise to the same action, so an alias replay is still a replay and
        not a conflict.
        """
        return (self.action, self.source, self.activation_id)


class CommandRejected(Exception):
    """A command that cannot be turned into an :class:`ActivationCommand`."""

    def __init__(self, reason, command_id=""):
        super().__init__(reason)
        self.reason = reason
        self.command_id = command_id


def parse_activation_command(data):
    """Validates one transport payload.

    Raises :class:`CommandRejected` with the machine-readable reason and the
    ``commandId`` that could still be recovered, so that even a rejection stays
    correlated.
    """
    if not isinstance(data, dict):
        raise CommandRejected("invalid_payload")

    raw_command_id = data.get("commandId")
    if raw_command_id is not None and not isinstance(raw_command_id, str):
        raise CommandRejected("invalid_command_id")
    command_id = str(raw_command_id or "").strip()
    if not command_id:
        raise CommandRejected("missing_command_id")

    raw_action = data.get("action")
    if raw_action is not None and not isinstance(raw_action, str):
        raise CommandRejected("invalid_action", command_id)
    action = str(raw_action or "").strip().lower()
    action = ACTION_ALIASES.get(action, action)
    if action not in ACTIVATION_ACTIONS:
        raise CommandRejected("invalid_action", command_id)

    raw_source = data.get("source")
    if raw_source is not None and not isinstance(raw_source, str):
        raise CommandRejected("invalid_source", command_id)
    source = str(raw_source or "").strip().lower()
    if source not in ACTIVATION_SOURCES:
        raise CommandRejected("invalid_source", command_id)

    raw_activation_id = data.get("activationId")
    if raw_activation_id is not None and not isinstance(raw_activation_id, str):
        raise CommandRejected("invalid_payload", command_id)
    activation_id = str(raw_activation_id or "").strip() or None
    if action == ACTIVATE and activation_id is not None:
        # ``activate`` opens a new activation and must never address one.
        raise CommandRejected("invalid_payload", command_id)

    return ActivationCommand(
        command_id=command_id,
        action=action,
        source=source,
        activation_id=activation_id,
    )


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
