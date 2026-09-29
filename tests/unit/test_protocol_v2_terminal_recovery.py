"""AP-SRV-080-FIX-02 — Terminale Recovery muss den V2-Transport schließen.

Tests A–D gegen den echten produktiven Endpoint ``/ws/v2`` mit echter Session.

- A: terminale Recovery ohne weitere Clientnachricht → Close 1011.
- B: Ressourcenfreigabe (Registry, Slot, neuer Handshake).
- C: Idempotenz doppelter/konkurrierender Closes.
- D: keine Regression (Disconnect, Handshake-Fehler, finish/cancel).
- E: äußere Endpoint-Cancellation räumt Receive-/Close-Tasks ohne Waisen auf.
- F: fataler Writerfehler schließt mit internem Close-Code 1011.
"""

import asyncio
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


def _v2_endpoint(app):
    for route in app.routes:
        if getattr(route, "path", None) == "/ws/v2":
            return route.endpoint
    raise AssertionError("keine /ws/v2-Route gefunden")


class _FakeWebSocket:
    """Minimaler Transport-Stub für die echte Endpoint-Closure.

    Führt den produktiven ``websocket_protocol_v2``-Code aus (Sink, Writer,
    Receive-Schleife, Cleanup), nur der Socket ist gestellt.
    """

    def __init__(self, inbound_texts=(), fail_send=False):
        self.query_params = {}
        self.headers = {}
        self._inbound = list(inbound_texts)
        self._fail_send = fail_send
        self.sent_texts = []
        self.close_code = None
        self.accepted = False
        self.blocked = asyncio.Event()

    async def accept(self):
        self.accepted = True

    async def receive(self):
        if self._inbound:
            return {"type": "websocket.receive", "text": self._inbound.pop(0)}
        self.blocked.set()
        await asyncio.Future()

    async def send_text(self, text):
        if self._fail_send:
            raise RuntimeError("boom")
        self.sent_texts.append(text)

    async def close(self, code=1000):
        self.close_code = code


async def _wait_for_sent(fake, expected_type, timeout=15.0):
    async def _poll():
        while True:
            for raw in list(fake.sent_texts):
                try:
                    message = json.loads(raw)
                except ValueError:
                    continue
                if message.get("type") == expected_type:
                    return message
            await asyncio.sleep(0.01)

    return await asyncio.wait_for(_poll(), timeout=timeout)


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
            # Ungültiger Handshake → 4400, keine Session (strikt, begrenzt).
            with client.websocket_connect("/ws/v2") as bad:
                bad.send_text("{not json")
                inbox, stop, reader = start_background_reader(bad)
                try:
                    close_code, seen = wait_for_disconnect(inbox)
                finally:
                    stop.set()
                    try:
                        bad.close()
                    except Exception:
                        pass
                    reader.join(timeout=10.0)
                self.assertEqual(
                    close_code,
                    schema.CLOSE_INVALID_HANDSHAKE,
                    f"erwartet 4400; close={close_code} interim={seen[-5:]}",
                )
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
                    inbox, stop, reader = start_background_reader(socket)
                    try:
                        close_code, seen = wait_for_disconnect(inbox)
                    finally:
                        stop.set()
                        try:
                            socket.close()
                        except Exception:
                            pass
                        reader.join(timeout=10.0)
                    self.assertEqual(
                        close_code,
                        schema.CLOSE_HANDSHAKE_TIMEOUT,
                        f"erwartet 4408; close={close_code} "
                        f"interim={seen[-5:]}",
                    )
        self.assertEqual(len(app.state.voicestt_service.sessions.all()), 0)


class EndpointFailureTests(unittest.IsolatedAsyncioTestCase):
    """Gezielte Failure-Tests gegen die produktive Endpoint-Closure."""

    async def test_e_outer_cancellation_awaits_child_tasks(self):
        GateAwareRecorder.instances = []
        app = build_app()
        service = app.state.voicestt_service
        endpoint = _v2_endpoint(app)
        fake = _FakeWebSocket(inbound_texts=[json.dumps(hello_message())])
        endpoint_task = asyncio.create_task(endpoint(fake))
        try:
            accepted = await _wait_for_sent(fake, schema.HELLO_ACCEPTED)
            session_id = accepted["sessionId"]
            self.assertIsNotNone(service.sessions.get(session_id))
            # Deterministisch: Der Endpoint blockiert jetzt in asyncio.wait.
            await asyncio.wait_for(fake.blocked.wait(), timeout=15.0)
            endpoint_task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await endpoint_task
        finally:
            if not endpoint_task.done():
                endpoint_task.cancel()
                try:
                    await endpoint_task
                except asyncio.CancelledError:
                    pass
        for _ in range(50):
            pending = [
                task for task in asyncio.all_tasks()
                if task is not asyncio.current_task() and not task.done()
            ]
            if not pending:
                break
            await asyncio.sleep(0)
        self.assertEqual(pending, [])
        self.assertIsNone(service.sessions.get(session_id))

    async def test_f_fatal_writer_error_closes_with_1011(self):
        GateAwareRecorder.instances = []
        app = build_app()
        service = app.state.voicestt_service
        endpoint = _v2_endpoint(app)
        fake = _FakeWebSocket(
            inbound_texts=[json.dumps(hello_message())], fail_send=True
        )
        # Muss regulär zurückkehren (nicht hängen) und mit 1011 schließen.
        await asyncio.wait_for(endpoint(fake), timeout=15.0)
        self.assertEqual(fake.sent_texts, [])
        self.assertEqual(fake.close_code, schema.CLOSE_INTERNAL_ERROR)
        self.assertEqual(len(service.sessions.all()), 0)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
