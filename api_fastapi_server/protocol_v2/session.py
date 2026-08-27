"""Protocol-level session state for one accepted v2 connection.

This component owns the **wire** identity of a session and nothing else:

* the negotiated ``protocolVersion`` and the canonical ``sessionId``;
* ``stateVersion`` - the monotone counter of visible domain changes;
* ``eventSeq``/``eventId`` - the logical identity of every projected event;
* ``settingsRevision`` as mirrored from the settings port;
* the registry that makes a transport retry re-send the *same* logical event.

It explicitly does **not** own the activation phase, any deadline, the trigger
lock, the segment ledger, the wake latch, settings domain state or recorder
state. Those authorities stay in :mod:`api_fastapi_server.activation`,
:mod:`api_fastapi_server.segment_ledger` and the session itself; this class
only numbers what they already decided.

``stateVersion`` therefore is not ``ActivationController.version``: a ledger
terminal is a visible change that the controller never sees, and a refreshed
deadline that did not move is a controller no-op that must not bump the wire
version.
"""

import threading
import time

from . import schema


class ProtocolSessionState:
    """Wire-state versioning, event sequencing and snapshot consistency."""

    def __init__(
        self,
        session_id,
        *,
        protocol_version=schema.PROTOCOL_VERSION,
        settings_revision=0,
        id_factory=None,
        clock=None,
    ):
        if not schema.is_canonical_uuid(session_id):
            raise ValueError("sessionId muss eine kanonische UUID sein")
        self.session_id = session_id
        self.protocol_version = int(protocol_version)
        self._lock = threading.RLock()
        self._id_factory = id_factory or schema.new_canonical_id
        self._clock = clock or time.time
        self._state_version = 0
        self._settings_revision = int(settings_revision)
        self._last_event_seq = 0
        #: logical key -> already minted envelope, so a retry cannot mint a
        #: second identity for one logical event.
        self._minted = {}

    # -- observable counters -------------------------------------------------

    @property
    def state_version(self):
        with self._lock:
            return self._state_version

    @property
    def last_event_seq(self):
        with self._lock:
            return self._last_event_seq

    @property
    def settings_revision(self):
        with self._lock:
            return self._settings_revision

    def set_settings_revision(self, revision):
        """Mirrors a confirmed settings revision from the settings port."""
        with self._lock:
            revision = int(revision)
            if revision == self._settings_revision:
                return False
            self._settings_revision = revision
            return True

    def versions(self):
        """A consistent ``(stateVersion, settingsRevision)`` pair."""
        with self._lock:
            return self._state_version, self._settings_revision

    # -- event identity ------------------------------------------------------

    def mint_event(self, event_type, *, logical_key=None, state_change=None,
                   occurred_at_unix_ms=None):
        """Assigns the logical identity of one domain event.

        ``logical_key`` identifies the *logical* occurrence. Calling this twice
        with the same key returns the identical envelope - a transport retry
        re-sends an event, it does not create a new one. ``None`` means the
        caller guarantees a fresh occurrence.

        ``state_change`` decides whether ``stateVersion`` advances. It defaults
        to the frozen classification: every canonical domain event is a visible
        change except the diagnostic ones.
        """
        if state_change is None:
            state_change = event_type not in schema.NON_STATE_EVENTS
        with self._lock:
            if logical_key is not None:
                existing = self._minted.get(logical_key)
                if existing is not None:
                    return dict(existing)

            if state_change:
                self._state_version += 1
            self._last_event_seq += 1
            envelope = {
                "type": event_type,
                "protocolVersion": self.protocol_version,
                "sessionId": self.session_id,
                "eventId": self._id_factory(),
                "eventSeq": self._last_event_seq,
                "stateVersion": self._state_version,
                "occurredAtUnixMs": (
                    int(round(self._clock() * 1000))
                    if occurred_at_unix_ms is None
                    else int(occurred_at_unix_ms)
                ),
            }
            if logical_key is not None:
                self._minted[logical_key] = envelope
            return dict(envelope)

    def minted_event(self, logical_key):
        """The already minted envelope for ``logical_key``, or ``None``."""
        with self._lock:
            existing = self._minted.get(logical_key)
            return None if existing is None else dict(existing)

    def forget_event(self, logical_key):
        """Drops a minted identity. Only for events that never became real."""
        with self._lock:
            return self._minted.pop(logical_key, None) is not None
