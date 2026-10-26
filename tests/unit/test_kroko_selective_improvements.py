"""Regression tests for Kroko V2 changes extracted from draft PR #14.

All license transport interactions are synthetic and never contact Kroko.
"""
import asyncio
import json
from types import SimpleNamespace
from unittest import mock

import pytest

from VoiceSTT.kroko.credentials import effective_recognizer_key
from VoiceSTT.kroko.license_api import LicenseCheckResult, check_onprem_license
from VoiceSTT.kroko.license_state import KrokoLicenseState
from VoiceSTT.kroko.models import KrokoModelManifest, community_fallback_model
from VoiceSTT.transcription_engines.kroko_onnx_engine import KrokoOnnxBackend

MODEL = "123e4567-e89b-12d3-a456-426614174000"
OTHER_MODEL = "123e4567-e89b-12d3-a456-426614174001"
KEY = "secret-do-not-log"


@pytest.mark.parametrize("options,expected", [
    ({}, "env"),
    ({"key": "outer"}, "outer"),
    ({"key": "outer", "recognizer": {"key": "inner"}}, "inner"),
    ({"key": "outer", "recognizer": {"key": ""}}, ""),
    ({"recognizer": {"key": None}}, None),
])
def test_effective_key_matches_native_kwargs_override(options, expected):
    environment = {"KROKO_API_KEY": "env"}
    assert effective_recognizer_key(options, environ=environment) == expected
    backend = object.__new__(KrokoOnnxBackend)
    backend.config = SimpleNamespace()
    backend.engine_options = dict(options)
    backend.model_path = "synthetic.data"
    backend.sample_rate = 16000
    with mock.patch.dict("os.environ", environment, clear=True):
        assert backend._recognizer_kwargs()["key"] == expected


def test_key_env_precedence_and_missing_key():
    assert effective_recognizer_key({}, environ={}) == ""
    assert effective_recognizer_key({}, environ={
        "KROKO_KEY": "last", "VOICESTT_KROKO_ONNX_KEY": "third",
        "KROKO_ONNX_KEY": "second", "KROKO_API_KEY": "first",
    }) == "first"


class FakeSocket:
    def __init__(self, value):
        self.value = value
        self.closed = False

    def recv(self):
        if isinstance(self.value, Exception):
            raise self.value
        return self.value

    def close(self):
        self.closed = True


def test_license_probe_validates_specific_model_with_conservative_ttl():
    conn = FakeSocket(json.dumps({
        "allowed": True, "remaining_seconds": 86400,
        "offline_timeout": 60, "report_interval": 15,
    }))
    received = []

    def connect(url, **kw):
        received.append((url, kw))
        return conn

    result = check_onprem_license(KEY, MODEL, connect=connect)
    assert result.allowed and result.status == "VALID"
    assert result.model_uuid == MODEL and result.max_age_seconds == 60
    assert received[0][0] == f"wss://license.kroko.ai/ws/v1/{KEY}/{MODEL}"
    assert received[0][1]["timeout"] == 5
    assert conn.closed


@pytest.mark.parametrize("reply,status", [
    ({"allowed": False}, "INVALID"),
    ({"allowed": "true", "remaining_seconds": 60, "offline_timeout": 60}, "CHECK_FAILED"),
    ({"allowed": True, "remaining_seconds": 0, "offline_timeout": 60}, "CHECK_FAILED"),
    ({"allowed": True, "remaining_seconds": True, "offline_timeout": 60}, "CHECK_FAILED"),
    ({"allowed": True, "remaining_seconds": 60, "offline_timeout": 0}, "CHECK_FAILED"),
    ({"allowed": True, "remaining_seconds": 60, "offline_timeout": 60, "error": "revoked"}, "CHECK_FAILED"),
    ({"remaining_seconds": 60}, "CHECK_FAILED"),
])
def test_license_probe_fails_closed_for_invalid_reply(reply, status):
    socket = FakeSocket(json.dumps(reply))
    result = check_onprem_license(KEY, MODEL, connect=lambda *a, **kw: socket)
    assert result.status == status
    assert not result.allowed
    assert socket.closed
    assert KEY not in repr(result)


def test_license_probe_handles_transport_and_malformed_reply_without_secret():
    for bad in (RuntimeError("provider returned " + KEY),
                ValueError("bad websocket response " + KEY)):
        def connect(*_args, **_kwargs):
            raise bad
        result = check_onprem_license(KEY, MODEL, connect=connect)
        assert result.status == "CHECK_FAILED"
        assert KEY not in repr(result)
        assert not result.allowed
    socket = FakeSocket("{invalid")
    result = check_onprem_license(KEY, MODEL, connect=lambda *_a, **_k: socket)
    assert result.status == "CHECK_FAILED" and socket.closed
    assert not result.allowed


def test_license_probe_never_connects_without_key_or_valid_model():
    connect = mock.Mock(side_effect=AssertionError("must not connect"))
    assert check_onprem_license("", MODEL, connect=connect).status == "NOT_CHECKED"
    assert check_onprem_license(KEY, "bad-id", connect=connect).status == "CHECK_FAILED"
    assert check_onprem_license(KEY, MODEL, timeout=float("nan"), connect=connect).status == "CHECK_FAILED"
    connect.assert_not_called()


def test_license_state_rejects_stale_generations_and_other_models():
    clock = [10.0]
    state = KrokoLicenseState(clock=lambda: clock[0])
    state.bind(key=KEY)
    old = state.begin(MODEL)
    state.bind(key="rotated-secret")
    assert not state.apply(old, LicenseCheckResult("VALID", MODEL, 20, "ok"))
    current = state.begin(MODEL)
    assert state.apply(current, LicenseCheckResult("VALID", MODEL, 10, "ok"))
    assert state.pro_enabled_for(MODEL)
    assert not state.pro_enabled_for(OTHER_MODEL)
    assert KEY not in repr(state.public_snapshot())
    assert "rotated-secret" not in repr(state.public_snapshot())
    clock[0] = 20.0
    assert not state.pro_enabled_for(MODEL)
    assert state.public_snapshot()["status"] == "CHECK_FAILED"


def test_license_state_force_community_invalidates_proof():
    state = KrokoLicenseState()
    state.bind(key=KEY)
    generation = state.begin(MODEL)
    assert state.apply(generation, LicenseCheckResult("VALID", MODEL, 20, "ok"))
    assert state.pro_enabled_for(MODEL)
    state.bind(key=KEY, force_community=True)
    assert not state.pro_enabled_for(MODEL)
    assert state.begin(MODEL) is None
    assert state.public_snapshot()["status"] == "NOT_CHECKED"


def test_license_state_rejects_old_result_and_model_mismatch():
    state = KrokoLicenseState()
    state.bind(key=KEY)
    previous = state.begin(MODEL)
    current = state.begin(OTHER_MODEL)
    assert not state.apply(previous, LicenseCheckResult("VALID", MODEL, 20, "ok"))
    assert not state.apply(current, LicenseCheckResult("VALID", MODEL, 20, "ok"))
    assert state.apply(current, LicenseCheckResult("INVALID", OTHER_MODEL, reason="license_rejected"))
    assert not state.pro_enabled_for(OTHER_MODEL)


def test_community_fallback_prefers_original_then_language_then_first():
    manifest = KrokoModelManifest({"models": [
        {"id": "en", "filename": "Kroko-EN-Community-64-L-Streaming-001.data",
         "language": "en", "tier": "community", "requiresRuntimeVariant": "free",
         "redistributionStatus": "POLICY_REQUIRED"},
        {"id": "de", "filename": "Kroko-DE-Community-64-L-Streaming-001.data",
         "language": "de", "tier": "community", "requiresRuntimeVariant": "free",
         "redistributionStatus": "POLICY_REQUIRED"},
        {"id": "pro", "filename": "Kroko-DE-Pro-16-L-Streaming-001.data",
         "language": "de", "tier": "pro", "requiresRuntimeVariant": "pro",
         "redistributionStatus": "PROHIBITED"},
    ]})
    assert community_fallback_model(manifest, "de").id == "de"
    assert community_fallback_model(manifest, "pro").id == "de"
    assert community_fallback_model(manifest, "unknown").id == "en"
    assert community_fallback_model(KrokoModelManifest({"models": []}), "pro") is None


def test_fastapi_lifespan_stops_service_even_when_start_raises(tmp_path):
    from api_fastapi_server.server import ServerSettings, create_app
    from tests.unit.test_openai_compatible_endpoint import ImmediateScheduler

    app = create_app(ServerSettings(data_root_path=str(tmp_path),
                                    model_warmup=False),
                     scheduler_factory=ImmediateScheduler)
    service = app.state.voicestt_service
    with (mock.patch.object(service, "start", side_effect=RuntimeError("synthetic startup failure")),
          mock.patch.object(service, "stop") as stop):
        async def run():
            async with app.router.lifespan_context(app):
                pass
        with pytest.raises(RuntimeError, match="synthetic startup failure"):
            asyncio.run(run())
        stop.assert_called_once()
