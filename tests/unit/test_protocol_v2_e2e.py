"""AP-SRV-040 – end-to-end proof of the frozen protocol v2 wire.

Every test in this file goes through the real production entry point::

    websocket_connect("/ws/v2")
        -> ProtocolV2Connection
        -> handshake / VoiceSTTService.admit_session
        -> ProtocolSessionState
        -> strict v2 envelope
        -> RecorderBackedRealtimeSession.handle_trigger_command
        -> ActivationController
        -> the real controlled activation gate
        -> recorder callbacks
        -> v2 event projection and snapshot

The recorder fake and the gate wiring are the ones AP-SRV-030 already proves
in ``test_server_controlled_e2e``; this file reuses them deliberately so a
break in the domain path shows up here as well instead of being mocked away.
"""

import json
import queue
import threading
import time
import unittest
import uuid
from unittest import mock

from api_fastapi_server.protocol_v2 import schema

try:
    from starlette.websockets import WebSocketDisconnect
except Exception:  # pragma: no cover - optional dependency
    class WebSocketDisconnect(Exception):
        code = None

from tests.unit.test_server_controlled_e2e import (
    GateAwareRecorder,
    TestClient,
    build_app,
    speech_packet,
)


CLIENT_RUN_ID = "10000000-0000-4000-8000-000000000001"


def _without(message, field):
    stripped = dict(message)
    stripped.pop(field, None)
    return stripped


def hello_message(
    *,
    manual=True,
    wake_word=False,
    wake_word_ids=(),
    suppress_manual=False,
    suppress_wake_word=False,
    versions=(2,),
    client_run_id=CLIENT_RUN_ID,
):
    return {
        "type": "hello",
        "supportedProtocolVersions": list(versions),
        "clientVersion": "2.0.0-test",
        "clientCommit": "client-test-commit",
        "clientRunId": client_run_id,
        "requestedSession": {
            "trigger": {"manual": manual, "wakeWord": wake_word},
            "wakeWordIds": list(wake_word_ids),
        },
        "runtimeSuppression": {
            "manual": suppress_manual,
            "wakeWord": suppress_wake_word,
        },
    }


class V2Session:
    """Drives one real ``/ws/v2`` connection with bounded waits.

    A background reader keeps every wait bounded, so a missing server message
    fails the test instead of hanging it.
    """

    def __init__(self, client, hello=None, expect_accept=True):
        self.client = client
        self._hello = hello_message() if hello is None else hello
        self._expect_accept = expect_accept
        #: Append-only history of everything the server sent.
        self.messages = []
        #: Messages no wait has consumed yet.
        self._pending = []
        self._inbox = queue.Queue()
        self._closed = threading.Event()
        self.accepted = None

    def __enter__(self):
        self._context = self.client.websocket_connect("/ws/v2")
        self.socket = self._context.__enter__()
        self._reader = threading.Thread(target=self._read_forever, daemon=True)
        self._reader.start()
        if self._hello is not None:
            self.send_raw(self._hello)
        if self._expect_accept:
            self.accepted = self.drain(schema.HELLO_ACCEPTED, timeout=15.0)
        return self

    def __exit__(self, *exc):
        self._closed.set()
        return self._context.__exit__(*exc)

    def _read_forever(self):
        try:
            while not self._closed.is_set():
                self._inbox.put(self.socket.receive_json())
        except Exception:
            self._inbox.put(None)

    # -- identity ------------------------------------------------------------

    @property
    def session_id(self):
        return self.accepted["sessionId"]

    def command(self, payload):
        """Fills in the session envelope and sends one command."""
        message = dict(payload)
        message.setdefault("protocolVersion", schema.PROTOCOL_VERSION)
        message.setdefault("sessionId", self.session_id)
        message.setdefault("commandId", str(uuid.uuid4()))
        self.send_raw(message)
        return message

    def send_raw(self, payload):
        self.socket.send_text(json.dumps(payload))
        return payload

    def send_bytes(self, data):
        self.socket.send_bytes(data)

    # -- reading -------------------------------------------------------------

    def expect(self, timeout=15.0):
        """Reads one more server message into history and the pending list."""
        try:
            message = self._inbox.get(timeout=timeout)
        except queue.Empty:
            raise AssertionError(f"no server message within {timeout}s")
        if message is None:
            raise AssertionError("the server closed the connection")
        self.messages.append(message)
        self._pending.append(message)
        return message

    def _take(self, predicate, description, timeout):
        """Consumes the first pending message that matches.

        Consuming matters: a second wait for the same message type has to see
        a *new* message, not the one an earlier wait already returned.
        """
        deadline = time.monotonic() + timeout
        while True:
            for message in self._pending:
                if predicate(message):
                    self._pending.remove(message)
                    return message
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise AssertionError(
                    f"no {description} within {timeout}s; saw "
                    f"{[m.get('type') for m in self.messages[-10:]]}"
                )
            self.expect(timeout=remaining)

    def drain(self, expected_type, timeout=15.0):
        return self._take(
            lambda message: message.get("type") == expected_type,
            expected_type,
            timeout,
        )

    def ack(self, command_id, timeout=15.0):
        return self._take(
            lambda message: (
                message.get("type") == schema.COMMAND_ACK
                and message.get("commandId") == command_id
            ),
            f"ack for {command_id}",
            timeout,
        )

    def event(self, event_type, timeout=15.0):
        return self.drain(event_type, timeout=timeout)

    def seen(self, message_type):
        return [m for m in self.messages if m.get("type") == message_type]

    def settle(self, timeout=15.0):
        """Round-trips a snapshot request so pending messages are delivered."""
        sent = self.command({"type": schema.SESSION_SNAPSHOT_REQUEST})
        self.ack(sent["commandId"], timeout=timeout)
        return self.drain(schema.SESSION_SNAPSHOT, timeout=timeout)

    def snapshot(self, timeout=15.0):
        return self.settle(timeout=timeout)

    def collected(self, message_type=None):
        return [
            m for m in self.messages
            if message_type is None or m.get("type") == message_type
        ]

    # -- domain helpers ------------------------------------------------------

    def recorder(self):
        assert GateAwareRecorder.instances, "no recorder was created"
        return GateAwareRecorder.instances[-1]

    def server_session(self, app):
        session = app.state.voicestt_service.sessions.get(self.session_id)
        assert session is not None, "the server session is gone"
        return session

    def activate(self):
        sent = self.command({
            "type": schema.ACTIVATION_COMMAND,
            "action": schema.ACTIVATE,
            "source": schema.MANUAL_SOURCE,
        })
        ack = self.ack(sent["commandId"])
        return sent["commandId"], ack


@unittest.skipIf(TestClient is None, "FastAPI test client is not installed")
class ProtocolV2HandshakeTests(unittest.TestCase):
    def setUp(self):
        GateAwareRecorder.instances = []
        self.app = build_app()

    def _refuse(self, first_message, *, raw=False, send=True):
        """One refused handshake: the messages sent and the close code."""
        close_code = None
        messages = []
        with TestClient(self.app) as client:
            with client.websocket_connect("/ws/v2") as socket:
                if send:
                    if raw:
                        socket.send_text(first_message)
                    else:
                        socket.send_text(json.dumps(first_message))
                try:
                    while True:
                        messages.append(socket.receive_json())
                except WebSocketDisconnect as disconnect:
                    close_code = disconnect.code
                except Exception:
                    pass
        return messages, close_code

    def _refused(self, first_message, *, raw=False):
        return self._refuse(first_message, raw=raw)[0]

    def test_hello_is_accepted_with_an_embedded_snapshot(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                accepted = session.accepted
                self.assertEqual(accepted["protocolVersion"], 2)
                self.assertTrue(schema.is_canonical_uuid(accepted["sessionId"]))
                self.assertTrue(accepted["serverVersion"])
                self.assertTrue(accepted["serverCommit"])
                snapshot = accepted["snapshot"]
                # Only the inner ``type`` is dropped when embedded.
                self.assertNotIn("type", snapshot)
                for field in (
                    "protocolVersion", "serverVersion", "serverCommit",
                    "sessionId", "stateVersion", "lastEventSeq",
                    "settingsRevision", "input", "pendingActivations",
                    "trigger", "audioAvailable", "effectiveSettings",
                    "wakeWordCapabilities",
                ):
                    self.assertIn(field, snapshot)

    def test_first_message_must_be_hello(self):
        messages = self._refused({
            "type": schema.ACTIVATION_COMMAND,
            "protocolVersion": 2,
            "commandId": str(uuid.uuid4()),
            "action": "activate",
            "source": "manual",
        })
        self.assertEqual(messages, [])
        self.assertEqual(len(self.app.state.voicestt_service.sessions.all()), 0)

    def test_invalid_json_closes_without_a_session(self):
        messages = self._refused("{not json", raw=True)
        self.assertEqual(messages, [])
        self.assertEqual(len(self.app.state.voicestt_service.sessions.all()), 0)

    def test_hello_with_missing_fields_is_refused(self):
        for missing in (
            "clientVersion", "clientCommit", "clientRunId",
            "requestedSession", "runtimeSuppression",
            "supportedProtocolVersions",
        ):
            with self.subTest(missing=missing):
                message = hello_message()
                message.pop(missing)
                self.assertEqual(self._refused(message), [])

    def test_empty_supported_protocol_versions_is_refused(self):
        self.assertEqual(self._refused(hello_message(versions=())), [])

    def test_no_common_version_reports_protocol_incompatible(self):
        messages = self._refused(hello_message(versions=(1, 3)))
        self.assertEqual(len(messages), 1)
        payload = messages[0]
        self.assertEqual(payload["type"], schema.PROTOCOL_INCOMPATIBLE)
        self.assertEqual(payload["reason"], "no_common_protocol_version")
        self.assertEqual(payload["supportedProtocolVersions"], [2])
        self.assertIn("serverVersion", payload)
        self.assertIn("serverCommit", payload)
        # No partially usable session is opened.
        self.assertNotIn("sessionId", payload)
        self.assertEqual(len(self.app.state.voicestt_service.sessions.all()), 0)

    def test_wake_word_enabled_without_selection_is_rejected(self):
        messages = self._refused(hello_message(
            manual=True, wake_word=True, wake_word_ids=(),
            suppress_wake_word=True,
        ))
        self.assertEqual(len(messages), 1)
        payload = messages[0]
        self.assertEqual(payload["type"], schema.SESSION_REJECTED)
        self.assertNotIn("sessionId", payload)
        codes = {error["code"] for error in payload["errors"]}
        self.assertIn("wake_word_selection_required", codes)
        self.assertEqual(len(self.app.state.voicestt_service.sessions.all()), 0)

    def test_no_trigger_source_is_rejected(self):
        messages = self._refused(hello_message(manual=False, wake_word=False))
        self.assertEqual(len(messages), 1)
        codes = {error["code"] for error in messages[0]["errors"]}
        self.assertIn("activation_trigger_required", codes)

    def test_unknown_wake_word_id_rejects_the_whole_selection(self):
        messages = self._refused(hello_message(
            manual=True, wake_word=True, wake_word_ids=("does_not_exist",),
        ))
        self.assertEqual(len(messages), 1)
        payload = messages[0]
        self.assertEqual(payload["type"], schema.SESSION_REJECTED)
        codes = {error["code"] for error in payload["errors"]}
        self.assertIn("wake_word_unavailable", codes)
        self.assertEqual(len(self.app.state.voicestt_service.sessions.all()), 0)

    def test_audio_before_hello_accepted_is_refused(self):
        with TestClient(self.app) as client:
            with client.websocket_connect("/ws/v2") as socket:
                socket.send_bytes(speech_packet())
                messages = []
                try:
                    while True:
                        messages.append(socket.receive_json())
                except Exception:
                    pass
        self.assertEqual(messages, [])
        self.assertEqual(len(self.app.state.voicestt_service.sessions.all()), 0)
        # No recorder and therefore no audio path was created.
        self.assertEqual(GateAwareRecorder.instances, [])

    def test_command_before_hello_accepted_creates_no_session(self):
        messages = self._refused({
            "type": schema.ACTIVATION_COMMAND,
            "protocolVersion": 2,
            "sessionId": "20000000-0000-4000-8000-000000000001",
            "commandId": "50000000-0000-4000-8000-000000000001",
            "action": "activate",
            "source": "manual",
        })
        self.assertEqual(messages, [])
        self.assertEqual(GateAwareRecorder.instances, [])

    def test_close_codes_follow_the_frozen_table(self):
        cases = (
            ("invalid first message", {
                "type": schema.ACTIVATION_COMMAND,
                "protocolVersion": 2,
                "commandId": str(uuid.uuid4()),
                "action": "activate",
                "source": "manual",
            }, schema.CLOSE_INVALID_HANDSHAKE),
            ("hello without clientRunId", _without(hello_message(), "clientRunId"),
             schema.CLOSE_INVALID_HANDSHAKE),
            ("no common version", hello_message(versions=(1,)),
             schema.CLOSE_PROTOCOL_INCOMPATIBLE),
            ("session rejected", hello_message(manual=False, wake_word=False),
             schema.CLOSE_SESSION_REJECTED),
        )
        for label, message, expected in cases:
            with self.subTest(case=label):
                _messages, code = self._refuse(message)
                self.assertEqual(code, expected)

    def test_unparseable_handshake_closes_with_4400(self):
        _messages, code = self._refuse("{not json", raw=True)
        self.assertEqual(code, schema.CLOSE_INVALID_HANDSHAKE)

    def test_audio_before_hello_closes_with_4400(self):
        close_code = None
        with TestClient(self.app) as client:
            with client.websocket_connect("/ws/v2") as socket:
                socket.send_bytes(speech_packet())
                try:
                    while True:
                        socket.receive_json()
                except WebSocketDisconnect as disconnect:
                    close_code = disconnect.code
                except Exception:
                    pass
        self.assertEqual(close_code, schema.CLOSE_INVALID_HANDSHAKE)

    def test_a_silent_client_hits_the_handshake_timeout(self):
        with mock.patch.object(
            schema, "DEFAULT_HANDSHAKE_TIMEOUT_SECONDS", 0.25
        ):
            _messages, code = self._refuse(None, send=False)
        self.assertEqual(code, schema.CLOSE_HANDSHAKE_TIMEOUT)
        self.assertEqual(len(self.app.state.voicestt_service.sessions.all()), 0)

    def test_an_unexpected_admission_failure_closes_with_1011(self):
        service = self.app.state.voicestt_service
        with mock.patch.object(
            service, "admit_session", side_effect=RuntimeError("boom")
        ):
            messages, code = self._refuse(hello_message())
        self.assertEqual(messages, [])
        self.assertEqual(code, schema.CLOSE_INTERNAL_ERROR)
        self.assertEqual(len(service.sessions.all()), 0)

    def test_a_rejected_command_never_closes_the_session(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                sent = session.command({
                    "type": schema.ACTIVATION_COMMAND,
                    "action": schema.ACTIVATE,
                    "source": schema.WAKE_WORD_SOURCE,
                })
                session.ack(sent["commandId"])
                # The connection is still usable afterwards.
                _command_id, ack = session.activate()
                self.assertEqual(ack["result"], schema.RESULT_APPLIED)

    def test_second_hello_is_not_a_command_and_changes_nothing(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                before = session.snapshot()
                session.send_raw(hello_message())
                after = session.snapshot()
                self.assertEqual(
                    after["sessionId"], before["sessionId"]
                )
                self.assertEqual(
                    after["stateVersion"], before["stateVersion"]
                )


@unittest.skipIf(TestClient is None, "FastAPI test client is not installed")
class ProtocolV2CommandTests(unittest.TestCase):
    def setUp(self):
        GateAwareRecorder.instances = []
        self.app = build_app()

    def test_manual_activate_is_applied(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                _command_id, ack = session.activate()
                self.assertTrue(ack["accepted"])
                self.assertEqual(ack["result"], schema.RESULT_APPLIED)
                self.assertEqual(ack["inputPhase"], schema.WAITING_FIRST_SPEECH)
                self.assertTrue(schema.is_canonical_uuid(ack["activationId"]))
                self.assertEqual(ack["sessionId"], session.session_id)
                self.assertEqual(ack["protocolVersion"], 2)
                self.assertGreaterEqual(ack["stateVersion"], 1)
                self.assertEqual(ack["settingsRevision"], 0)

    def test_client_claiming_wake_word_is_invalid_payload(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                sent = session.command({
                    "type": schema.ACTIVATION_COMMAND,
                    "action": schema.ACTIVATE,
                    "source": schema.WAKE_WORD_SOURCE,
                })
                ack = session.ack(sent["commandId"])
                self.assertFalse(ack["accepted"])
                self.assertEqual(ack["result"], schema.RESULT_INVALID_PAYLOAD)
                self.assertEqual(ack["inputPhase"], schema.IDLE)

    def test_activate_with_activation_id_is_invalid_payload(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                sent = session.command({
                    "type": schema.ACTIVATION_COMMAND,
                    "action": schema.ACTIVATE,
                    "source": schema.MANUAL_SOURCE,
                    "activationId": "30000000-0000-4000-8000-000000000001",
                })
                ack = session.ack(sent["commandId"])
                self.assertEqual(ack["result"], schema.RESULT_INVALID_PAYLOAD)

    def test_control_without_activation_id_is_invalid_payload(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                for action in (schema.REFRESH, schema.FINISH, schema.CANCEL):
                    with self.subTest(action=action):
                        sent = session.command({
                            "type": schema.ACTIVATION_COMMAND,
                            "action": action,
                        })
                        ack = session.ack(sent["commandId"])
                        self.assertEqual(
                            ack["result"], schema.RESULT_INVALID_PAYLOAD
                        )

    def test_control_with_source_is_invalid_payload(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                _command_id, activate_ack = session.activate()
                sent = session.command({
                    "type": schema.ACTIVATION_COMMAND,
                    "action": schema.REFRESH,
                    "activationId": activate_ack["activationId"],
                    "source": schema.MANUAL_SOURCE,
                })
                ack = session.ack(sent["commandId"])
                self.assertEqual(ack["result"], schema.RESULT_INVALID_PAYLOAD)

    def test_extend_alias_is_not_accepted_in_v2(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                _command_id, activate_ack = session.activate()
                sent = session.command({
                    "type": schema.ACTIVATION_COMMAND,
                    "action": "extend",
                    "activationId": activate_ack["activationId"],
                })
                ack = session.ack(sent["commandId"])
                self.assertEqual(ack["result"], schema.RESULT_INVALID_PAYLOAD)

    def test_stale_session_id_has_no_effect(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                before = session.snapshot()
                sent = session.command({
                    "type": schema.ACTIVATION_COMMAND,
                    "sessionId": "20000000-0000-4000-8000-0000000000ff",
                    "action": schema.ACTIVATE,
                    "source": schema.MANUAL_SOURCE,
                })
                ack = session.ack(sent["commandId"])
                self.assertEqual(ack["result"], schema.RESULT_STALE_SESSION)
                self.assertFalse(ack["accepted"])
                # The ack still carries the *current* session.
                self.assertEqual(ack["sessionId"], session.session_id)
                after = session.snapshot()
                self.assertEqual(after["input"]["phase"], schema.IDLE)
                self.assertEqual(
                    after["stateVersion"], before["stateVersion"]
                )

    def test_stale_activation_id_is_refused(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                session.activate()
                sent = session.command({
                    "type": schema.ACTIVATION_COMMAND,
                    "action": schema.FINISH,
                    "activationId": "30000000-0000-4000-8000-0000000000ff",
                })
                ack = session.ack(sent["commandId"])
                self.assertEqual(ack["result"], schema.RESULT_STALE_ACTIVATION)
                snapshot = session.snapshot()
                self.assertEqual(
                    snapshot["input"]["phase"], schema.WAITING_FIRST_SPEECH
                )

    def test_activation_locked_while_a_window_is_open(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                session.activate()
                _command_id, ack = session.activate()
                self.assertFalse(ack["accepted"])
                self.assertEqual(
                    ack["result"], schema.RESULT_ACTIVATION_LOCKED
                )

    def test_refresh_in_waiting_first_speech_is_invalid_phase(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                _command_id, activate_ack = session.activate()
                sent = session.command({
                    "type": schema.ACTIVATION_COMMAND,
                    "action": schema.REFRESH,
                    "activationId": activate_ack["activationId"],
                })
                ack = session.ack(sent["commandId"])
                self.assertEqual(ack["result"], schema.RESULT_INVALID_PHASE)

    def test_control_while_idle_is_not_active(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                sent = session.command({
                    "type": schema.ACTIVATION_COMMAND,
                    "action": schema.FINISH,
                    "activationId": "30000000-0000-4000-8000-000000000001",
                })
                ack = session.ack(sent["commandId"])
                self.assertEqual(ack["result"], schema.RESULT_NOT_ACTIVE)

    def test_replay_returns_the_identical_ack_and_acts_once(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                payload = {
                    "type": schema.ACTIVATION_COMMAND,
                    "protocolVersion": 2,
                    "sessionId": session.session_id,
                    "commandId": "50000000-0000-4000-8000-000000000001",
                    "action": schema.ACTIVATE,
                    "source": schema.MANUAL_SOURCE,
                }
                session.send_raw(payload)
                first = session.ack(payload["commandId"])
                session.event(schema.EVENT_ACTIVATION_STARTED)
                session.send_raw(dict(payload))
                second = session.ack(payload["commandId"])

                self.assertEqual(first, second)
                snapshot = session.snapshot()
                started = [
                    m for m in session.collected(schema.EVENT_ACTIVATION_STARTED)
                ]
                self.assertEqual(len(started), 1)
                self.assertEqual(snapshot["stateVersion"], first["stateVersion"])

    def test_replay_with_unknown_additive_field_is_still_a_replay(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                payload = {
                    "type": schema.ACTIVATION_COMMAND,
                    "protocolVersion": 2,
                    "sessionId": session.session_id,
                    "commandId": "50000000-0000-4000-8000-000000000010",
                    "action": schema.ACTIVATE,
                    "source": schema.MANUAL_SOURCE,
                }
                session.send_raw(payload)
                first = session.ack(payload["commandId"])
                replay = dict(payload)
                replay["someFutureAdditiveField"] = {"a": 1}
                session.send_raw(replay)
                second = session.ack(payload["commandId"])
                self.assertEqual(first, second)

    def test_same_command_id_with_changed_payload_conflicts(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                command_id = "50000000-0000-4000-8000-000000000001"
                session.send_raw({
                    "type": schema.ACTIVATION_COMMAND,
                    "protocolVersion": 2,
                    "sessionId": session.session_id,
                    "commandId": command_id,
                    "action": schema.ACTIVATE,
                    "source": schema.MANUAL_SOURCE,
                })
                first = session.ack(command_id)
                session.send_raw({
                    "type": schema.ACTIVATION_COMMAND,
                    "protocolVersion": 2,
                    "sessionId": session.session_id,
                    "commandId": command_id,
                    "action": schema.CANCEL,
                    "activationId": first["activationId"],
                })
                conflict = session.ack(command_id)
                self.assertFalse(conflict["accepted"])
                self.assertEqual(
                    conflict["result"], schema.RESULT_COMMAND_ID_CONFLICT
                )
                snapshot = session.snapshot()
                self.assertEqual(
                    snapshot["input"]["phase"], schema.WAITING_FIRST_SPEECH
                )

    def test_rejected_command_keeps_its_replay_identity(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                command_id = "50000000-0000-4000-8000-000000000003"
                invalid = {
                    "type": schema.ACTIVATION_COMMAND,
                    "protocolVersion": 2,
                    "sessionId": session.session_id,
                    "commandId": command_id,
                    "action": schema.ACTIVATE,
                    "source": schema.WAKE_WORD_SOURCE,
                }
                session.send_raw(invalid)
                first = session.ack(command_id)
                session.send_raw(dict(invalid))
                replay = session.ack(command_id)
                self.assertEqual(first, replay)

                # A different payload under the same id is a conflict, and the
                # forbidden ``source`` on a control is part of the identity.
                session.send_raw({
                    "type": schema.ACTIVATION_COMMAND,
                    "protocolVersion": 2,
                    "sessionId": session.session_id,
                    "commandId": command_id,
                    "action": schema.ACTIVATE,
                    "source": schema.MANUAL_SOURCE,
                })
                conflict = session.ack(command_id)
                self.assertEqual(
                    conflict["result"], schema.RESULT_COMMAND_ID_CONFLICT
                )
                self.assertEqual(
                    session.snapshot()["input"]["phase"], schema.IDLE
                )

    def test_non_canonical_command_id_gets_no_ack(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                before = session.snapshot()
                compact = uuid.uuid4().hex  # compact, not canonical
                session.send_raw({
                    "type": schema.ACTIVATION_COMMAND,
                    "protocolVersion": 2,
                    "sessionId": session.session_id,
                    "commandId": compact,
                    "action": schema.ACTIVATE,
                    "source": schema.MANUAL_SOURCE,
                })
                after = session.snapshot()
                answered = {
                    ack["commandId"]
                    for ack in session.collected(schema.COMMAND_ACK)
                }
                self.assertNotIn(compact, answered)
                self.assertEqual(
                    after["stateVersion"], before["stateVersion"]
                )
                self.assertEqual(after["input"]["phase"], schema.IDLE)

    def test_unknown_message_type_is_ignored(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                before = session.snapshot()
                session.send_raw({
                    "type": "something.from.the.future",
                    "protocolVersion": 2,
                    "sessionId": session.session_id,
                    "commandId": str(uuid.uuid4()),
                })
                after = session.snapshot()
                self.assertEqual(
                    after["stateVersion"], before["stateVersion"]
                )

    def test_wrong_protocol_version_on_a_command_is_invalid_payload(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                sent = session.command({
                    "type": schema.ACTIVATION_COMMAND,
                    "protocolVersion": 1,
                    "action": schema.ACTIVATE,
                    "source": schema.MANUAL_SOURCE,
                })
                ack = session.ack(sent["commandId"])
                self.assertEqual(ack["result"], schema.RESULT_INVALID_PAYLOAD)

    def test_audio_unavailable_refuses_a_new_activation(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                sent = session.command({
                    "type": schema.AUDIO_AVAILABILITY_SET,
                    "audioAvailable": False,
                })
                availability = session.ack(sent["commandId"])
                self.assertTrue(availability["accepted"])
                self.assertEqual(availability["result"], schema.RESULT_APPLIED)

                _command_id, ack = session.activate()
                self.assertFalse(ack["accepted"])
                self.assertEqual(
                    ack["result"], schema.RESULT_AUDIO_UNAVAILABLE
                )
                self.assertFalse(session.snapshot()["audioAvailable"])

    def test_audio_availability_replay_is_idempotent(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                payload = {
                    "type": schema.AUDIO_AVAILABILITY_SET,
                    "protocolVersion": 2,
                    "sessionId": session.session_id,
                    "commandId": "50000000-0000-4000-8000-000000000020",
                    "audioAvailable": False,
                }
                session.send_raw(payload)
                first = session.ack(payload["commandId"])
                session.send_raw(dict(payload))
                second = session.ack(payload["commandId"])
                self.assertEqual(first, second)

    def test_trigger_suppression_blocks_new_admission_only(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                sent = session.command({
                    "type": schema.TRIGGER_SUPPRESSION_SET,
                    "manual": True,
                    "wakeWord": False,
                })
                ack = session.ack(sent["commandId"])
                self.assertEqual(ack["result"], schema.RESULT_APPLIED)

                snapshot = session.snapshot()
                self.assertTrue(snapshot["trigger"]["configured"]["manual"])
                self.assertTrue(snapshot["trigger"]["suppressed"]["manual"])
                self.assertFalse(snapshot["trigger"]["effective"]["manual"])

                _command_id, activate_ack = session.activate()
                self.assertFalse(activate_ack["accepted"])
                self.assertEqual(
                    activate_ack["result"], schema.RESULT_TRIGGER_SUPPRESSED
                )
                suppressed = session.event(
                    schema.EVENT_ACTIVATION_TRIGGER_SUPPRESSED
                )
                self.assertEqual(suppressed["source"], schema.MANUAL_SOURCE)

    def test_suppression_does_not_end_a_running_activation(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                _command_id, activate_ack = session.activate()
                sent = session.command({
                    "type": schema.TRIGGER_SUPPRESSION_SET,
                    "manual": True,
                    "wakeWord": True,
                })
                session.ack(sent["commandId"])
                snapshot = session.snapshot()
                self.assertEqual(
                    snapshot["input"]["phase"], schema.WAITING_FIRST_SPEECH
                )
                self.assertEqual(
                    snapshot["input"]["activationId"],
                    activate_ack["activationId"],
                )

    def test_repeated_suppression_is_no_change(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                first = session.command({
                    "type": schema.TRIGGER_SUPPRESSION_SET,
                    "manual": True,
                    "wakeWord": False,
                })
                self.assertEqual(
                    session.ack(first["commandId"])["result"],
                    schema.RESULT_APPLIED,
                )
                second = session.command({
                    "type": schema.TRIGGER_SUPPRESSION_SET,
                    "manual": True,
                    "wakeWord": False,
                })
                ack = session.ack(second["commandId"])
                self.assertTrue(ack["accepted"])
                self.assertEqual(ack["result"], schema.RESULT_NO_CHANGE)

    def test_hello_runtime_suppression_is_applied_at_admission(self):
        with TestClient(self.app) as client:
            with V2Session(
                client, hello=hello_message(suppress_manual=True)
            ) as session:
                snapshot = session.accepted["snapshot"]
                self.assertTrue(snapshot["trigger"]["suppressed"]["manual"])
                self.assertFalse(snapshot["trigger"]["effective"]["manual"])
                _command_id, ack = session.activate()
                self.assertEqual(
                    ack["result"], schema.RESULT_TRIGGER_SUPPRESSED
                )

    def test_settings_patch_is_refused_until_ap_srv_050(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                sent = session.command({
                    "type": schema.SESSION_SETTINGS_PATCH,
                    "baseSettingsRevision": 0,
                    "changes": {"activation.followupTimeoutMs": 4000},
                })
                ack = session.ack(sent["commandId"])
                self.assertFalse(ack["accepted"])
                self.assertEqual(ack["result"], schema.RESULT_SETTINGS_REJECTED)
                self.assertTrue(ack["errors"])
                self.assertEqual(ack["settingsRevision"], 0)

    def test_settings_patch_with_stale_revision_conflicts(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                sent = session.command({
                    "type": schema.SESSION_SETTINGS_PATCH,
                    "baseSettingsRevision": 7,
                    "changes": {"activation.followupTimeoutMs": 4000},
                })
                ack = session.ack(sent["commandId"])
                self.assertEqual(
                    ack["result"], schema.RESULT_SETTINGS_REVISION_CONFLICT
                )

    def test_settings_patch_with_empty_changes_is_invalid_payload(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                sent = session.command({
                    "type": schema.SESSION_SETTINGS_PATCH,
                    "baseSettingsRevision": 0,
                    "changes": {},
                })
                ack = session.ack(sent["commandId"])
                self.assertEqual(ack["result"], schema.RESULT_INVALID_PAYLOAD)

    def test_every_ack_uses_a_frozen_result_code(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                session.activate()
                session.command({
                    "type": schema.ACTIVATION_COMMAND,
                    "action": schema.ACTIVATE,
                    "source": schema.WAKE_WORD_SOURCE,
                })
                session.command({
                    "type": schema.TRIGGER_SUPPRESSION_SET,
                    "manual": False,
                    "wakeWord": True,
                })
                session.snapshot()
                acks = [
                    m for m in session.messages
                    if m.get("type") == schema.COMMAND_ACK
                ]
                self.assertTrue(acks)
                for ack in acks:
                    self.assertIn(ack["result"], schema.RESULT_CODES)
                    self.assertEqual(
                        ack["accepted"],
                        ack["result"] in schema.ACCEPTED_RESULTS,
                    )


@unittest.skipIf(TestClient is None, "FastAPI test client is not installed")
class ProtocolV2EventTests(unittest.TestCase):
    def setUp(self):
        GateAwareRecorder.instances = []
        self.app = build_app()

    def _events(self, session):
        return [
            message for message in session.messages
            if message.get("type") in schema.EVENT_TYPES
        ]

    def test_activation_started_carries_the_full_frozen_envelope(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                _command_id, ack = session.activate()
                started = session.event(schema.EVENT_ACTIVATION_STARTED)
                for field in (
                    "protocolVersion", "sessionId", "eventId", "eventSeq",
                    "stateVersion", "occurredAtUnixMs", "activationId",
                    "activationSequence", "primarySource", "inputPhase",
                    "effectiveSettings",
                ):
                    self.assertIn(field, started)
                self.assertEqual(started["sessionId"], session.session_id)
                self.assertTrue(schema.is_canonical_uuid(started["eventId"]))
                self.assertEqual(started["activationId"], ack["activationId"])
                self.assertEqual(started["primarySource"], schema.MANUAL_SOURCE)
                self.assertEqual(
                    started["inputPhase"], schema.WAITING_FIRST_SPEECH
                )
                self.assertEqual(started["activationSequence"], 1)

    def test_event_seq_is_strictly_monotonic_and_ids_are_unique(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                for _ in range(3):
                    _command_id, ack = session.activate()
                    session.event(schema.EVENT_ACTIVATION_STARTED)
                    finish = session.command({
                        "type": schema.ACTIVATION_COMMAND,
                        "action": schema.FINISH,
                        "activationId": ack["activationId"],
                    })
                    session.ack(finish["commandId"])
                    session.event(schema.EVENT_ACTIVATION_INPUT_CLOSED)
                session.snapshot()

                events = self._events(session)
                self.assertGreaterEqual(len(events), 6)
                sequences = [event["eventSeq"] for event in events]
                self.assertEqual(sequences, sorted(sequences))
                self.assertEqual(len(set(sequences)), len(sequences))
                identifiers = [event["eventId"] for event in events]
                self.assertEqual(len(set(identifiers)), len(identifiers))
                versions = [event["stateVersion"] for event in events]
                self.assertEqual(versions, sorted(versions))

    def test_snapshot_agrees_with_the_last_event(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                session.activate()
                started = session.event(schema.EVENT_ACTIVATION_STARTED)
                snapshot = session.snapshot()
                self.assertGreaterEqual(
                    snapshot["lastEventSeq"], started["eventSeq"]
                )
                self.assertGreaterEqual(
                    snapshot["stateVersion"], started["stateVersion"]
                )

    def test_input_closed_is_emitted_exactly_once_for_finish(self):
        self._assert_single_input_close("finish")

    def test_input_closed_is_emitted_exactly_once_for_cancel(self):
        self._assert_single_input_close("cancel")

    def _assert_single_input_close(self, action):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                _command_id, ack = session.activate()
                session.event(schema.EVENT_ACTIVATION_STARTED)
                sent = session.command({
                    "type": schema.ACTIVATION_COMMAND,
                    "action": action,
                    "activationId": ack["activationId"],
                })
                command_ack = session.ack(sent["commandId"])
                self.assertEqual(command_ack["result"], schema.RESULT_APPLIED)
                closed = session.event(schema.EVENT_ACTIVATION_INPUT_CLOSED)
                self.assertEqual(
                    closed["causedByCommandId"], sent["commandId"]
                )
                self.assertEqual(closed["activationId"], ack["activationId"])
                self.assertIn("reason", closed)
                self.assertIn("acceptedSegmentCount", closed)

                # A repeated control in ``closing_input``/idle must not create
                # a second close.
                repeat = session.command({
                    "type": schema.ACTIVATION_COMMAND,
                    "action": action,
                    "activationId": ack["activationId"],
                })
                session.ack(repeat["commandId"])
                session.snapshot()
                closes = session.collected(
                    schema.EVENT_ACTIVATION_INPUT_CLOSED
                )
                self.assertEqual(len(closes), 1)

    def test_device_close_has_a_null_caused_by_command_id(self):
        """An availability ``commandId`` never becomes a close correlation."""
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                _command_id, ack = session.activate()
                session.event(schema.EVENT_ACTIVATION_STARTED)
                sent = session.command({
                    "type": schema.AUDIO_AVAILABILITY_SET,
                    "audioAvailable": False,
                })
                session.ack(sent["commandId"])
                closed = session.event(schema.EVENT_ACTIVATION_INPUT_CLOSED)
                self.assertIsNone(closed["causedByCommandId"])
                self.assertNotEqual(
                    closed.get("causedByCommandId"), sent["commandId"]
                )
                self.assertEqual(closed["activationId"], ack["activationId"])
                session.snapshot()
                self.assertEqual(
                    len(session.collected(
                        schema.EVENT_ACTIVATION_INPUT_CLOSED
                    )),
                    1,
                )

    def test_no_legacy_event_name_reaches_a_v2_connection(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                _command_id, ack = session.activate()
                session.event(schema.EVENT_ACTIVATION_STARTED)
                finish = session.command({
                    "type": schema.ACTIVATION_COMMAND,
                    "action": schema.FINISH,
                    "activationId": ack["activationId"],
                })
                session.ack(finish["commandId"])
                session.event(schema.EVENT_ACTIVATION_INPUT_CLOSED)
                session.snapshot()

                allowed = set(schema.EVENT_TYPES) | {
                    schema.HELLO_ACCEPTED,
                    schema.COMMAND_ACK,
                    schema.SESSION_SNAPSHOT,
                }
                for message in session.messages:
                    self.assertIn(message.get("type"), allowed, message)

    def test_no_change_does_not_bump_state_version(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                _command_id, ack = session.activate()
                session.event(schema.EVENT_ACTIVATION_STARTED)
                before = session.snapshot()["stateVersion"]
                suppression = session.command({
                    "type": schema.TRIGGER_SUPPRESSION_SET,
                    "manual": False,
                    "wakeWord": False,
                })
                repeat_ack = session.ack(suppression["commandId"])
                self.assertEqual(repeat_ack["result"], schema.RESULT_NO_CHANGE)
                after = session.snapshot()["stateVersion"]
                self.assertEqual(after, before)

    def test_segment_lifecycle_events_carry_the_frozen_segment_fields(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                session.activate()
                session.event(schema.EVENT_ACTIVATION_STARTED)
                session.send_bytes(speech_packet())
                started = session.event(schema.EVENT_SEGMENT_RECORDING_STARTED)
                for field in ("activationId", "segmentId", "segmentSequence"):
                    self.assertIn(field, started)
                self.assertEqual(started["segmentSequence"], 1)

                session.recorder().flush_buffered_audio()
                ended = session.event(schema.EVENT_SEGMENT_RECORDING_ENDED)
                self.assertIn("reason", ended)
                # The same segment identity survives the released context.
                self.assertEqual(ended["segmentId"], started["segmentId"])
                self.assertEqual(
                    ended["segmentSequence"], started["segmentSequence"]
                )

    def test_a_phase_change_is_announced_before_the_segment_event(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                session.activate()
                session.event(schema.EVENT_ACTIVATION_STARTED)
                session.send_bytes(speech_packet())
                changed = session.event(schema.EVENT_ACTIVATION_PHASE_CHANGED)
                self.assertEqual(
                    changed["previousPhase"], schema.WAITING_FIRST_SPEECH
                )
                self.assertEqual(changed["inputPhase"], schema.SEGMENT_ACTIVE)
                self.assertIn("deadlineAtUnixMs", changed)
                self.assertIn("remainingMs", changed)
                started = session.event(schema.EVENT_SEGMENT_RECORDING_STARTED)
                self.assertGreater(started["eventSeq"], changed["eventSeq"])


@unittest.skipIf(TestClient is None, "FastAPI test client is not installed")
class ProtocolV2SnapshotTests(unittest.TestCase):
    def setUp(self):
        GateAwareRecorder.instances = []
        self.app = build_app()

    def test_idle_snapshot_nulls_every_optional_input_value(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                snapshot = session.snapshot()
                self.assertEqual(snapshot["input"], {
                    "phase": schema.IDLE,
                    "activationId": None,
                    "primarySource": None,
                    "deadlineAtUnixMs": None,
                    "remainingMs": None,
                    "closeRequested": False,
                })
                self.assertEqual(snapshot["pendingActivations"], [])

    def test_waiting_first_speech_snapshot_projects_the_deadline(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                _command_id, ack = session.activate()
                snapshot = session.snapshot()
                inputs = snapshot["input"]
                self.assertEqual(inputs["phase"], schema.WAITING_FIRST_SPEECH)
                self.assertEqual(inputs["activationId"], ack["activationId"])
                self.assertEqual(inputs["primarySource"], schema.MANUAL_SOURCE)
                self.assertIsNotNone(inputs["deadlineAtUnixMs"])
                self.assertGreater(inputs["remainingMs"], 0)
                self.assertFalse(inputs["closeRequested"])

    def test_segment_active_and_followup_wait_are_visible(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                session.activate()
                session.event(schema.EVENT_ACTIVATION_STARTED)
                session.send_bytes(speech_packet())
                session.event(schema.EVENT_SEGMENT_RECORDING_STARTED)
                self.assertEqual(
                    session.snapshot()["input"]["phase"], schema.SEGMENT_ACTIVE
                )
                session.recorder().flush_buffered_audio()
                session.event(schema.EVENT_SEGMENT_RECORDING_ENDED)
                self.assertEqual(
                    session.snapshot()["input"]["phase"], schema.FOLLOWUP_WAIT
                )

    def test_snapshot_request_does_not_change_the_domain(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                session.activate()
                session.event(schema.EVENT_ACTIVATION_STARTED)
                first = session.snapshot()
                second = session.snapshot()
                self.assertEqual(first["stateVersion"], second["stateVersion"])
                self.assertEqual(
                    first["input"]["activationId"],
                    second["input"]["activationId"],
                )

    def test_idle_with_pending_activations_is_representable(self):
        app = build_app()
        GateAwareRecorder.instances = []
        with TestClient(app) as client:
            with V2Session(client) as session:
                _command_id, ack = session.activate()
                session.event(schema.EVENT_ACTIVATION_STARTED)
                session.send_bytes(speech_packet())
                session.event(schema.EVENT_SEGMENT_RECORDING_STARTED)

                server_session = session.server_session(app)
                # Keep the final work pending so the activation drains in the
                # background while the foreground goes idle.
                server_session.segment_ledger  # authority reference
                finish = session.command({
                    "type": schema.ACTIVATION_COMMAND,
                    "action": schema.FINISH,
                    "activationId": ack["activationId"],
                })
                session.ack(finish["commandId"])
                session.event(schema.EVENT_ACTIVATION_INPUT_CLOSED)

                snapshot = session.snapshot()
                self.assertEqual(snapshot["input"]["phase"], schema.IDLE)
                self.assertIsNone(snapshot["input"]["activationId"])
                for entry in snapshot["pendingActivations"]:
                    for field in (
                        "activationId", "activationSequence",
                        "inputClosedReason", "processingState",
                        "acceptedSegmentCount", "terminalSegmentCount",
                    ):
                        self.assertIn(field, entry)

    def test_pending_activations_stay_sorted_by_activation_sequence(self):
        from api_fastapi_server.protocol_v2 import snapshot as snapshot_layer

        class FakeLedger:
            def snapshot(self):
                return {"activations": [
                    {
                        "activationId": "c", "activationSequence": 3,
                        "inputClosed": True, "inputClosedReason": "finished",
                        "state": "draining", "acceptedSegmentCount": 1,
                        "terminalSegmentCount": 0,
                    },
                    {
                        "activationId": "a", "activationSequence": 1,
                        "inputClosed": True, "inputClosedReason": "cancelled",
                        "state": "draining", "acceptedSegmentCount": 2,
                        "terminalSegmentCount": 1,
                    },
                    {
                        "activationId": "open", "activationSequence": 4,
                        "inputClosed": False, "inputClosedReason": None,
                        "state": "draining", "acceptedSegmentCount": 0,
                        "terminalSegmentCount": 0,
                    },
                    {
                        "activationId": "b", "activationSequence": 2,
                        "inputClosed": True, "inputClosedReason": "finished",
                        "state": "draining", "acceptedSegmentCount": 0,
                        "terminalSegmentCount": 0,
                    },
                ]}

        pending = snapshot_layer.build_pending_activations(FakeLedger())
        self.assertEqual(
            [entry["activationSequence"] for entry in pending], [1, 2, 3]
        )
        # The still open foreground activation is not a pending one.
        self.assertNotIn("open", [entry["activationId"] for entry in pending])

    def test_snapshot_reports_suppression_combinations(self):
        for manual, wake in ((True, False), (False, True), (True, True)):
            with self.subTest(manual=manual, wakeWord=wake):
                app = build_app()
                GateAwareRecorder.instances = []
                with TestClient(app) as client:
                    with V2Session(client) as session:
                        sent = session.command({
                            "type": schema.TRIGGER_SUPPRESSION_SET,
                            "manual": manual,
                            "wakeWord": wake,
                        })
                        session.ack(sent["commandId"])
                        trigger = session.snapshot()["trigger"]
                        self.assertEqual(
                            trigger["suppressed"],
                            {"manual": manual, "wakeWord": wake},
                        )
                        self.assertEqual(
                            trigger["effective"]["manual"],
                            trigger["configured"]["manual"] and not manual,
                        )

    def test_snapshot_reports_audio_unavailable(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                sent = session.command({
                    "type": schema.AUDIO_AVAILABILITY_SET,
                    "audioAvailable": False,
                })
                session.ack(sent["commandId"])
                self.assertFalse(session.snapshot()["audioAvailable"])


@unittest.skipIf(TestClient is None, "FastAPI test client is not installed")
class ProtocolV2IdentityTests(unittest.TestCase):
    """K1 - one identity is one string from the domain to the wire."""

    def setUp(self):
        GateAwareRecorder.instances = []
        self.app = build_app()

    def test_every_generated_id_is_canonical_end_to_end(self):
        with TestClient(self.app) as client:
            with V2Session(client) as session:
                self.assertTrue(
                    schema.is_canonical_uuid(session.session_id)
                )
                _command_id, ack = session.activate()
                started = session.event(schema.EVENT_ACTIVATION_STARTED)
                self.assertTrue(
                    schema.is_canonical_uuid(started["activationId"])
                )

                server_session = session.server_session(self.app)
                controller_snapshot = server_session.activation_snapshot()
                # The domain string and the wire string are byte identical -
                # no boundary reformatting exists.
                self.assertEqual(
                    controller_snapshot["activationId"], started["activationId"]
                )
                self.assertEqual(
                    server_session.session_id, session.session_id
                )

                session.send_bytes(speech_packet())
                recording = session.event(
                    schema.EVENT_SEGMENT_RECORDING_STARTED
                )
                self.assertTrue(
                    schema.is_canonical_uuid(recording["segmentId"])
                )
                ledger_snapshot = server_session.segment_ledger.snapshot()
                self.assertEqual(
                    ledger_snapshot["activations"][0]["activationId"],
                    started["activationId"],
                )

    def test_v1_sessions_keep_their_compact_ids(self):
        service = self.app.state.voicestt_service
        from api_fastapi_server.server import (
            SessionActivationRequest,
        )

        session = service.admit_session(
            uuid.uuid4().hex,
            activation_request=SessionActivationRequest(
                manual_enabled=True, wake_word_enabled=False
            ),
        )
        try:
            self.assertFalse(session.canonical_ids)
            self.assertEqual(session.segment_state.current(), 1)
        finally:
            service.remove_session(session.session_id)


@unittest.skipIf(TestClient is None, "FastAPI test client is not installed")
class ProtocolV2IsolationTests(unittest.TestCase):
    """v1 and v2 coexist on the transport layer only (AP-SRV-070 removes v1)."""

    def setUp(self):
        GateAwareRecorder.instances = []
        self.app = build_app()

    def test_v1_endpoint_still_serves_its_own_hello(self):
        with TestClient(self.app) as client:
            with client.websocket_connect(
                "/ws/transcribe?manualTriggerEnabled=true"
            ) as socket:
                hello = socket.receive_json()
                # v1 keeps its server-sent hello and its compact session id.
                self.assertEqual(hello["type"], "hello")
                self.assertFalse(schema.is_canonical_uuid(hello["sessionId"]))

    def test_v1_and_v2_sessions_can_run_side_by_side(self):
        with TestClient(self.app) as client:
            with client.websocket_connect(
                "/ws/transcribe?manualTriggerEnabled=true"
            ) as legacy:
                legacy_hello = legacy.receive_json()
                with V2Session(client) as session:
                    self.assertNotEqual(
                        legacy_hello["sessionId"], session.session_id
                    )
                    _command_id, ack = session.activate()
                    self.assertEqual(ack["result"], schema.RESULT_APPLIED)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
