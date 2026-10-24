import json

import pytest

from tests.unit.test_kroko_restintegration import authority, native_reply, PRO_ID
from VoiceSTT.kroko.native_status import NativeStatusVerifier
from VoiceSTT.kroko.license_runtime import LicenseStatus
from VoiceSTT_server.credential_redaction import redact_kroko_credentials
from tests.unit.test_stt_management_v2 import app_client


def simulated_pro(service):
    state, clock = authority()
    verifier = NativeStatusVerifier(lambda: native_reply(), {"native-model-uuid": PRO_ID})
    assert state.run_check(verifier, (PRO_ID,)) == LicenseStatus.VALID
    service.kroko_license = state
    service._kroko_native_candidate = True
    service.settings.transcription_engine = "kroko_onnx"
    service.settings.realtime_transcription_engine = "kroko_onnx"
    return clock


@pytest.mark.parametrize("public,admin,access_valid,client_valid,expected", [
    (False, False, False, False, False),
    (True, False, False, False, True),
    (False, True, False, False, True),
    (False, False, True, False, True),
    (False, False, False, True, True),
])
def test_client_right_is_separate_from_native_server_proof(app_client, public, admin, access_valid, client_valid, expected):
    _, service = app_client
    simulated_pro(service)
    service.settings.kroko_pro_access_public = public
    service.settings.kroko_pro_access_key = "separate-access-fixture"
    service.kroko_client_key_validator = lambda key: client_valid and key == "client-fixture"
    headers = {"x-kroko-client-key": "client-fixture"}
    if access_valid:
        headers["x-voicestt-pro-access-key"] = "separate-access-fixture"
    native_credentials = service._kroko_effective_key()
    assert service.authorize_pro_client(headers, admin=admin) is expected
    assert service._kroko_effective_key() == native_credentials
    assert not service.stt_model_manager.downloads.snapshot()


def test_public_access_ignores_an_explicit_invalid_client_key(app_client):
    _, service = app_client
    simulated_pro(service)
    service.settings.kroko_pro_access_public = True
    service.kroko_client_key_validator = lambda key: pytest.fail("public access must ignore the key")
    assert service.authorize_pro_client({"x-kroko-client-key": "invalid"})


def test_no_client_key_contract_means_no_client_key_permission_and_no_leaks(app_client):
    client, service = app_client
    simulated_pro(service)
    service.settings.kroko_pro_access_key = "must-never-leak-access-fixture"
    assert not service.authorize_pro_client({"x-kroko-client-key": "unqualified-key"})
    service.kroko_client_key_validator = lambda key: (_ for _ in ()).throw(RuntimeError("provider-secret"))
    assert not service.authorize_pro_client({"x-kroko-client-key": "unqualified-key"})
    payload = json.dumps(service.settings.public_dict())
    assert "must-never-leak-access-fixture" not in payload
    assert "provider-secret" not in payload
    assert "kroko_pro_access_key" not in redact_kroko_credentials({"kroko_pro_access_key": "secret"}, drop=True)


def test_expired_proof_cannot_authorize_any_client(app_client):
    _, service = app_client
    clock = simulated_pro(service)
    service.settings.kroko_pro_access_public = True
    clock.advance(9)
    assert not service.authorize_pro_client({}, admin=True)


@pytest.mark.parametrize("route", ["/ws/transcribe", "/ws/v2"])
def test_audio_websockets_reject_unentitled_clients_before_admission(app_client, monkeypatch, route):
    client, service = app_client
    simulated_pro(service)
    monkeypatch.setattr(service, "admit_session", lambda *a, **kw: pytest.fail("unauthorized side effect"))
    from starlette.websockets import WebSocketDisconnect
    with client.websocket_connect(route) as socket:
        if route == "/ws/transcribe":
            assert socket.receive_json()["code"] == "pro_access_required"
        with pytest.raises(WebSocketDisconnect) as error:
            socket.receive_json()
        assert error.value.code == 1008
