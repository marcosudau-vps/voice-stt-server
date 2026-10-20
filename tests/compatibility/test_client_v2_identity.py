"""Opt-in new-pair check using unchanged client product code on real loopback.

This is deliberately separate from historical client tests pinned to ada13b0.
Only ASR/recorder and physical capture are fixtures; HTTP, WebSockets, client
transport/settings/media/logging and server protocol/domain code are real.
"""

import asyncio
import importlib
import json
import os
from pathlib import Path
import socket
import subprocess
import threading
import time

import httpx
import pytest
import uvicorn

from api_fastapi_server.server import ServerSettings, create_app
from tests.unit.test_server_controlled_e2e import AutoScheduler, GateAwareRecorder

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def client_product(monkeypatch):
    location = os.environ.get("VOICESTT_CLIENT_V2_ROOT")
    expected_commit = os.environ.get("VOICESTT_CLIENT_V2_COMMIT")
    if not location or not expected_commit:
        pytest.skip("requires an explicit unchanged client checkout and qualification commit")
    root = Path(location)
    observed = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    assert observed == expected_commit
    assert not subprocess.check_output(
        ["git", "-C", str(root), "status", "--porcelain", "--untracked-files=no"], text=True
    ).strip(), "client checkout changed"
    vector = "HEAD:tests/contracts/protocol-v2-vectors.json"
    assert subprocess.check_output(["git", "-C", str(root), "show", vector]) == (
        subprocess.check_output(["git", "-C", str(ROOT), "show", vector])
    )
    monkeypatch.syspath_prepend(str(root))
    product = importlib.import_module("voice_stt_client")
    assert Path(product.__file__).resolve().is_relative_to(root.resolve())
    return root


@pytest.fixture
def backend(tmp_path, monkeypatch):
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    monkeypatch.setenv("VOICESTT_SERVER_COMMIT", commit)
    settings = ServerSettings(
        model_warmup=False, data_root_path=str(tmp_path), realtime_processing_pause=0.0,
        realtime_min_audio_seconds=0.01, min_length_of_recording=0.0,
        post_speech_silence_duration=60.0,
        request_logging_enabled=True, request_log_stdout=False,
        system_event_logging_enabled=False, performance_logging_enabled=False,
        performance_log_mirror_enabled=False, transcription_logging_enabled=True,
        transcription_log_stdout=False, event_store_enabled=True, log_live_enabled=True,
    )
    app = create_app(settings, scheduler_factory=AutoScheduler, recorder_factory=GateAwareRecorder)
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(
        app, host="127.0.0.1", port=port, log_level="critical", access_log=False,
    ))
    thread = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 20
        while not server.started and thread.is_alive() and time.monotonic() < deadline:
            time.sleep(.01)
        assert server.started and thread.is_alive(), "isolated backend did not become ready"
        yield f"http://127.0.0.1:{port}", f"ws://127.0.0.1:{port}/ws/v2", commit
    finally:
        server.should_exit = True
        thread.join(15)
        sock.close()
        assert not thread.is_alive(), "isolated backend failed to stop"


class SyntheticCapture:
    is_running = False
    device_active = True
    on_audio_packet = None

    def probe(self):
        return None

    def start(self):
        self.is_running = True

    def stop(self):
        self.is_running = False

    def emit(self):
        self.on_audio_packet(b"\x10\x27" * 3200, 16000, 1, 3200)


async def until(predicate, *, seconds=15):
    async with asyncio.timeout(seconds):
        while not predicate():
            await asyncio.sleep(.01)


def test_unchanged_client_bootstrap_audio_controls_logs_and_new_identity(client_product, backend):
    from voice_stt_client.core import protocol_v2 as p
    from voice_stt_client.core.config import ServerConfig, EventStreamConfig
    from voice_stt_client.core.event_models import EventConnectionState
    from voice_stt_client.core.session_coordinator import DualSessionCoordinator
    from voice_stt_client.core.settings_service import SettingsService
    from voice_stt_client.core.v2_media import V2MediaConnection
    from voice_stt_client.core.v2_profile import V2Profile
    from voice_stt_client.core.v2_transport import V2STTSession, V2TransportConfig
    from websockets.asyncio.client import connect

    http_url, ws_url, commit = backend

    async def exercise():
        async with httpx.AsyncClient(base_url=http_url) as http:
            response = await http.get("/api/v2/info")
            info = response.json()
            assert response.headers["cache-control"] == "no-store"
            assert info["serverCommit"] == commit
            assert commit != "ada13b011e1d3829f78e7f389e3b927795a2b3be"
            messages = []
            session = V2STTSession(V2TransportConfig(
                url=ws_url, backoff_initial=.02, backoff_max=.1,
            ))
            session.on_message = lambda binding, message: messages.append(message)
            settings = SettingsService(
                session, V2Profile(desired_settings={"activation.followupTimeoutMs": 4000})
            )
            logs = DualSessionCoordinator(
                ServerConfig(url=ws_url), EventStreamConfig(cursor_persistence_enabled=False)
            )
            capture = SyntheticCapture()
            media = V2MediaConnection(session, capture, logs=logs, settings_bootstrap=settings.bootstrap)
            running = asyncio.create_task(session.run())
            try:
                await until(lambda: session.is_ready and media._gate)
                await until(lambda: logs.context.event_state == EventConnectionState.LIVE)
                accepted = session.binding.accepted
                for payload in (accepted.payload, accepted.snapshot.payload):
                    assert payload["serverVersion"] == info["serverVersion"]
                    assert payload["serverCommit"] == commit
                assert accepted.logAccess.payload["serverInstanceId"] == info["serverInstanceId"]
                assert accepted.logAccess.accessToken not in json.dumps(info)
                assert settings.report().effective["activation.followupTimeoutMs"] == 4000
                for route, decoder in (
                    ("/api/v2/settings/schema", p.decode_settings_schema),
                    ("/api/v2/settings/server", p.decode_server_settings),
                ):
                    payload = (await http.get(route)).json()
                    decoder(payload)
                    assert payload["serverCommit"] == commit
                    assert payload["serverVersion"] == info["serverVersion"]
                assert (await http.get("/openapi.json")).json()["info"]["version"] == info["serverVersion"]
                activation = await session.request(
                    p.CommandType.ACTIVATION, action="activate", source="manual"
                )
                assert activation.ack.accepted
                capture.emit()
                await until(lambda: any(message.type == p.EventType.RECORDING_STARTED for message in messages))
                finish = await session.request(
                    p.CommandType.ACTIVATION, action="finish", activationId=activation.ack.activationId
                )
                assert finish.ack.accepted
                await until(lambda: any(message.type == p.EventType.COMPLETED for message in messages))
                before = len(messages)
                assert (await session.request(p.CommandType.SNAPSHOT_REQUEST)).ack.accepted
                await until(lambda: any(isinstance(value, p.Snapshot) for value in messages[before:]))
                for value in messages[before:]:
                    if isinstance(value, p.Snapshot):
                        assert value.payload["serverCommit"] == commit
                        assert value.payload["serverVersion"] == info["serverVersion"]
                for incompatible in (True, False):
                    async with connect(ws_url) as ws:
                        hello = p.build_hello(
                            clientVersion="2.0.0", clientCommit="unknown", clientRunId=p.new_id(),
                            manual=True, wakeWord=False, wakeWordIds=[],
                            suppressManual=True, suppressWakeWord=True,
                        ).to_mapping()
                        if incompatible:
                            hello["supportedProtocolVersions"] = [999]
                        else:
                            hello["requestedSession"]["trigger"]["manual"] = False
                        await ws.send(json.dumps(hello))
                        refusal = p.decode_server_message(await asyncio.wait_for(ws.recv(), 5))
                        assert isinstance(refusal, p.HandshakeRejected)
                        assert refusal.payload["serverCommit"] == commit
                        assert refusal.payload["serverVersion"] == info["serverVersion"]
                previous = session.binding
                await session.reconnect(previous, "issue9-new-pair-test")
                await until(lambda: session.is_ready and session.binding is not previous)
                assert session.binding.session_id != previous.session_id
                assert session.binding.accepted.payload["serverCommit"] == commit
                assert (await http.get("/api/v2/info")).json() == info
            finally:
                await media.close()
                await settings.close()
                await session.stop()
                await asyncio.gather(running, return_exceptions=True)

    asyncio.run(exercise())
