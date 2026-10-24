import json
import threading
import time
import uuid

import pytest
from starlette.websockets import WebSocket, WebSocketDisconnect

from api_fastapi_server import server
from tests.unit.test_fastapi_server_multi_user import FakeRecorder, ManualScheduler
from tests.unit.test_protocol_v2_e2e import hello_message
from tests.unit.test_server_controlled_e2e import GateAwareRecorder
from tests.unit.test_stt_management_v2 import app_client


def until(socket, kind):
    for _ in range(30):
        payload = socket.receive_json()
        if payload["type"] == kind:
            return payload
    pytest.fail("expected " + kind)


def slow_loader(service, monkeypatch, *, succeeds=True):
    entered, release, signal_sent = threading.Event(), threading.Event(), threading.Event()
    calls = []
    original = WebSocket.send_text

    async def send_text(websocket, data):
        await original(websocket, data)
        if json.loads(data).get("status") == "models_loading":
            signal_sent.set()

    monkeypatch.setattr(WebSocket, "send_text", send_text)
    monkeypatch.setattr(server, "MODEL_INITIALIZATION_STATUS_INTERVAL_SECONDS", .02)
    monkeypatch.setattr(server, "MODEL_INITIALIZATION_TIMEOUT_SECONDS", 2)

    class Slow(ManualScheduler):
        def wait_ready(self, timeout=None):
            calls.append(True)
            entered.set()
            assert release.wait(3)
            return succeeds

    service.scheduler = None
    service._model_state = "unloaded"
    service.scheduler_factory = Slow
    return entered, release, signal_sent, calls


def test_v1_signal_precedes_loader_and_http_remains_responsive_until_real_ready(app_client, monkeypatch):
    client, service = app_client
    entered, release, signal_sent, calls = slow_loader(service, monkeypatch)
    try:
        with client.websocket_connect("/ws/transcribe") as socket:
            first = socket.receive_json()
            assert first["type"] == "status" and first["sttReady"] is False
            assert signal_sent.is_set() and entered.wait(1)
            started = time.monotonic()
            status = client.get("/api/v2/server/status").json()
            assert time.monotonic() - started < 1
            assert status["modelState"] == "loading" and not status["loaded"]
            assert socket.receive_json()["status"] == "models_loading"
            release.set()
            assert until(socket, "hello")["sessionId"] == first["sessionId"]
            ready = until(socket, "ready")
            assert ready["ok"] and ready["models"]["loaded"]
            assert calls == [True]
    finally:
        release.set()


def test_v1_failed_lazy_load_is_an_error_never_ready(app_client, monkeypatch):
    client, service = app_client
    entered, release, _, calls = slow_loader(service, monkeypatch, succeeds=False)
    try:
        with client.websocket_connect("/ws/transcribe") as socket:
            assert socket.receive_json()["type"] == "status"
            assert entered.wait(1)
            release.set()
            error = until(socket, "error")
            assert error["code"] == "models_load_failed"
            with pytest.raises(WebSocketDisconnect):
                socket.receive_json()
        assert service.sessions.count() == 0 and service._model_state == "unloaded"
    finally:
        release.set()


def test_two_v1_clients_share_one_loader_and_receive_independent_hellos(app_client, monkeypatch):
    client, service = app_client
    entered, release, _, calls = slow_loader(service, monkeypatch)
    try:
        with client.websocket_connect("/ws/transcribe") as a:
            assert a.receive_json()["type"] == "status"
            assert entered.wait(1)
            with client.websocket_connect("/ws/transcribe") as b:
                assert b.receive_json()["type"] == "status"
                release.set()
                first, second = until(a, "hello"), until(b, "hello")
                assert first["sessionId"] != second["sessionId"]
                assert until(a, "ready")["models"]["loaded"]
                assert until(b, "ready")["models"]["loaded"]
                assert calls == [True]
    finally:
        release.set()


def test_v1_wait_is_bounded_and_timeout_creates_no_session(app_client, monkeypatch):
    client, service = app_client
    entered, release, _, _ = slow_loader(service, monkeypatch)
    monkeypatch.setattr(server, "MODEL_INITIALIZATION_TIMEOUT_SECONDS", .15)
    try:
        with client.websocket_connect("/ws/transcribe") as socket:
            assert socket.receive_json()["type"] == "status"
            assert until(socket, "error")["code"] == "models_load_failed"
        assert service.sessions.count() == 0
    finally:
        release.set()


def test_v2_accepts_before_asr_load_and_snapshot_stays_responsive(app_client, monkeypatch):
    client, service = app_client
    service.recorder_factory = GateAwareRecorder
    entered, release, _, calls = slow_loader(service, monkeypatch)
    worker = None
    try:
        with client.websocket_connect("/ws/v2") as socket:
            socket.send_json(hello_message())
            accepted = socket.receive_json()
            assert accepted["type"] == "hello.accepted" and not calls
            worker = threading.Thread(target=service.ensure_models_loaded)
            worker.start()
            assert entered.wait(1)
            command_id = str(uuid.uuid4())
            socket.send_json({"type": "session.snapshot.request", "protocolVersion": 2,
                              "sessionId": accepted["sessionId"], "commandId": command_id})
            snapshot = until(socket, "session.snapshot")
            assert snapshot["sessionId"] == accepted["sessionId"]
            assert client.get("/api/v2/server/status").json()["modelState"] == "loading"
            release.set()
            worker.join(2)
            assert not worker.is_alive() and calls == [True]
    finally:
        release.set()
        if worker is not None:
            worker.join(2)


def test_v2_timeout_during_slow_admission_cleans_late_session(app_client, monkeypatch):
    client, service = app_client
    entered, release = threading.Event(), threading.Event()

    def recorder(**kwargs):
        entered.set()
        assert release.wait(3)
        return GateAwareRecorder(**kwargs)

    service.recorder_factory = recorder
    monkeypatch.setattr(server, "MODEL_INITIALIZATION_TIMEOUT_SECONDS", .1)
    try:
        with client.websocket_connect("/ws/v2") as socket:
            socket.send_json(hello_message())
            assert entered.wait(1)
            with pytest.raises(WebSocketDisconnect) as error:
                socket.receive_json()
            assert error.value.code == 1011
            release.set()
            deadline = time.monotonic() + 2
            while service.sessions.snapshots()["pendingSessionAdmissions"] and time.monotonic() < deadline:
                time.sleep(.01)
            assert service.sessions.count() == 0
    finally:
        release.set()
