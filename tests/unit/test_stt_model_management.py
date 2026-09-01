import hashlib
import inspect
import json
import os
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from VoiceSTT_server.stt_model_management import (
    AtomicModelProvisioner,
    LOAD_VERIFIED,
    ManagedModelRegistryView,
    MINIMUM_READY,
    NOT_READY,
    OperatorIntent,
    ProductModel,
    STTModelManager,
)


def product(
    model_id,
    payload=b"model",
    *,
    priority=None,
    provisionable=False,
    roles=("final", "realtime"),
    runtime_variant=None,
):
    return ProductModel(
        id=model_id,
        engine="kroko_onnx",
        filename=f"{model_id}.data",
        bytes=len(payload),
        sha256=hashlib.sha256(payload).hexdigest(),
        source=f"fixture://{model_id}",
        source_identity=f"fixture://{model_id}",
        provisioning_allowed=provisionable,
        rights_status="ALLOWED" if provisionable else "LOCAL_ONLY",
        recovery_priority=priority,
        roles=roles,
        runtime_variant=runtime_variant,
    )


def write_model(root: Path, entry: ProductModel, payload=b"model") -> Path:
    root.mkdir(parents=True, exist_ok=True)
    path = root / entry.filename
    path.write_bytes(payload)
    return path


def intent(
    *,
    custom=(),
    defaults=None,
    global_auto=False,
    engine_auto=False,
    model_settings=None,
    runtime_variant=None,
    pro_license=False,
):
    return OperatorIntent(
        global_auto_download=global_auto,
        engines={
            "kroko_onnx": {
                "enabled": True,
                "auto_download_enabled": engine_auto,
                "custom_paths": [str(path) for path in custom],
            }
        },
        models=model_settings or {},
        defaults=defaults or {},
        kroko_runtime_variant=runtime_variant,
        kroko_pro_license_present=pro_license,
    )


def copying_fetcher(payload, calls=None, observed_source=None, entered=None, release=None):
    def fetch(source, destination):
        if calls is not None:
            calls.append(source)
        if entered is not None:
            entered.set()
        if release is not None:
            assert release.wait(5)
        destination.write_bytes(payload)
        return observed_source or source

    return fetch


def test_default_store_and_custom_precedence(tmp_path):
    entry = product("primary")
    custom = tmp_path / "read-only-source"
    runtime = tmp_path / "runtime"
    custom_path = write_model(custom, entry)
    write_model(runtime / "models" / "stt" / "kroko_asr", entry)
    manager = STTModelManager(
        runtime_root=runtime,
        authority=[entry],
        intent=intent(
            custom=[custom],
            defaults={"final": ("kroko_onnx", entry.id), "realtime": ("kroko_onnx", entry.id)},
        ),
        load_probe=lambda candidate: True,
    )

    assert manager.default_root("kroko_onnx") == runtime / "models" / "stt" / "kroko_asr"
    snapshot = manager.refresh()
    assert snapshot.readiness == MINIMUM_READY
    assert snapshot.active["final"].path == str(custom_path.resolve())


def test_faster_whisper_uses_default_runtime_store_and_validates_structure(tmp_path):
    runtime = tmp_path / "runtime"
    root = runtime / "models" / "stt" / "fasterwhisper"
    model = root / "models--Systran--faster-whisper-small"
    model.mkdir(parents=True)
    (model / "config.json").write_text("{}", encoding="utf-8")
    (model / "model.bin").write_bytes(b"model")
    entry = ProductModel(
        id="faster-whisper-small",
        engine="faster_whisper",
        artifact_kind="directory",
        recovery_priority=1,
    )
    manager = STTModelManager(
        runtime_root=runtime,
        authority=[entry],
        intent=OperatorIntent(),
        load_probe=lambda candidate: True,
    )
    snapshot = manager.refresh()
    assert snapshot.minimum_ready
    assert snapshot.active["final"].path == str(model.resolve())


def test_partial_and_staging_content_is_not_discovered(tmp_path):
    entry = product("primary")
    root = tmp_path / "models"
    root.mkdir()
    (root / f"{entry.filename}.part").write_bytes(b"model")
    (root / f".{entry.filename}.token.part").write_bytes(b"model")
    manager = STTModelManager(
        runtime_root=tmp_path / "runtime",
        authority=[entry],
        intent=intent(custom=[root]),
    )
    snapshot = manager.refresh()
    assert snapshot.candidates == ()


def test_direct_custom_kroko_file_is_a_discovery_source(tmp_path):
    entry = product("direct", priority=1)
    path = write_model(tmp_path / "custom", entry)
    manager = STTModelManager(
        runtime_root=tmp_path / "runtime",
        authority=[entry],
        intent=intent(custom=[path]),
        load_probe=lambda candidate: True,
    )
    snapshot = manager.refresh()
    assert snapshot.minimum_ready
    assert snapshot.active["final"].path == str(path.resolve())


def test_unmanaged_kroko_file_is_visible_but_not_declared_available(tmp_path):
    root = tmp_path / "custom"
    root.mkdir()
    path = root / "unknown-pro-or-community.data"
    path.write_bytes(b"unknown")
    manager = STTModelManager(
        runtime_root=tmp_path / "runtime",
        authority=[],
        intent=intent(
            custom=[root],
            defaults={
                "final": ("kroko_onnx", path.name),
                "realtime": ("kroko_onnx", path.name),
            },
        ),
        load_probe=lambda candidate: True,
    )
    snapshot = manager.refresh()
    assert snapshot.readiness == NOT_READY
    assert any(item.id == path.name for item in snapshot.candidates)
    listed = ManagedModelRegistryView(manager).list_models()
    assert listed[0]["available"] is False


def test_read_only_custom_source_is_discovered_but_writable_runtime_is_target(tmp_path):
    local = product("local")
    wanted = product("wanted", provisionable=True)
    custom = tmp_path / "custom"
    write_model(custom, local)
    runtime = tmp_path / "runtime"
    calls = []
    provisioner = AtomicModelProvisioner(
        fetcher=copying_fetcher(b"model", calls),
        writable_probe=lambda root: root != custom,
    )
    manager = STTModelManager(
        runtime_root=runtime,
        authority=[local, wanted],
        intent=intent(
            custom=[custom],
            defaults={"final": ("kroko_onnx", wanted.id), "realtime": ("kroko_onnx", wanted.id)},
            global_auto=True,
        ),
        provisioner=provisioner,
    )
    snapshot = manager.refresh()
    assert any(item.id == local.id for item in snapshot.candidates)
    assert (runtime / "models" / "stt" / "kroko_asr" / wanted.filename).is_file()
    assert not (custom / wanted.filename).exists()
    assert calls == [wanted.source]


@pytest.mark.parametrize(
    "global_flag,engine_flag,model_flag,expected",
    [
        (False, False, False, False),
        (True, False, False, True),
        (False, True, False, True),
        (False, False, True, True),
        (True, False, False, True),
    ],
)
def test_auto_download_is_exact_global_or_engine_or_model(
    global_flag, engine_flag, model_flag, expected
):
    entry = product("requested", provisionable=True)
    cfg = intent(
        global_auto=global_flag,
        engine_auto=engine_flag,
        model_settings={entry.id: {"auto_download_enabled": model_flag}},
    )
    assert cfg.effective_auto_download(entry) is expected


def test_hard_ineligibility_wins_over_global_request(tmp_path):
    blocked = product("blocked", provisionable=False, priority=1)
    calls = []
    manager = STTModelManager(
        runtime_root=tmp_path,
        authority=[blocked],
        intent=intent(global_auto=True),
        provisioner=AtomicModelProvisioner(fetcher=copying_fetcher(b"model", calls)),
    )
    snapshot = manager.refresh()
    assert snapshot.readiness == NOT_READY
    assert calls == []
    assert any(item["result"] == "blocked_ineligible" for item in snapshot.diagnostics)


def test_defaults_precede_ordered_priority_and_stable_id_ties(tmp_path):
    default = product("default", priority=None)
    bravo = product("bravo", priority=10)
    alpha = product("alpha", priority=10)
    root = tmp_path / "models"
    for entry in (default, bravo, alpha):
        write_model(root, entry)
    probes = []

    def probe(candidate):
        probes.append(candidate.id)
        return candidate.id != default.id

    manager = STTModelManager(
        runtime_root=tmp_path / "runtime",
        authority=[default, bravo, alpha],
        intent=intent(
            custom=[root],
            defaults={"final": ("kroko_onnx", default.id), "realtime": ("kroko_onnx", default.id)},
        ),
        load_probe=probe,
    )
    snapshot = manager.refresh()
    assert probes == ["default", "alpha"]
    assert snapshot.minimum_ready
    assert snapshot.active["final"].id == "alpha"
    assert snapshot.active["realtime"].id == "alpha"


def test_no_priority_model_is_not_a_generic_fallback(tmp_path):
    entry = product("manual-only", priority=None)
    root = tmp_path / "models"
    write_model(root, entry)
    probes = []
    manager = STTModelManager(
        runtime_root=tmp_path / "runtime",
        authority=[entry],
        intent=intent(custom=[root]),
        load_probe=lambda candidate: probes.append(candidate.id) or True,
    )
    assert manager.refresh().readiness == NOT_READY
    assert probes == []


def test_local_fallback_needs_no_auto_download_but_missing_one_does(tmp_path):
    entry = product("fallback", priority=1, provisionable=True)
    local_root = tmp_path / "local"
    write_model(local_root, entry)
    local_manager = STTModelManager(
        runtime_root=tmp_path / "runtime-local",
        authority=[entry],
        intent=intent(custom=[local_root], global_auto=False),
    )
    assert local_manager.refresh().minimum_ready

    calls = []
    missing_manager = STTModelManager(
        runtime_root=tmp_path / "runtime-missing",
        authority=[entry],
        intent=intent(global_auto=False),
        provisioner=AtomicModelProvisioner(fetcher=copying_fetcher(b"model", calls)),
    )
    assert missing_manager.refresh().readiness == NOT_READY
    assert calls == []


def test_discovery_does_not_probe_catalog_and_recovery_stops_at_minimum(tmp_path):
    chosen = product("chosen", priority=1)
    later = product("later", priority=2)
    root = tmp_path / "models"
    write_model(root, chosen)
    write_model(root, later)
    probes = []
    manager = STTModelManager(
        runtime_root=tmp_path / "runtime",
        authority=[chosen, later],
        intent=intent(custom=[root]),
        load_probe=lambda candidate: probes.append(candidate.id) or True,
    )
    snapshot = manager.refresh()
    assert snapshot.minimum_ready
    assert probes == [chosen.id]
    assert any(item.id == later.id and item.state != LOAD_VERIFIED for item in snapshot.candidates)


def test_optional_request_continues_after_ready_and_failure_keeps_ready(tmp_path):
    ready = product("ready", priority=1)
    optional = product("optional", provisionable=True)
    root = tmp_path / "models"
    write_model(root, ready)
    provisioner = AtomicModelProvisioner(
        fetcher=copying_fetcher(b"wrong"),
        writable_probe=lambda path: True,
    )
    manager = STTModelManager(
        runtime_root=tmp_path / "runtime",
        authority=[ready, optional],
        intent=intent(
            custom=[root],
            model_settings={optional.id: {"auto_download_enabled": True}},
        ),
        provisioner=provisioner,
    )
    snapshot = manager.refresh()
    assert snapshot.minimum_ready
    assert snapshot.optional_state == "errors"
    assert set(snapshot.active) == {"final", "realtime"}


def test_optional_provisioning_in_progress_is_observable(tmp_path):
    ready = product("ready", priority=1)
    optional = product("optional", provisionable=True)
    root = tmp_path / "models"
    write_model(root, ready)
    entered = threading.Event()
    release = threading.Event()
    manager = STTModelManager(
        runtime_root=tmp_path / "runtime",
        authority=[ready, optional],
        intent=intent(
            custom=[root],
            model_settings={optional.id: {"auto_download_enabled": True}},
        ),
        provisioner=AtomicModelProvisioner(
            fetcher=copying_fetcher(b"model", entered=entered, release=release)
        ),
    )
    worker = threading.Thread(target=manager.refresh)
    worker.start()
    assert entered.wait(5)
    status = manager.status()
    assert status["minimumReady"] is True
    assert status["state"] == "ready_optional_provisioning"
    release.set()
    worker.join(5)
    assert not worker.is_alive()


def test_failed_refresh_preserves_last_known_good(tmp_path):
    entry = product("ready", priority=1)
    root = tmp_path / "models"
    path = write_model(root, entry)
    manager = STTModelManager(
        runtime_root=tmp_path / "runtime",
        authority=[entry],
        intent=intent(custom=[root]),
    )
    first = manager.refresh()
    assert first.minimum_ready
    path.unlink()
    second = manager.refresh()
    assert second is first
    assert manager.status()["lastRefreshDiagnostics"]


def test_concurrent_refresh_never_publishes_partial_candidates(tmp_path):
    entry = product("ready", priority=1)
    root = tmp_path / "models"
    write_model(root, entry)
    entered = threading.Event()
    release = threading.Event()

    def probe(candidate):
        entered.set()
        assert release.wait(5)
        return True

    manager = STTModelManager(
        runtime_root=tmp_path / "runtime",
        authority=[entry],
        intent=intent(custom=[root]),
        load_probe=probe,
    )
    worker = threading.Thread(target=manager.refresh)
    worker.start()
    assert entered.wait(5)
    during = manager.status()
    assert during["revision"] == 0
    assert during["candidates"] == []
    assert during["refreshInProgress"] is True
    release.set()
    worker.join(5)
    assert manager.status()["minimumReady"] is True


def test_pro_model_is_visible_but_not_activatable_without_prerequisites(tmp_path):
    pro = product("pro", priority=1, runtime_variant="pro")
    root = tmp_path / "models"
    write_model(root, pro)
    manager = STTModelManager(
        runtime_root=tmp_path / "runtime",
        authority=[pro],
        intent=intent(custom=[root], runtime_variant="pro", pro_license=False),
    )
    snapshot = manager.refresh()
    assert any(item.id == pro.id for item in snapshot.candidates)
    assert snapshot.readiness == NOT_READY
    assert any(
        item["result"] == "pro_license_prerequisite_missing"
        for item in snapshot.diagnostics
    )
    listed = ManagedModelRegistryView(manager).list_models()
    assert listed[0]["eligible"] is False
    assert listed[0]["available"] is False


def test_invalid_content_and_source_never_activate_or_leave_part_file(tmp_path):
    entry = product("wanted", provisionable=True)
    root = tmp_path / "target"
    provisioner = AtomicModelProvisioner(
        fetcher=copying_fetcher(b"wrong", observed_source="fixture://redirected")
    )
    with pytest.raises(ValueError, match="source identity mismatch"):
        provisioner.provision(entry, [root])
    assert not (root / entry.filename).exists()
    assert list(root.glob("*.part")) == []
    assert list(root.glob(".*.part")) == []


def test_failed_replacement_preserves_existing_content(tmp_path):
    new = product("same", payload=b"new-good", provisionable=True)
    root = tmp_path / "target"
    root.mkdir()
    target = root / new.filename
    target.write_bytes(b"old-known-good")
    provisioner = AtomicModelProvisioner(fetcher=copying_fetcher(b"bad"))
    with pytest.raises(ValueError, match="identity verification"):
        provisioner.provision(new, [root])
    assert target.read_bytes() == b"old-known-good"
    assert not list(root.glob(".*.part"))


def test_concurrent_provisioning_same_target_converges_without_duplicate_cache(tmp_path):
    entry = product("shared", provisionable=True)
    root = tmp_path / "target"
    calls = []
    provisioner = AtomicModelProvisioner(fetcher=copying_fetcher(b"model", calls))
    results = []
    errors = []

    def run():
        try:
            results.append(provisioner.provision(entry, [root]))
        except Exception as exc:  # pragma: no cover - asserted below
            errors.append(exc)

    threads = [threading.Thread(target=run) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(5)
    assert errors == []
    assert len(results) == 2 and results[0] == results[1]
    assert calls == [entry.source]
    assert (root / entry.filename).read_bytes() == b"model"
    assert sorted(path.name for path in root.iterdir()) == [entry.filename]


def test_provisionable_product_rejects_incomplete_immutable_authority():
    with pytest.raises(ValueError, match="immutable authority"):
        ProductModel(
            id="dishonest",
            engine="kroko_onnx",
            filename="dishonest.data",
            provisioning_allowed=True,
        )
    with pytest.raises(ValueError, match="must not contain a path"):
        ProductModel(
            id="traversal",
            engine="kroko_onnx",
            filename="../outside.data",
        )


def test_operator_config_cannot_rewrite_product_facts_or_expose_pro_secret(tmp_path, monkeypatch):
    entry = product("authority", priority=1)
    settings = SimpleNamespace(
        stt_auto_download_enabled=False,
        stt_engine_settings={"kroko_onnx": {"custom_paths": []}},
        stt_model_settings={entry.id: {
            "sha256": "operator-forgery",
            "source": "https://attacker.invalid/model",
        }},
        transcription_engine="kroko_onnx",
        realtime_transcription_engine="kroko_onnx",
        model=entry.id,
        realtime_model=entry.id,
        download_root=str(tmp_path / "legacy-download-root"),
        transcription_engine_options={"runtime_variant": "pro"},
        realtime_transcription_engine_options=None,
    )
    monkeypatch.setenv("KROKO_API_KEY", "sentinel-license-value")
    manager = STTModelManager(
        runtime_root=tmp_path,
        authority=[entry],
        intent=OperatorIntent.from_settings(settings),
    )
    assert str(tmp_path / "legacy-download-root") in manager.intent.engine_config(
        "kroko_onnx"
    )["custom_paths"]
    encoded = json.dumps(manager.status(), sort_keys=True)
    assert entry.sha256 in encoded
    assert "operator-forgery" not in encoded
    assert "attacker.invalid" not in encoded
    assert os.environ["KROKO_API_KEY"] not in encoded


def test_load_probe_exception_redacts_pro_secret(tmp_path, monkeypatch):
    secret = "never-echo-this-license"
    monkeypatch.setenv("KROKO_API_KEY", secret)
    entry = product("redaction", priority=1)
    root = tmp_path / "models"
    write_model(root, entry)
    manager = STTModelManager(
        runtime_root=tmp_path / "runtime",
        authority=[entry],
        intent=intent(custom=[root]),
        load_probe=lambda candidate: (_ for _ in ()).throw(
            RuntimeError(f"native failure mentioned {secret}")
        ),
    )
    manager.refresh()
    encoded = json.dumps(manager.status(), sort_keys=True)
    assert secret not in encoded
    assert "[REDACTED]" in encoded


def test_server_admin_and_health_remain_available_when_stt_is_not_ready(tmp_path):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from api_fastapi_server.server import ServerSettings, create_app

    class HealthyFakeScheduler:
        def __init__(self, *_args):
            pass

        def start(self):
            pass

        def stop(self):
            pass

        def wait_ready(self, timeout=None):
            return True

        def healthy(self):
            return True

        def snapshot(self):
            return {"mode": "fake", "queues": {}, "workers": {}}

    app = create_app(
        ServerSettings(
            data_root_path=str(tmp_path / "runtime"),
            event_store_enabled=False,
            log_live_enabled=False,
            request_logging_enabled=False,
            performance_logging_enabled=False,
            transcription_logging_enabled=False,
            system_event_logging_enabled=False,
        ),
        scheduler_factory=HealthyFakeScheduler,
    )
    with TestClient(app) as client:
        health = client.get("/health")
        management = client.get("/api/models/management")
        config = client.get("/api/config")
    assert health.status_code == 200
    assert health.json()["sttReady"] is False
    assert health.json()["ok"] is True  # process liveness is separate
    assert management.status_code == 200
    assert management.json()["state"] == "not_ready"
    assert config.status_code == 200


def test_existing_yaml_settings_authority_parses_model_management_fields():
    from api_fastapi_server.server import parse_args, settings_from_args

    config_path = Path(__file__).resolve().parents[2] / "config.yaml"
    settings = settings_from_args(parse_args(["--config", str(config_path)]))
    assert settings.stt_auto_download_enabled is False
    assert settings.stt_engine_settings["faster_whisper"]["enabled"] is True
    assert settings.stt_engine_settings["kroko_onnx"]["auto_download_enabled"] is False
    assert settings.stt_model_settings == {}


def test_engines_have_no_network_or_native_build_provisioning_path():
    from VoiceSTT.transcription_engines import faster_whisper_engine
    from VoiceSTT.transcription_engines import kroko_onnx_engine
    from VoiceSTT.transcription_engines import model_resolver
    from VoiceSTT_server import stt_model_management

    engine_source = "\n".join((
        inspect.getsource(faster_whisper_engine),
        inspect.getsource(kroko_onnx_engine),
        inspect.getsource(model_resolver),
    ))
    assert "urlopen" not in engine_source
    assert "hf_hub_download" not in engine_source
    manager_source = inspect.getsource(stt_model_management)
    assert "install_kroko" not in manager_source
    assert "build_kroko" not in manager_source
