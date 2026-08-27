"""The ``/ws/v2`` connection driver.

One :class:`ProtocolV2Connection` is the wire/session/projection layer of one
v2 WebSocket connection. It is deliberately transport agnostic: outbound
payloads go into a thread-safe queue that the endpoint drains, so the whole
protocol can be driven synchronously in tests without a socket.

Ownership
---------

The connection owns the protocol: handshake sequencing, session admission,
strict envelope validation, ack projection, event projection and the snapshot.
Every domain decision stays where AP-SRV-020/030 put it:

* the phase matrix, the trigger lock, the deadlines and the input close belong
  to :class:`~api_fastapi_server.activation.ActivationController`;
* the ``commandId`` replay identity belongs to the session's one
  :class:`~api_fastapi_server.activation_commands.CommandReplayCache` - this
  layer uses that same cache instead of opening a second one;
* the accepted/terminal accounting belongs to the
  :class:`~api_fastapi_server.segment_ledger.SegmentLedger`;
* the exactly-once input-close record belongs to the AP-SRV-030 close seam,
  which this layer *binds* through the single lifecycle funnel.

Replay routing
--------------

A command that the strict v2 envelope refuses never reaches the domain, so the
connection stores that refusal in the shared replay cache itself, keyed by a
type-stable freeze of the whole v2 payload. A command that passes the envelope
is answered by the domain, which stores its own semantic key. Both live in one
cache under one ``commandId``, so a payload change of either kind is a
``command_id_conflict``.

Because a replay must return the *original* version values, the connection
also memoises the v2 ack it produced for a ``commandId`` and returns that
memo verbatim when the domain reports a replay.
"""

import json
import logging
import queue
import threading

from ..activation_commands import CONFLICT, REPLAY
from . import commands as command_layer
from . import events as event_layer
from . import handshake as handshake_layer
from . import identity, ports, schema, snapshot as snapshot_layer
from ..settings_control import POLICY_EVENT_ORDER
from .session import ProtocolSessionState

LOGGER = logging.getLogger(__name__)


class ProtocolV2Connection:
    """Protocol state machine of one v2 connection."""

    def __init__(
        self,
        service,
        *,
        client_id=None,
        server_version=None,
        server_commit=None,
        handshake_timeout=None,
    ):
        self.service = service
        self.client_id = client_id
        self.server_version = server_version or identity.server_version()
        self.server_commit = server_commit or identity.server_commit()
        # Read at construction time, not bound as a default argument, so the
        # frozen timeout stays configurable and testable.
        self.handshake_timeout = (
            schema.DEFAULT_HANDSHAKE_TIMEOUT_SECONDS
            if handshake_timeout is None
            else handshake_timeout
        )

        self.outbound = queue.Queue()
        self._sink = None
        self._lock = threading.RLock()
        # One session-local linearization point from event minting through the
        # thread-safe sink/queue hand-off. The asynchronous WebSocket writer
        # runs only after this lock has been released.
        self._event_dispatch_lock = threading.RLock()
        self._closed = False
        self._close_code = None

        self.session = None
        self.state = None
        self.projector = None
        self.settings_port = None
        self.wake_word_port = ports.WakeWordPort(service)
        self.hello = None
        #: commandId -> the v2 ack that was answered first.
        self._ack_memo = {}
        #: (activationId, activationSequence) -> the stateVersion that made the
        #: entry into ``closing_input`` visible. One closing entry advances the
        #: version once, even if a failed close is retried by the recovery.
        self._closing_versions = {}

    # -- outbound ------------------------------------------------------------

    @property
    def accepted(self):
        return self.state is not None

    @property
    def closed(self):
        with self._lock:
            return self._closed

    @property
    def close_code(self):
        with self._lock:
            return self._close_code

    def set_sink(self, sink):
        """Routes outbound payloads to a transport instead of the test queue.

        The sink is called from domain threads as well, so it has to be
        thread-safe; the endpoint hands in a loop-safe scheduler. ``None`` as
        the payload means "the connection wants to close".
        """
        with self._lock:
            self._sink = sink

    def send(self, payload):
        with self._lock:
            if self._closed:
                return False
            sink = self._sink
        if sink is None:
            self.outbound.put(payload)
        else:
            sink(payload)
        return True

    def request_close(self, code):
        with self._lock:
            if self._closed:
                return False
            self._closed = True
            self._close_code = int(code)
            sink = self._sink
        # Wakes a blocked writer so it can perform the close.
        if sink is None:
            self.outbound.put(None)
        else:
            sink(None)
        return True

    def drain(self):
        """Every queued outbound payload. Test and writer helper."""
        payloads = []
        while True:
            try:
                item = self.outbound.get_nowait()
            except queue.Empty:
                break
            if item is not None:
                payloads.append(item)
        return payloads

    # -- inbound -------------------------------------------------------------

    def handle_text(self, raw):
        """One inbound text frame."""
        if not self.accepted:
            return self._handle_handshake(raw)
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError):
            # A rejected command never closes the session, and an unparseable
            # frame is not a recognisable command at all.
            LOGGER.debug("Unparsebarer v2-Frame für %s verworfen", self._session_id())
            return None
        return self._handle_command(payload)

    def handle_binary(self, data):
        """One inbound audio frame. Forbidden before ``hello.accepted``."""
        if not self.accepted:
            self.request_close(schema.CLOSE_INVALID_HANDSHAKE)
            return False
        from ..protocol import AudioPacketError, decode_audio_packet

        try:
            accepted, _warning = self.session.ingest_audio_packet(
                decode_audio_packet(data)
            )
        except AudioPacketError:
            LOGGER.debug("Ungültiges v2-Audiopaket für %s", self._session_id())
            return False
        except Exception:
            LOGGER.exception("v2-Audiopaket konnte nicht verarbeitet werden")
            return False
        return bool(accepted)

    def close_session(self):
        """Tears the domain session down when the connection ends."""
        session = self.session
        if session is None:
            return
        try:
            session.set_protocol_observer(None)
        except Exception:
            LOGGER.debug("v2-Observer konnte nicht gelöst werden", exc_info=True)
        try:
            self.service.remove_session(session.session_id)
        except Exception:
            LOGGER.exception("v2-Session konnte nicht entfernt werden")
        finally:
            self.session = None

    # -- handshake -----------------------------------------------------------

    def _handle_handshake(self, raw):
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError):
            self.request_close(schema.CLOSE_INVALID_HANDSHAKE)
            return None

        result = handshake_layer.parse_hello(
            payload,
            server_version=self.server_version,
            server_commit=self.server_commit,
        )
        if not result.accepted:
            if result.refusal.message is not None:
                self.send(result.refusal.message)
            self.request_close(result.refusal.close_code)
            return None

        errors = handshake_layer.validate_requested_session(
            result.hello, self.wake_word_port
        )
        if errors:
            return self._reject_session("invalid_requested_session", errors)

        try:
            session = self._admit(result.hello)
        except Exception as exc:  # noqa: BLE001 - classified below
            return self._admission_failure(exc)

        if session is None:
            return self._reject_session("session_limit_reached", [{
                "field": "requestedSession",
                "code": "session_limit_reached",
                "message": "Der Server hat das konfigurierte Sitzungslimit erreicht.",
            }])

        self._activate_session(session, result)
        return session

    def _admit(self, hello):
        from ..server import SessionActivationRequest, SessionWakeWordRequest

        wake_word_request = SessionWakeWordRequest(
            enabled=bool(hello.wake_word_trigger),
            values=(
                (("wakeWords", ",".join(hello.wake_word_ids)),)
                if hello.wake_word_ids
                else ()
            ),
        )
        activation_request = SessionActivationRequest(
            manual_enabled=bool(hello.manual_trigger),
            wake_word_enabled=bool(hello.wake_word_trigger),
        )
        return self.service.admit_session(
            schema.new_canonical_id(),
            wake_word_request=wake_word_request,
            client_id=self.client_id,
            activation_request=activation_request,
            canonical_ids=True,
        )

    def _admission_failure(self, exc):
        from ..server import SessionConfigurationError

        if isinstance(exc, SessionConfigurationError):
            return self._reject_session("invalid_requested_session", [{
                "field": exc.details.get("field", "requestedSession"),
                "code": exc.code,
                "message": exc.message,
            }])
        LOGGER.exception("v2-Sessionadmission ist unerwartet fehlgeschlagen")
        self.request_close(schema.CLOSE_INTERNAL_ERROR)
        return None

    def _reject_session(self, reason, errors):
        self.send(handshake_layer.session_rejected(
            reason,
            errors,
            server_version=self.server_version,
            server_commit=self.server_commit,
        ))
        self.request_close(schema.CLOSE_SESSION_REJECTED)
        return None

    def _activate_session(self, session, result):
        """Builds the protocol state and releases domain traffic."""
        self.session = session
        self.hello = result.hello
        self.settings_port = ports.SettingsPort(session)
        self.state = ProtocolSessionState(
            session.session_id,
            protocol_version=result.protocol_version,
            settings_revision=self.settings_port.revision,
        )
        self.projector = event_layer.EventProjector(self.state)

        controller = session.activation_controller()
        if controller is not None:
            controller.set_runtime_suppression(
                manual=result.hello.suppress_manual,
                wake_word=result.hello.suppress_wake_word,
            )
        session.set_protocol_observer(self._on_domain_event)
        # A v2 session has no ``start`` command: the audio path is part of the
        # admitted session, so it is opened atomically with the acceptance.
        session.start_streaming()

        payload = self._snapshot_payload()
        self.send({
            "type": schema.HELLO_ACCEPTED,
            "protocolVersion": self.state.protocol_version,
            "sessionId": self.state.session_id,
            "serverVersion": self.server_version,
            "serverCommit": self.server_commit,
            "snapshot": snapshot_layer.embedded_snapshot(payload),
        })

    # -- commands ------------------------------------------------------------

    def _handle_command(self, payload):
        parsed = command_layer.parse_command(
            payload, session_id=self.state.session_id
        )
        if parsed is None:
            # Unknown message types must not be interpreted as a known state
            # change (frozen wire schema 1).
            return None
        if parsed.command_id is None:
            # No usable canonical commandId: no replay slot and no ack.
            return None

        if parsed.rejected:
            return self._answer_cached(parsed, lambda: (parsed.rejection, None))

        handlers = {
            schema.ACTIVATION_COMMAND: self._apply_activation_command,
            schema.TRIGGER_SUPPRESSION_SET: self._apply_trigger_suppression,
            schema.AUDIO_AVAILABILITY_SET: self._apply_audio_availability,
            schema.SESSION_SETTINGS_PATCH: self._apply_settings_patch,
            schema.SESSION_SNAPSHOT_REQUEST: self._apply_snapshot_request,
        }
        return handlers[parsed.type](parsed)

    # -- commands answered by the AP-SRV-030 authority -----------------------

    def _apply_activation_command(self, parsed):
        legacy = {
            "commandId": parsed.command_id,
            "action": parsed.payload["action"],
        }
        if parsed.payload["action"] == schema.ACTIVATE:
            legacy["source"] = parsed.payload["source"]
        else:
            legacy["activationId"] = parsed.payload["activationId"]
        before = self.state.state_version
        legacy_ack = self.session.handle_trigger_command(legacy)
        # An accepted activation change always carries its own version: it
        # either mints a state event (``activation.started``,
        # ``activation.phase_changed``) or it is the entry into
        # ``closing_input``, which is versioned by the closing observer. A
        # refresh that did not move a longer deadline changes nothing visible
        # and must therefore not advance anything.
        return self._answer_domain(parsed, legacy_ack, before=before)

    def _apply_audio_availability(self, parsed):
        legacy = {
            "commandId": parsed.command_id,
            "audioAvailable": parsed.payload["audioAvailable"],
        }
        before = self.state.state_version
        legacy_ack = self.session.handle_audio_availability_command(legacy)
        # ``audioAvailable`` is a mandatory snapshot field, so an effective
        # change is visible even though the frozen event catalogue has no
        # availability event. If losing the device also closed an activation,
        # that one logical change is already versioned by the closing observer
        # and must not be counted twice.
        return self._answer_domain(
            parsed, legacy_ack, before=before, visible_without_event=True
        )

    def _answer_domain(
        self, parsed, legacy_ack, *, before=None, visible_without_event=False
    ):
        """Projects one AP-SRV-030 ack, honouring its replay bookkeeping."""
        reason = legacy_ack.get("reason")
        try:
            result = command_layer.map_domain_reason(reason)
        except command_layer.UnmappedDomainReason:
            LOGGER.error(
                "Unbekannter Domain-Reason '%s' ohne v2-Mapping für %s",
                reason,
                self._session_id(),
            )
            result = schema.RESULT_INTERNAL_ERROR

        if result == schema.RESULT_COMMAND_ID_CONFLICT:
            # A conflict never becomes the memoised answer of the original.
            return self._emit_ack(parsed.command_id, result, legacy_ack=legacy_ack)

        memo = self._memoised(parsed.command_id)
        if memo is not None:
            # The domain replayed its stored answer; the original wire ack -
            # including its original version values - is authoritative. A
            # replay never advances the state version.
            self.send(dict(memo))
            return memo

        state_version = self._state_version_for(
            result,
            legacy_ack,
            before=before,
            visible_without_event=visible_without_event,
        )
        ack = self._emit_ack(
            parsed.command_id,
            result,
            legacy_ack=legacy_ack,
            state_version=state_version,
        )
        self._memoise(parsed.command_id, ack)
        if result == schema.RESULT_TRIGGER_SUPPRESSED:
            self._emit_trigger_suppressed(parsed)
        return ack

    def _state_version_for(
        self, result, legacy_ack, *, before, visible_without_event
    ):
        """The version one accepted domain command has to report.

        Three cases, in this order:

        * the command entered ``closing_input`` - the ack reports the version
          of that entry, not the higher one of the close that followed inside
          the same call;
        * the command changed visible state that has no event of its own and
          nothing advanced the version during the call - advance once here;
        * anything else - report the current version, which the minted state
          events already advanced.
        """
        if result != schema.RESULT_APPLIED or before is None:
            return None

        if legacy_ack.get("phase") == schema.CLOSING_INPUT:
            closing = self._closing_version(
                legacy_ack.get("activationId"), newer_than=before
            )
            if closing is not None:
                return closing

        if visible_without_event and self.state.state_version == before:
            return self.state.advance_state()
        return None

    # -- commands answered by this layer -------------------------------------

    def _apply_trigger_suppression(self, parsed):
        def apply():
            controller = self.session.activation_controller()
            if controller is None:
                return schema.RESULT_INTERNAL_ERROR, None
            changed = controller.set_runtime_suppression(
                manual=parsed.payload["manual"],
                wake_word=parsed.payload["wakeWord"],
            )
            if not changed:
                return schema.RESULT_NO_CHANGE, None
            # ``trigger.suppressed`` and ``trigger.effective`` are mandatory
            # snapshot fields, so this is a visible change - and the frozen
            # event catalogue has no event for it.
            # ``activation.trigger_suppressed`` is diagnostic and only appears
            # when a later trigger is refused, so the version has to be
            # advanced here.
            self.state.advance_state()
            return schema.RESULT_APPLIED, None

        return self._answer_cached(parsed, apply)

    def _apply_settings_patch(self, parsed):
        def apply():
            # AP-SRV-050 C3: the whole settings wire block - domain mutation,
            # wire mirror, settings.changed - runs under the shared
            # ``_event_dispatch_lock`` linearization boundary, so a parallel
            # snapshot or domain event can never observe a revision-mixed
            # intermediate state. The lock is an RLock; the reentrant
            # acquisitions inside ``_emit_settings_changed``/``_dispatch_events``
            # are intentional.
            with self._event_dispatch_lock:
                patch = self.settings_port.patch(
                    parsed.payload["baseSettingsRevision"],
                    parsed.payload["changes"],
                )
                return self._bind_settings_patch(patch)

        return self._answer_cached(parsed, apply)

    def _bind_settings_patch(self, patch):
        """Projects one confirmed settings transaction onto the wire state.

        On a real change the session settings revision is mirrored into
        ``ProtocolSessionState`` exactly once and the ``settings.changed``
        events are minted through the existing ``_dispatch_events`` seam - the
        same linearization boundary every AP-SRV-040 domain event uses - so
        ``eventSeq`` order, ``stateVersion`` and retry identity stay at
        AP-SRV-040.
        """
        if patch.result == schema.RESULT_NO_CHANGE:
            return schema.RESULT_NO_CHANGE, None
        if patch.result == schema.RESULT_SETTINGS_REVISION_CONFLICT:
            return schema.RESULT_SETTINGS_REVISION_CONFLICT, patch.error_dicts
        if patch.result == schema.RESULT_SETTINGS_REJECTED:
            return schema.RESULT_SETTINGS_REJECTED, patch.error_dicts

        self.state.set_settings_revision(patch.settings_revision)
        self._emit_settings_changed(patch)
        return schema.RESULT_APPLIED, None

    def _emit_settings_changed(self, patch):
        """Emits the settings.changed groups of one confirmed transaction.

        Changed keys are grouped deterministicly by apply policy
        (``live``, ``next_activation``, ``next_session``, ``server_restart``),
        sorted lexicographically inside each group. Only the first event is a
        visible state change, so one transaction raises ``stateVersion``
        exactly once while every event carries the same new revision.
        """
        revision = int(patch.settings_revision)
        groups = {policy: [] for policy in POLICY_EVENT_ORDER}
        for key in patch.changed_keys:
            policy = patch.apply_policies.get(key)
            if policy in groups:
                groups[policy].append(key)

        def produce():
            payloads = []
            first = True
            for policy in POLICY_EVENT_ORDER:
                keys = sorted(groups[policy])
                if not keys:
                    continue
                envelope = self.state.mint_event(
                    schema.EVENT_SETTINGS_CHANGED,
                    logical_key=("settings.changed", revision, policy),
                    state_change=first,
                )
                envelope.update({
                    "settingsRevision": revision,
                    "scope": "session",
                    "changedKeys": keys,
                    "applyPolicy": policy,
                })
                payloads.append(envelope)
                first = False
            return payloads

        self._dispatch_events(produce)

    def _apply_snapshot_request(self, parsed):
        ack = self._answer_cached(
            parsed, lambda: (schema.RESULT_APPLIED, None)
        )
        # A snapshot is a read, not a mutation: answering a repeated resync
        # request again has no second domain effect and is what the client
        # asked for after an event gap.
        self.send(self._snapshot_payload())
        return ack

    def _answer_cached(self, parsed, apply):
        """Replay/conflict handling for commands this layer owns itself."""
        lookup = self.session.protocol_replay_lookup(
            parsed.command_id, parsed.payload_key
        )
        if lookup.state == REPLAY:
            memo = self._memoised(parsed.command_id)
            if memo is not None:
                self.send(dict(memo))
                return memo
            return self._emit_ack(parsed.command_id, schema.RESULT_INTERNAL_ERROR)
        if lookup.state == CONFLICT:
            return self._emit_ack(
                parsed.command_id, schema.RESULT_COMMAND_ID_CONFLICT
            )

        result, errors = apply()
        ack = self._emit_ack(parsed.command_id, result, errors=errors)
        self.session.protocol_replay_store(
            parsed.command_id, parsed.payload_key, ack
        )
        self._memoise(parsed.command_id, ack)
        return ack

    # -- ack construction ----------------------------------------------------

    def _emit_ack(
        self, command_id, result, *, legacy_ack=None, errors=None,
        state_version=None,
    ):
        controller_snapshot = self._controller_snapshot()
        current_version, settings_revision = self.state.versions()
        if state_version is None:
            state_version = current_version
        if legacy_ack is not None:
            activation_id = legacy_ack.get("activationId")
            input_phase = legacy_ack.get("phase")
        else:
            activation_id = controller_snapshot.get("activationId")
            input_phase = controller_snapshot.get("phase")
        if input_phase not in schema.INPUT_PHASES:
            input_phase = schema.IDLE

        ack = {
            "type": schema.COMMAND_ACK,
            "protocolVersion": self.state.protocol_version,
            "sessionId": self.state.session_id,
            "commandId": command_id,
            "accepted": command_layer.is_accepted(result),
            "result": result,
            "activationId": activation_id,
            "inputPhase": input_phase,
            "stateVersion": state_version,
            "settingsRevision": settings_revision,
        }
        if errors:
            ack["errors"] = [dict(item) for item in errors]
        self.send(ack)
        return ack

    def _memoise(self, command_id, ack):
        with self._lock:
            self._ack_memo.setdefault(command_id, dict(ack))

    def _memoised(self, command_id):
        with self._lock:
            memo = self._ack_memo.get(command_id)
            return None if memo is None else dict(memo)

    def _emit_trigger_suppressed(self, parsed):
        """Diagnostic event for a refused trigger. Never a state change."""
        source = parsed.payload.get("source") or schema.MANUAL_SOURCE

        def mint():
            envelope = self.state.mint_event(
                schema.EVENT_ACTIVATION_TRIGGER_SUPPRESSED
            )
            envelope.update({
                "source": source,
                "reason": "trigger_suppressed",
            })
            return (envelope,)

        self._dispatch_events(mint)

    # -- domain event projection ---------------------------------------------

    def _dispatch_events(self, produce):
        """Mints and hands one ordered event block to the outbound boundary."""
        with self._event_dispatch_lock:
            events = produce()
            for event in events:
                self.send(event)

    def _on_domain_event(self, legacy_event, payload):
        """Single subscription to the one AP-SRV-030 lifecycle funnel."""
        projector = self.projector
        if projector is None:
            return
        if legacy_event == self.session.INPUT_CLOSING_NOTIFICATION:
            self._observe_input_closing(payload)
            return
        try:
            self._dispatch_events(lambda: projector.project(
                legacy_event, payload, self._projection_context()
            ))
        except Exception:
            LOGGER.exception(
                "v2-Eventprojektion für '%s' ist fehlgeschlagen", legacy_event
            )

    def _observe_input_closing(self, payload):
        """Versions the visible entry into ``closing_input``.

        ``closing_input`` is one of the five canonical foreground phases, so
        reaching it is a visible state change - but AP-SRV-030 publishes no
        lifecycle event for it, and ``activation.input_closed`` describes the
        *completed* close, not its beginning. Without this the ack that already
        reports ``inputPhase = closing_input`` would carry the version of the
        later close.

        A failed close that the recovery retries is the same logical entry and
        therefore advances the version only once.
        """
        key = (
            str(payload.get("activationId")),
            int(payload.get("activationSequence") or 0),
        )
        with self._lock:
            if key in self._closing_versions:
                return self._closing_versions[key]
            version = self.state.advance_state()
            self._closing_versions[key] = version
            return version

    def _closing_version(self, activation_id, *, newer_than):
        """The closing version of this activation, if this call created it."""
        if activation_id is None:
            return None
        with self._lock:
            for (identifier, _sequence), version in self._closing_versions.items():
                if identifier == str(activation_id) and version > newer_than:
                    return version
        return None

    def _projection_context(self):
        controller_snapshot = self._controller_snapshot()
        deadline_at, remaining = snapshot_layer.project_deadline(
            controller_snapshot.get("deadline")
        )
        segment_id, segment_sequence = self._active_segment()
        return event_layer.ProjectionContext(
            phase=controller_snapshot.get("phase") or schema.IDLE,
            activation_id=controller_snapshot.get("activationId"),
            activation_sequence=controller_snapshot.get("activationSequence"),
            primary_source=controller_snapshot.get("primarySource"),
            deadline_at_unix_ms=deadline_at,
            remaining_ms=remaining,
            effective_settings=self.settings_port.effective_settings(),
            active_segment_id=segment_id,
            active_segment_sequence=segment_sequence,
        )

    def _active_segment(self):
        session = self.session
        if session is None:
            return None, None
        try:
            return session.active_segment_identity()
        except Exception:
            return None, None

    # -- snapshot ------------------------------------------------------------

    def _snapshot_payload(self):
        # AP-SRV-050 C3: the complete snapshot is built under the same
        # ``_event_dispatch_lock`` boundary as the settings patch block, so no
        # snapshot can be captured mid-way between a settings domain commit and
        # its wire mirror / settings.changed. The revision-mixed window is
        # structurally unreachable from this side as well.
        with self._event_dispatch_lock:
            return snapshot_layer.build_snapshot(
                state=self.state,
                controller=self.session.activation_controller(),
                ledger=self.session.segment_ledger,
                audio_available=self.session.audio_available(),
                settings_port=self.settings_port,
                wake_word_port=self.wake_word_port,
                server_version=self.server_version,
                server_commit=self.server_commit,
            )

    def _controller_snapshot(self):
        session = self.session
        if session is None:
            return {}
        snapshot = session.activation_snapshot()
        return snapshot or {}

    def _session_id(self):
        return None if self.state is None else self.state.session_id
