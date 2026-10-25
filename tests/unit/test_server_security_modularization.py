"""Contract tests for security extraction and OpenAI route registration.

Synthetic credentials and model-license responses only; no external contacts.
"""

from types import SimpleNamespace
from unittest import mock

from fastapi import FastAPI
from starlette.datastructures import Headers

from api_fastapi_server.security import SecurityService
from api_fastapi_server.security.logs import LogTokenAuthority, TOKEN_LIFETIME_SECONDS
from api_fastapi_server.server import ServerSettings, create_app
from VoiceSTT.kroko.license_api import LicenseCheckResult

MODEL_UUID = "123e4567-e89b-12d3-a456-426614174000"


def request(headers=None, host="203.0.113.7", path="/api/models"):
    return SimpleNamespace(
        headers=Headers(headers or {}),
        client=SimpleNamespace(host=host),
        url=SimpleNamespace(path=path),
    )


def security(*, admin=None, openai=None):
    return SecurityService(ServerSettings(
        admin_api_key=admin, openai_api_key=openai, model_warmup=False
    ))


def test_admin_gate_preserves_header_precedence_and_local_no_key_policy(monkeypatch):
    monkeypatch.delenv("VOICESTT_ADMIN_API_KEY", raising=False)
    gate = security(admin="test-admin")
    assert gate.admin_http_error(request({"X-VoiceSTT-Admin-Key": "test-admin"})) is None
    assert gate.admin_http_error(request({"Authorization": "Bearer test-admin"})) is None
    assert gate.admin_http_error(request({"X-Admin-Key": "test-admin"})) is None
    # The explicit VoiceSTT header retains precedence over Bearer.
    rejected = gate.admin_http_error(request({
        "X-VoiceSTT-Admin-Key": "bad",
        "Authorization": "Bearer test-admin",
    }))
    assert rejected.status_code == 401
    assert rejected.headers["www-authenticate"] == "Bearer"
    assert b"test-admin" not in rejected.body
    assert gate.admin_http_error(request({"Authorization": "Bearer bad"})).status_code == 401

    gate = security()
    assert gate.admin_http_error(request(host="127.0.0.1")) is None
    assert gate.admin_http_error(request(host="testclient")) is None
    assert gate.admin_http_error(request(host="::1")) is None
    assert gate.admin_http_error(request()).status_code == 403


def test_admin_key_is_live_from_env_when_not_explicit(monkeypatch):
    gate = security()
    monkeypatch.setenv("VOICESTT_ADMIN_API_KEY", "env-admin")
    assert gate.admin_http_error(request({"X-Admin-Key": "env-admin"})) is None
    monkeypatch.setenv("VOICESTT_ADMIN_API_KEY", "rotated")
    assert gate.admin_http_error(request({"X-Admin-Key": "env-admin"})).status_code == 401
    assert gate.admin_http_error(request({"X-Admin-Key": "rotated"})) is None


def test_openai_key_is_optional_and_invalid_header_is_audited(monkeypatch):
    monkeypatch.delenv("VOICESTT_API_KEY", raising=False)
    audit = SimpleNamespace(event=mock.Mock())
    gate = security()
    normalizer = lambda value: str(value).strip().lower()
    req = request(path="/v1/audio/transcriptions")
    assert gate.openai_http_error(
        req, audit=audit, normalize_client_id=normalizer
    ) is None
    audit.event.assert_not_called()

    gate = security(openai="test-openai")
    assert gate.openai_http_error(
        request({"Authorization": "Bearer test-openai"}),
        audit=audit, normalize_client_id=normalizer,
    ) is None
    result = gate.openai_http_error(
        request({"Authorization": "Bearer wrong", "X-VoiceSTT-Client-ID": " CLIENT "},
                path="/v1/models"),
        audit=audit, normalize_client_id=normalizer,
    )
    assert result.status_code == 401
    assert result.headers["www-authenticate"] == "Bearer"
    assert b"invalid_api_key" in result.body
    assert b"test-openai" not in result.body
    audit.event.assert_called_once_with(
        "authentication.failed", transport="http", clientId="client",
        path="/v1/models", reason="invalid_api_key"
    )


def test_scoped_log_token_authority_expires_and_rejects_other_session():
    clock = [123.0]
    store = LogTokenAuthority(clock=lambda: clock[0])
    token, expiry = store.issue("session-a")
    assert len(token) == 64
    assert expiry == 123.0 + TOKEN_LIFETIME_SECONDS
    assert store.validate(token, "session-a")["sessionId"] == "session-a"
    assert store.validate(token, "session-b") is None
    clock[0] = expiry
    assert store.validate(token) is None


def test_http_and_websocket_log_scopes_preserve_distinct_admin_rules(monkeypatch):
    monkeypatch.delenv("VOICESTT_ADMIN_API_KEY", raising=False)
    gate = security(admin="admin-secret")
    token, _ = gate.log_tokens.issue("one")
    assert gate.log_http_scope(request({"X-VoiceSTT-Log-Token": token}),
                               "one") == {"admin": False, "sessionId": "one"}
    assert gate.log_http_scope(request({"Authorization": "Bearer " + token}),
                               "two") is None
    assert gate.log_http_scope(request({"X-VoiceSTT-Admin-Key": "admin-secret"}),
                               "two") == {"admin": True, "sessionId": "two"}
    assert gate.log_websocket_scope(token, "two") is None
    assert gate.log_websocket_scope(token, "one") == {"admin": False, "sessionId": "one"}
    assert gate.log_websocket_scope("admin-secret", "two") == {
        "admin": True, "sessionId": "two"
    }

    no_key = security()
    assert no_key.log_http_scope(request(host="127.0.0.1")) == {
        "admin": True, "sessionId": None
    }
    # The historical WebSocket contract does not grant implicit loopback admin.
    assert no_key.log_websocket_scope("") is None


def test_kroko_adapter_does_not_auto_check_and_requires_explicit_model(monkeypatch):
    monkeypatch.delenv("KROKO_API_KEY", raising=False)
    gate = security().kroko
    assert gate.state.public_snapshot()["status"] == "NOT_CHECKED"
    with mock.patch("api_fastapi_server.security.kroko.check_onprem_license") as probe:
        result = gate.check_model(MODEL_UUID, options={"key": "test-kroko"},
                                  force_community=True)
        assert result.status == "NOT_CHECKED"
        probe.assert_not_called()

        probe.return_value = LicenseCheckResult("VALID", MODEL_UUID, 20, "ok")
        result = gate.check_model(MODEL_UUID, options={"key": "test-kroko"})
        assert result.allowed
        probe.assert_called_once()
        assert gate.state.pro_enabled_for(MODEL_UUID)
        assert not gate.state.pro_enabled_for("123e4567-e89b-12d3-a456-426614174002")
        assert "test-kroko" not in repr(gate.state.public_snapshot())


def test_kroko_adapter_rejects_other_model_verdict_even_when_positive():
    gate = security().kroko
    other = "123e4567-e89b-12d3-a456-426614174001"
    with mock.patch(
        "api_fastapi_server.security.kroko.check_onprem_license",
        return_value=LicenseCheckResult("VALID", other, 30, "ok"),
    ):
        result = gate.check_model(MODEL_UUID, options={"key": "synthetic"})
    assert result.status == "CHECK_FAILED"
    assert not result.allowed
    assert not gate.state.pro_enabled_for(MODEL_UUID)
    assert not gate.state.pro_enabled_for(other)


def test_openai_routes_registered_without_an_import_cycle():
    """Verify public routes over HTTP, not version-specific app.routes internals."""
    from fastapi.testclient import TestClient

    from api_fastapi_server.openai_routes import create_openai_router
    from tests.unit.test_openai_compatible_endpoint import ImmediateScheduler, wav_bytes

    app = create_app(
        ServerSettings(model_warmup=False),
        scheduler_factory=ImmediateScheduler,
    )
    assert create_openai_router.__module__ == "api_fastapi_server.openai_routes"
    assert isinstance(app, FastAPI)

    # include_router may retain an internal router node in newer FastAPI
    # versions rather than flattening everything to objects with .path.
    # Real HTTP dispatch is the actual OpenAI API contract.
    with TestClient(app) as client:
        models = client.get("/v1/models")
        assert models.status_code == 200, models.text
        assert models.json()["object"] == "list"

        transcription = client.post(
            "/v1/audio/transcriptions",
            data={"model": "whisper-1"},
            files={"file": ("sample.wav", wav_bytes(), "audio/wav")},
        )
        assert transcription.status_code == 200, transcription.text
        assert "text" in transcription.json()
