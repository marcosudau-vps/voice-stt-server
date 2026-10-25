"""Deterministic Kroko license lifecycle tests (PR #15 Korrekturlauf, D1).

Covers the decision truth table through the real component chain
(SecurityService -> KrokoLicenseGate -> KrokoLicenseState -> VoiceSTTService
-> STTModelManager) with synthetic transports, injected clocks and model
fakes only. No network, no native runtime, no secrets on disk.
"""
import asyncio
import json
import threading
from unittest import mock

import pytest

from VoiceSTT.kroko.license_api import LicenseCheckResult
from VoiceSTT.kroko.license_state import KrokoLicenseState
from VoiceSTT.kroko.models import (
    KrokoModelManifest,
    license_uuid_for,
    read_model_uuid,
)
from api_fastapi_server.security.kroko import KrokoLicenseGate
from api_fastapi_server import settings_control as settings_control_module
from VoiceSTT_server.stt_model_management import (
    OperatorIntent,
    ProductModel,
    STTModelManager,
)

MODEL = "123e4567-e89b-12d3-a456-426614174000"
OTHER_MODEL = "123e4567-e89b-12d3-a456-426614174001"
KEY = "synthetic-test-key"


class FakeSocket:
    def __init__(self, value):
        self.value = value
        self.closed = False
        self.url = None

    def recv(self):
        if isinstance(self.value, Exception):
            raise self.value
        return self.value

    def close(self):
        self.closed = True


def make_connect(value, record=None):
    sockets = []

    def connect(url, timeout=None):
        socket = FakeSocket(value)
        socket.url = url
        sockets.append(socket)
        return socket

    connect.sockets = sockets
    if record is not None:
        record.append(connect)
    return connect


def valid_reply(seconds=100, offline=100):
    return json.dumps({
        "allowed": True, "error": "", "remaining_seconds": seconds,
        "offline_timeout": offline,
    })


def write_data_file(root, filename, uuid):
    root.mkdir(parents=True, exist_ok=True)
    path = root / filename
    path.write_bytes(
        b'{"id": "' + uuid.encode("ascii") + b'", "type": "zipformer2", '
        b'"free": false}\x00' + b"\x00" * 256
    )
    return path


def synthetic_manifest():
    return KrokoModelManifest({
        "schemaVersion": 1,
        "models": [{
            "id": "pro-de-test", "filename": "Pro-DE-Test-Streaming-001.data",
            "language": "de", "tier": "pro", "requiresRuntimeVariant": "pro",
            "licenseClass": "commercial", "redistributionStatus": "PROHIBITED",
            "sha256": "0" * 64, "bytes": 1, "provenance": {},
        }],
    })


def commercial_product(model_id="pro-de-test", runtime_variant="pro"):
    return ProductModel(
        id=model_id, engine="kroko_onnx",
        filename=f"{model_id}.data",
        license_class="commercial", runtime_variant=runtime_variant,
    )


def gate_with_key(key=KEY):
    return KrokoLicenseGate(), {"key": key}


# -- header UUID mapping (B3) ----------------------------------------------

def test_read_model_uuid_from_header_and_rejects_garbage(tmp_path):
    good = write_data_file(tmp_path, "Pro-DE-Test-Streaming-001.data", MODEL)
    assert read_model_uuid(good) == MODEL
    assert read_model_uuid(tmp_path / "absent.data") is None
    plain = tmp_path / "plain.data"
    plain.write_bytes(b"no json header here" * 100)
    assert read_model_uuid(plain) is None


def test_license_uuid_for_resolves_manifest_entry_to_header_uuid(tmp_path):
    manifest = synthetic_manifest()
    write_data_file(tmp_path, "Pro-DE-Test-Streaming-001.data", MODEL)
    options = {"model_dir": str(tmp_path)}
    assert license_uuid_for("pro-de-test", manifest=manifest,
                            options=options) == MODEL
    assert license_uuid_for("unknown-model", manifest=manifest,
                            options=options) is None
    # File missing although manifested: fail-closed, no invented UUID.
    assert license_uuid_for("pro-de-test", manifest=manifest,
                            options={"model_dir": str(tmp_path / "empty")}) is None


# -- gate truth table (A2/A5) ------------------------------------------------

def test_no_key_means_community_without_network():
    gate, _options = gate_with_key(key="")
    connect = make_connect(valid_reply())
    decision, started = gate.refresh(
        MODEL, options={"key": ""}, connect=connect
    )
    assert decision["tier"] == "community"
    assert decision["reason"] == "no_key"
    assert started is False
    assert connect.sockets == []


def test_force_community_means_community_without_network():
    gate, options = gate_with_key()
    connect = make_connect(valid_reply())
    decision, started = gate.refresh(
        MODEL, options=options, force_community=True, connect=connect,
    )
    assert decision["tier"] == "community"
    assert decision["reason"] == "force_community"
    assert started is False
    assert connect.sockets == []


def test_valid_reply_yields_pro_and_skips_repeat_check():
    gate, options = gate_with_key()
    connect = make_connect(valid_reply())
    decision, started = gate.refresh(MODEL, options=options, connect=connect)
    assert started is True
    assert decision["tier"] == "pro"
    assert gate.state.pro_enabled_for(MODEL) is True
    assert gate.state.pro_enabled_for(OTHER_MODEL) is False
    # Fresh proof: second refresh must not hit the network again.
    decision2, started2 = gate.refresh(
        MODEL, options=options, connect=make_connect(valid_reply())
    )
    assert started2 is False
    assert decision2["tier"] == "pro"
    assert len(connect.sockets) == 1
    assert connect.sockets[0].closed is True


def test_negative_reply_timeout_and_malformed_never_grant():
    for value in (
        json.dumps({"allowed": False, "error": "",
                    "remaining_seconds": 100, "offline_timeout": 100}),
        TimeoutError("synthetic timeout"),
        "{not json",
        json.dumps({"allowed": True, "error": "revoked",
                    "remaining_seconds": 100, "offline_timeout": 100}),
        json.dumps({"allowed": True, "error": "",
                    "remaining_seconds": 0, "offline_timeout": 100}),
    ):
        gate, options = gate_with_key()
        decision, started = gate.refresh(
            MODEL, options=options, connect=make_connect(value)
        )
        assert started is True
        assert decision["tier"] == "community"
        assert gate.state.pro_enabled_for(MODEL) is False


def test_key_change_and_removal_invalidate_immediately():
    gate, options = gate_with_key()
    gate.refresh(MODEL, options=options, connect=make_connect(valid_reply()))
    assert gate.state.pro_enabled_for(MODEL) is True
    assert gate.state.bind(key="rotated-key", force_community=False) is True
    assert gate.state.pro_enabled_for(MODEL) is False
    gate.refresh(MODEL, options={"key": "rotated-key"},
                 connect=make_connect(valid_reply()))
    assert gate.state.pro_enabled_for(MODEL) is True
    gate.state.bind(key="", force_community=False)
    assert gate.state.pro_enabled_for(MODEL) is False
    assert gate.state.public_snapshot()["status"] == "NOT_CHECKED"


def test_force_activation_invalidates_and_release_rechecks():
    gate, options = gate_with_key()
    gate.refresh(MODEL, options=options, connect=make_connect(valid_reply()))
    assert gate.state.pro_enabled_for(MODEL) is True
    decision, started = gate.refresh(
        MODEL, options=options, force_community=True,
        connect=make_connect(valid_reply()),
    )
    assert decision["tier"] == "community"
    assert started is False
    assert gate.state.pro_enabled_for(MODEL) is False
    decision, started = gate.refresh(
        MODEL, options=options, force_community=False,
        connect=make_connect(valid_reply()),
    )
    assert started is True
    assert decision["tier"] == "pro"


def test_stale_generation_answer_is_discarded():
    gate, options = gate_with_key()
    release = threading.Event()
    entered = threading.Event()

    class GatedSocket(FakeSocket):
        def recv(self):
            entered.set()
            assert release.wait(10)
            return super().recv()

    def connect(url, timeout=None):
        return GatedSocket(valid_reply())

    outcome = []
    worker = threading.Thread(
        target=lambda: outcome.append(
            gate.refresh(MODEL, options=options, connect=connect)[0]
        ),
        daemon=True,
    )
    worker.start()
    assert entered.wait(10)
    # Supersede while the first check is in flight.
    gate.state.bind(key="rotated-key", force_community=False)
    release.set()
    worker.join(10)
    assert gate.state.pro_enabled_for(MODEL) is False
    assert outcome and outcome[0]["tier"] == "community"


def test_overlapping_checks_only_latest_applies():
    gate, options = gate_with_key()
    first = gate.refresh(MODEL, options=options,
                         connect=make_connect(valid_reply()))
    assert first[0]["tier"] == "pro"
    # A second model check supersedes the first proof for the old model.
    second = gate.refresh(OTHER_MODEL, options=options,
                          connect=make_connect(valid_reply()))
    assert second[0]["tier"] == "pro"
    assert gate.state.pro_enabled_for(MODEL) is False
    assert gate.state.pro_enabled_for(OTHER_MODEL) is True


def test_expired_proof_is_not_used():
    now = [1000.0]
    state = KrokoLicenseState(clock=lambda: now[0])
    state.bind(key=KEY, force_community=False)
    token = state.begin(MODEL)
    assert state.apply(token, LicenseCheckResult("VALID", MODEL, 10, "ok")) is True
    assert state.pro_enabled_for(MODEL) is True
    now[0] += 11.0
    assert state.pro_enabled_for(MODEL) is False
    assert state.public_snapshot()["status"] == "CHECK_FAILED"


def test_snapshot_is_model_scoped_not_global():
    gate, options = gate_with_key()
    gate.refresh(MODEL, options=options, connect=make_connect(valid_reply()))
    snapshot = gate.state.public_snapshot()
    assert snapshot["scope"] == "model"
    assert snapshot["modelUuid"] == MODEL
    assert snapshot["proEnabled"] is True
    assert KEY not in repr(snapshot)


# -- manager entitlement (B1/B2/B4) ------------------------------------------

def manager_with_policy(tmp_path, authority, intent_variant="pro", gate=None,
                        manifest=None):
    gate = gate or KrokoLicenseGate()
    model_dir = str(tmp_path / "models")

    def policy(product, candidate_path=None):
        uuid = None
        if candidate_path:
            uuid = read_model_uuid(candidate_path)
        if uuid is None:
            uuid = license_uuid_for(
                getattr(product, "id", "") or getattr(product, "filename", ""),
                manifest=manifest,
                options={"model_dir": model_dir},
            )
        if uuid is None:
            return False, "no_license_uuid"
        if gate.state.pro_enabled_for(uuid):
            return True, "license_valid"
        return False, "not_entitled"

    manager = STTModelManager(
        runtime_root=tmp_path / "runtime", authority=authority,
        intent=OperatorIntent(
            engines={"kroko_onnx": {"enabled": True,
                                    "auto_download_enabled": False,
                                    "custom_paths": [model_dir]}},
            models={}, defaults={}, kroko_runtime_variant=intent_variant,
        ),
        load_probe=lambda _candidate: True,
        license_policy=policy,
    )
    return manager, gate


def test_pro_model_needs_fresh_entitlement(tmp_path):
    write_data_file(tmp_path / "models", "Pro-DE-Test-Streaming-001.data",
                     MODEL)
    manager, gate = manager_with_policy(
        tmp_path, authority=None, manifest=synthetic_manifest())
    product = commercial_product()
    assert manager._eligible(product, "kroko_onnx", []) is False
    gate.refresh(MODEL, options={"key": KEY},
                 connect=make_connect(valid_reply()))
    assert manager._eligible(product, "kroko_onnx", []) is True


def test_negative_status_blocks_admission(tmp_path):
    write_data_file(tmp_path / "models", "Pro-DE-Test-Streaming-001.data",
                     MODEL)
    manager, gate = manager_with_policy(
        tmp_path, authority=None, manifest=synthetic_manifest())
    product = commercial_product()
    assert manager._eligible(product, "kroko_onnx", []) is False
    gate.refresh(MODEL, options={"key": KEY},
                 connect=make_connect(valid_reply()))
    assert manager._eligible(product, "kroko_onnx", []) is True
    gate.state.bind(key="rotated-key", force_community=False)
    assert manager._eligible(product, "kroko_onnx", []) is False


def test_community_model_eligible_on_free_and_pro_runtime(tmp_path):
    community = ProductModel(
        id="community-de", engine="kroko_onnx",
        filename="community-de.data", license_class="community-unresolved",
        runtime_variant="free",
    )
    for variant in ("free", "pro"):
        manager, _gate = manager_with_policy(
            tmp_path, authority=[community], intent_variant=variant)
        assert manager._eligible(community, "kroko_onnx", []) is True
        assert manager.candidate_eligible(
            SimpleNamespace_candidate(community), community) is True


def SimpleNamespace_candidate(product):
    from types import SimpleNamespace as NS
    return NS(engine=product.engine, path="", product_id=product.id)


def test_commercial_model_refused_on_free_runtime(tmp_path):
    write_data_file(tmp_path / "models", "pro-de-test.data", MODEL)
    manager, _gate = manager_with_policy(
        tmp_path, authority=None, intent_variant="free")
    assert manager._eligible(commercial_product(), "kroko_onnx", []) is False


def test_no_policy_keeps_legacy_behavior(tmp_path):
    product = commercial_product()
    manager = STTModelManager(
        runtime_root=tmp_path / "runtime", authority=[product],
        intent=OperatorIntent(
            engines={"kroko_onnx": {"enabled": True,
                                    "auto_download_enabled": False,
                                    "custom_paths": []}},
            models={}, defaults={}, kroko_runtime_variant="pro"),
        load_probe=lambda _candidate: True,
    )
    assert manager._eligible(product, "kroko_onnx", []) is True


# -- settings authority (A4) ---------------------------------------------------

def test_force_community_key_is_server_admin_live_and_default_false():
    registry = settings_control_module.build_default_registry()
    definition = registry.get(settings_control_module.KROKO_FORCE_COMMUNITY)
    assert definition is not None
    assert definition.scope == settings_control_module.SCOPE_SERVER
    assert definition.auth == settings_control_module.AUTH_ADMIN
    assert definition.type == settings_control_module.TYPE_BOOL
    assert definition.default_value is False
    assert definition.has_server_default is True
    assert definition.secret is False
    assert definition.apply_policy == settings_control_module.APPLY_LIVE


def test_force_community_patch_roundtrip_without_secrets():
    registry = settings_control_module.build_default_registry()
    state = settings_control_module.ServerSettingsState(registry)
    assert state.server_effective()[
        settings_control_module.KROKO_FORCE_COMMUNITY] is False
    result = state.patch_server(
        0, {settings_control_module.KROKO_FORCE_COMMUNITY: True})
    assert result.accepted is True
    assert state.server_effective()[
        settings_control_module.KROKO_FORCE_COMMUNITY] is True
    assert state.settings_revision == 1


# -- service wiring ------------------------------------------------------------

def test_service_init_binds_policy_without_network(tmp_path):
    from api_fastapi_server.server import ServerSettings, create_app
    from tests.unit.test_openai_compatible_endpoint import ImmediateScheduler

    app = create_app(
        ServerSettings(data_root_path=str(tmp_path), model_warmup=False),
        scheduler_factory=ImmediateScheduler,
    )
    service = app.state.voicestt_service
    snapshot = service.security.kroko.state.public_snapshot()
    assert snapshot["status"] == "NOT_CHECKED"
    assert service.stt_model_manager.license_policy is not None
    assert service.security.kroko._background_inflight == set()


def test_service_recheck_path_with_fake_transport(tmp_path, monkeypatch):
    from api_fastapi_server.server import ServerSettings, create_app
    from tests.unit.test_openai_compatible_endpoint import ImmediateScheduler

    settings = ServerSettings(data_root_path=str(tmp_path), model_warmup=False)
    settings.transcription_engine = "kroko_onnx"
    settings.model = "kroko-de-pro-16-l"
    settings.transcription_engine_options = {"key": KEY}
    root = tmp_path / "models"
    write_data_file(root, "Kroko-DE-Pro-16-L-Streaming-001.data", MODEL)
    monkeypatch.setenv("VOICESTT_KROKO_MODEL_ROOT", str(root))

    app = create_app(settings, scheduler_factory=ImmediateScheduler)
    service = app.state.voicestt_service
    decisions = service.refresh_kroko_license_policy(
        connect=make_connect(valid_reply()))
    assert decisions and decisions[0]["tier"] == "pro"
    assert decisions[0]["model_uuid"] == MODEL
    entitled, _reason = service._kroko_license_entitlement(
        commercial_product(
            model_id="kroko-de-pro-16-l", runtime_variant="pro"),
        str(root / "Kroko-DE-Pro-16-L-Streaming-001.data"))
    assert entitled is True


def test_lifespan_stop_error_cannot_mask_startup_error(tmp_path):
    from api_fastapi_server.server import ServerSettings, create_app
    from tests.unit.test_openai_compatible_endpoint import ImmediateScheduler

    app = create_app(ServerSettings(data_root_path=str(tmp_path),
                                    model_warmup=False),
                     scheduler_factory=ImmediateScheduler)
    service = app.state.voicestt_service
    with (mock.patch.object(service, "start",
                            side_effect=RuntimeError("synthetic startup failure")),
          mock.patch.object(service, "stop",
                            side_effect=RuntimeError("synthetic stop failure"))):
        async def run():
            async with app.router.lifespan_context(app):
                pass
        with pytest.raises(RuntimeError, match="synthetic startup failure"):
            asyncio.run(run())


def test_log_token_prune_threshold_and_host_source():
    from api_fastapi_server.security.admin import (
        LOCAL_ADMIN_HOSTS as ADMIN_HOSTS)
    from api_fastapi_server.security.logs import (
        LOCAL_ADMIN_HOSTS as LOG_HOSTS)
    assert ADMIN_HOSTS is LOG_HOSTS
    from api_fastapi_server.security.logs import LogTokenAuthority
    clock = [1000.0]
    authority = LogTokenAuthority(clock=lambda: clock[0])
    tokens = [authority.issue(f"session-{index}")[0] for index in range(5)]
    clock[0] += 24 * 60 * 60 + 1
    assert authority.validate(tokens[0], "session-0") is None


def test_openai_auth_error_carries_request_id(tmp_path):
    from fastapi.testclient import TestClient
    from api_fastapi_server.server import ServerSettings, create_app
    from tests.unit.test_openai_compatible_endpoint import (
        ImmediateScheduler, wav_bytes)

    app = create_app(
        ServerSettings(data_root_path=str(tmp_path), model_warmup=False,
                       openai_api_key="secret"),
        scheduler_factory=ImmediateScheduler,
    )
    with TestClient(app) as client:
        response = client.post(
            "/v1/audio/transcriptions",
            headers={"Authorization": "Bearer wrong"},
            data={"model": "whisper-1"},
            files={"file": ("sample.wav", wav_bytes(), "audio/wav")},
        )
        assert response.status_code == 401
        assert response.headers.get("x-request-id", "") != ""
