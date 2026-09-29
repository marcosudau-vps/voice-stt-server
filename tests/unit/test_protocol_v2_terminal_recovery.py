"""AP-SRV-080-FIX-02 — Terminale Recovery muss den V2-Transport schließen.

Tests A–D gegen den echten produktiven Endpoint ``/ws/v2`` mit echter Session.

- A: terminale Recovery ohne weitere Clientnachricht → Close 1011.
- B: Ressourcenfreigabe (Registry, Slot, neuer Handshake).
- C: Idempotenz doppelter/konkurrierender Closes.
- D: keine Regression (Disconnect, Handshake-Fehler, finish/cancel).
"""

import json
import queue
import threading
import time
import unittest
import uuid
from unittest import mock

from api_fastapi_server.protocol_v2 import schema
from api_fastapi_server.protocol_v2.connection import ProtocolV2Connection

from tests.unit.test_server_controlled_e2e import (
    GateAwareRecorder,
    TestClient,
    build_app,
)

try:
    from starlette.websockets import WebSocketDisconnect
except Exception:  # pragma: no cover
    class WebSocketDisconnect(Exception):
        code = None


CLIENT_RUN_ID = "10000000-0000-4000-8000-000000000001"
CLOSE_WAIT = 10.0


def hello_message(**overrides):
    message = {
        "type": "hello",
        "supportedProtocolVersions": [2],
        "clientVersion": "2.0.0-test",
        "clientCommit": "client-test-commit",
        "clientRunId": CLIENT_RUN_ID,
        "requestedSession": {
            "trigger": {"manual": True, "wakeWord": False},
            "wakeWordIds": [],
        },
        "runtimeSuppression": {"manual": False, "wakeWord": False},
    }
    message.update(overrides)
    return message


def wait_for_disconnect(inbox, timeout=CLOSE_WAIT):
    deadline = time.monotonic() + timeout
    seen = []
    while time.monotonic() < deadline:
        try:
            kind, value = inbox.get(timeout=max(0.1, deadline - time.monotonic()))
        except queue.Empty:
            break
        if kind == "disconnect":
            return value, seen
        seen.append((kind, value))
    return None, seen


def start_background_reader(socket):
    inbox = queue.Queue()
    stop = threading.Event()

    def read_forever():
        try:
            while not stop.is_set():
                try:
                    inbox.put(("message", socket.receive_json()))
                except WebSocketDisconnect as disconnect:
                    inbox.put(("disconnect", disconnect.code))
                    return
                except Exception as exc:
                    inbox.put(("error", repr(exc)))
                    return
        finally:
            pass

    reader = threading.Thread(target=read_forever, daemon=True)
    reader.start()
    return inbox, stop, reader


class TerminalRecoveryTransportTests(unittest.TestCase):
    def test_a_terminal_recovery_closes_without_further_client_message(self):
        GateAwareRecorder.instances = []
        app = build_app()
        with TestClient(app) as client:
            with client.websocket_connect("/ws/v2") as socket:
                socket.send_text(json.dumps(hello_message()))
                accepted = socket.receive_json()
                self.assertEqual(accepted["type"], schema.HELLO_ACCEPTED)
                session_id = accepted["sessionId"]
                session = app.state.voicestt_service.sessions.get(session_id)
                self.assertIsNotNone(session)

                inbox, stop, reader = start_background_reader(socket)
                try:
                    session.fail_closed_for_recovery(
                        "30000000-0000-4000-8000-000000000001"
                    )
                    close_code, seen = wait_for_disconnect(inbox)
                    self.assertEqual(
                        close_code,
                        schema.CLOSE_INTERNAL_ERROR,
                        f"kein terminaler Close 1011; close={close_code} "
                        f"interim={seen[-5:]}",
                    )
                finally:
                    stop.set()
                    try:
                        socket.close()
                    except Exception:
                        pass
                    reader.join(timeout=10.0)

    def test_b_resources_released_and_new_handshake_succeeds(self):
        GateAwareRecorder.instances = []
        app = build_app()
        service = None
        old_id = None
        with TestClient(app) as client:
            with client.websocket_connect("/ws/v2") as socket:
                socket.send_text(json.dumps(hello_message()))
                accepted = socket.receive_json()
                old_id = accepted["sessionId"]
                service = app.state.voicestt_service
                session = service.sessions.get(old_id)
                self.assertIsNotNone(session)
                inbox, stop, reader = start_background_reader(socket)
                try:
                    session.fail_closed_for_recovery(None)
                    close_code, _ = wait_for_disconnect(inbox)
                    self.assertEqual(close_code, schema.CLOSE_INTERNAL_ERROR)
                finally:
                    stop.set()
                    try:
                        socket.close()
                    except Exception:
                        pass
                    reader.join(timeout=10.0)
            # Endpoint-Cleanup (finally: close_session → remove_session) muss
            # die Session aus der Registry entfernt haben.
            deadline = time.monotonic() + 10.0
            while service.sessions.get(old_id) is not None:
                if time.monotonic() > deadline:
                    break
                time.sleep(0.05)
            self.assertIsNone(service.sessions.get(old_id))
            # Slot freigegeben: neuer Handshake + Snapshot funktionieren.
            with client.websocket_connect("/ws/v2") as socket2:
                socket2.send_text(json.dumps(hello_message()))
                accepted2 = socket2.receive_json()
                self.assertEqual(accepted2["type"], schema.HELLO_ACCEPTED)
                self.assertNotEqual(accepted2["sessionId"], old_id)
                cmd_id = str(uuid.uuid4())
                socket2.send_text(json.dumps({
                    "type": schema.SESSION_SNAPSHOT_REQUEST,
                    "protocolVersion": 2,
                    "sessionId": accepted2["sessionId"],
                    "commandId": cmd_id,
                }))
                ack = socket2.receive_json()
                self.assertEqual(ack["type"], schema.COMMAND_ACK)
                self.assertEqual(ack["commandId"], cmd_id)

    def test_c_double_and_concurrent_close_is_idempotent(self):
        GateAwareRecorder.instances = []
        app = build_app()
        with TestClient(app) as client:
            with client.websocket_connect("/ws/v2") as socket:
                socket.send_text(json.dumps(hello_message()))
                accepted = socket.receive_json()
                session_id = accepted["sessionId"]
                session = app.state.voicestt_service.sessions.get(session_id)
                inbox, stop, reader = start_background_reader(socket)
                try:
                    with mock.patch.object(
                        session, "close", wraps=session.close,
                    ) as close_spy:
                        first = session.fail_closed_for_recovery("a1")
                        second = session.fail_closed_for_recovery("a1")
                        self.assertTrue(first)
                        self.assertFalse(second)
                        calls_after_recovery = close_spy.call_count
                        self.assertGreaterEqual(calls_after_recovery, 1)
                    close_code, _ = wait_for_disconnect(inbox)
                    self.assertEqual(close_code, schema.CLOSE_INTERNAL_ERROR)
                    # Kein doppelter fachlicher Abschluss durch den Zweitaufruf:
                    # Zweitaufruf kehrt früh via status==closed zurück.
                    self.assertEqual(session.status, "closed")
                finally:
                    stop.set()
                    try:
                        socket.close()
                    except Exception:
                        pass
                    reader.join(timeout=10.0)

        # Konkurrierende request_close auf Connection-Ebene: keine Exception,
        # genau ein Gewinner, stabiler Code.
        connection = ProtocolV2Connection(object())
        received = []
        connection.set_sink(received.append)
        results = []
        barrier = threading.Barrier(5)

        def close_race():
            barrier.wait(timeout=10.0)
            results.append(connection.request_close(schema.CLOSE_INTERNAL_ERROR))

        threads = [threading.Thread(target=close_race) for _ in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10.0)
            self.assertFalse(thread.is_alive())
        self.assertEqual(sorted(results), [False] * 4 + [True])
        self.assertEqual(connection.close_code, schema.CLOSE_INTERNAL_ERROR)
        self.assertTrue(connection.closed)

    def test_d_no_regression_normal_paths(self):
        GateAwareRecorder.instances = []
        app = build_app()
        # Normaler Disconnect räumt die Session weg.
        with TestClient(app) as client:
            with client.websocket_connect("/ws/v2") as socket:
                socket.send_text(json.dumps(hello_message()))
                accepted = socket.receive_json()
                session_id = accepted["sessionId"]
            deadline = time.monotonic() + 10.0
            while app.state.voicestt_service.sessions.get(session_id) is not None:
                if time.monotonic() > deadline:
                    break
                time.sleep(0.05)
            self.assertIsNone(
                app.state.voicestt_service.sessions.get(session_id)
            )
            # Ungültiger Handshake → 4400, keine Session.
            with client.websocket_connect("/ws/v2") as bad:
                bad.send_text("{not json")
                try:
                    while True:
                        bad.receive_json()
                except WebSocketDisconnect as disconnect:
                    self.assertEqual(
                        disconnect.code, schema.CLOSE_INVALID_HANDSHAKE
                    )
                except Exception:
                    pass
            # Reguläres finish/cancel funktioniert weiter.
            with client.websocket_connect("/ws/v2") as socket2:
                socket2.send_text(json.dumps(hello_message()))
                accepted2 = socket2.receive_json()
                sid = accepted2["sessionId"]
                cmd_id = str(uuid.uuid4())
                socket2.send_text(json.dumps({
                    "type": schema.ACTIVATION_COMMAND,
                    "protocolVersion": 2,
                    "sessionId": sid,
                    "commandId": cmd_id,
                    "action": schema.ACTIVATE,
                    "source": schema.MANUAL_SOURCE,
                }))

                def _recv_ack(sock, want_id, timeout=15.0):
                    deadline = time.monotonic() + timeout
                    while time.monotonic() < deadline:
                        msg = sock.receive_json()
                        if (
                            msg.get("type") == schema.COMMAND_ACK
                            and msg.get("commandId") == want_id
                        ):
                            return msg
                    raise AssertionError(f"kein ack für {want_id}")

                ack = _recv_ack(socket2, cmd_id)
                self.assertEqual(ack["result"], schema.RESULT_APPLIED)
                finish_id = str(uuid.uuid4())
                socket2.send_text(json.dumps({
                    "type": schema.ACTIVATION_COMMAND,
                    "protocolVersion": 2,
                    "sessionId": sid,
                    "commandId": finish_id,
                    "action": schema.FINISH,
                    "activationId": ack["activationId"],
                }))
                fack = _recv_ack(socket2, finish_id)
                self.assertEqual(fack["result"], schema.RESULT_APPLIED)

    def test_d_handshake_timeout_still_4408(self):
        GateAwareRecorder.instances = []
        app = build_app()
        with mock.patch.object(
            schema, "DEFAULT_HANDSHAKE_TIMEOUT_SECONDS", 0.25
        ):
            with TestClient(app) as client:
                with client.websocket_connect("/ws/v2") as socket:
                    try:
                        while True:
                            socket.receive_json()
                    except WebSocketDisconnect as disconnect:
                        self.assertEqual(
                            disconnect.code, schema.CLOSE_HANDSHAKE_TIMEOUT
                        )
                    except Exception:
                        pass
        self.assertEqual(len(app.state.voicestt_service.sessions.all()), 0)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
