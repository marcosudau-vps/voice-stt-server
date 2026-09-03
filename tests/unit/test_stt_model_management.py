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
    ModelCandidate,
    ModelSnapshot,
    NOT_READY,
    OperatorIntent,
    ProductModel,
    STTModelManager,
)
from VoiceSTT_server.credential_redaction import (
    kroko_credential_values,
    redact_kroko_credentials,
    redact_secret_text,
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


def test_pro_model_eligibility_is_not_inferred_from_api_key_presence(tmp_path):
    pro = product("pro", priority=1, runtime_variant="pro")
    root = tmp_path / "models"
    write_model(root, pro)
    manager = STTModelManager(
        runtime_root=tmp_path / "runtime",
        authority=[pro],
        intent=intent(custom=[root], runtime_variant="pro"),
        load_probe=lambda candidate: True,
    )
    snapshot = manager.refresh()
    assert any(item.id == pro.id for item in snapshot.candidates)
    assert snapshot.readiness == MINIMUM_READY
    listed = ManagedModelRegistryView(manager).list_models()
    assert listed[0]["eligible"] is True
    assert listed[0]["available"] is True


def test_default_free_runtime_reaches_free_model_without_a_key(tmp_path, monkeypatch):
    for name in ("KROKO_API_KEY", "KROKO_ONNX_KEY", "KROKO_KEY"):
        monkeypatch.delenv(name, raising=False)
    free = product("community-free", priority=1, runtime_variant="free")
    root = tmp_path / "models"
    write_model(root, free)
    manager = STTModelManager(
        runtime_root=tmp_path / "runtime",
        authority=[free],
        intent=intent(custom=[root], runtime_variant="free"),
        load_probe=lambda _candidate: True,
    )
    assert manager.refresh().readiness == MINIMUM_READY


def test_key_cannot_make_a_pro_model_eligible_for_free_runtime(tmp_path, monkeypatch):
    monkeypatch.setenv("KROKO_API_KEY", "cannot-promote-runtime")
    pro = product("pro", priority=1, runtime_variant="pro")
    root = tmp_path / "models"
    write_model(root, pro)
    probe_calls = []
    manager = STTModelManager(
        runtime_root=tmp_path / "runtime",
        authority=[pro],
        intent=intent(custom=[root], runtime_variant="free"),
        load_probe=lambda candidate: probe_calls.append(candidate) or True,
    )
    snapshot = manager.refresh()
    assert snapshot.readiness == NOT_READY
    assert probe_calls == []
    assert any(
        item["result"] == "runtime_variant_incompatible"
        for item in snapshot.diagnostics
    )


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


def _variant_settings(**overrides):
    values = {
        "stt_auto_download_enabled": False,
        "stt_engine_settings": {},
        "stt_model_settings": {},
        "transcription_engine": "kroko_onnx",
        "realtime_transcription_engine": "kroko_onnx",
        "model": "community-free",
        "realtime_model": "community-free",
        "download_root": None,
        "transcription_engine_options": None,
        "realtime_transcription_engine_options": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_kroko_runtime_variant_defaults_to_community_free_and_ignores_key(monkeypatch):
    monkeypatch.setenv("KROKO_API_KEY", "credential-does-not-select-pro")
    monkeypatch.delenv("VOICESTT_KROKO_VARIANT", raising=False)
    parsed = OperatorIntent.from_settings(_variant_settings())
    assert parsed.kroko_runtime_variant == "free"


@pytest.mark.parametrize(
    ("settings", "environment", "expected"),
    [
        (
            _variant_settings(
                stt_engine_settings={"kroko_onnx": {"runtime_variant": "free"}},
            ),
            "pro",
            "free",
        ),
        (
            _variant_settings(
                stt_engine_settings={"kroko_onnx": {"runtime_variant": "pro"}},
                transcription_engine_options={"runtime_variant": "free"},
                realtime_transcription_engine_options={"runtime_variant": "free"},
            ),
            "free",
            "pro",
        ),
        (
            _variant_settings(
                transcription_engine_options={"runtime_variant": "pro"},
                realtime_transcription_engine_options={"runtime_variant": "free"},
            ),
            "free",
            "pro",
        ),
        (
            _variant_settings(
                transcription_engine="faster_whisper",
                realtime_transcription_engine="kroko_onnx",
                realtime_transcription_engine_options={"runtime_variant": "pro"},
            ),
            "free",
            "pro",
        ),
        (_variant_settings(), "pro", "pro"),
    ],
)
def test_kroko_runtime_variant_has_one_deterministic_precedence(
    settings, environment, expected, monkeypatch
):
    monkeypatch.setenv("VOICESTT_KROKO_VARIANT", environment)
    assert OperatorIntent.from_settings(settings).kroko_runtime_variant == expected


def test_kroko_credential_redaction_is_recursive_and_context_aware(monkeypatch):
    monkeypatch.setenv("KROKO_API_KEY", "environment-secret")
    value = {
        "ordinary": {"key": "business-key"},
        "stt_engine_settings": {
            "kroko_onnx": {
                "key": "nested-secret",
                "api_key": "alias-secret",
                "beam_size": 5,
            }
        },
    }
    redacted = redact_kroko_credentials(value)
    dropped = redact_kroko_credentials(value, drop=True)
    assert redacted["ordinary"]["key"] == "business-key"
    assert redacted["stt_engine_settings"]["kroko_onnx"]["key"] == "[REDACTED]"
    assert "key" not in dropped["stt_engine_settings"]["kroko_onnx"]
    assert dropped["stt_engine_settings"]["kroko_onnx"]["beam_size"] == 5
    secrets = kroko_credential_values(value)
    assert set(secrets) == {"nested-secret", "alias-secret"}
    message = redact_secret_text(
        "failed key=nested-secret and environment-secret", secrets
    )
    assert "nested-secret" not in message
    assert "environment-secret" not in message


@pytest.mark.parametrize(
    "option_field",
    ["transcription_engine_options", "realtime_transcription_engine_options"],
)
def test_engine_option_only_secret_is_redacted_from_model_diagnostics(
    tmp_path, monkeypatch, option_field
):
    monkeypatch.delenv("KROKO_API_KEY", raising=False)
    secret = "option-only-secret-{0}".format(option_field)
    settings = _variant_settings(
        stt_engine_settings={
            "kroko_onnx": {"custom_paths": [str(tmp_path / "models")]}
        },
        **{option_field: {"key": secret, "provider": "cpu"}},
    )
    parsed = OperatorIntent.from_settings(settings)
    assert secret in parsed.redaction_values
    assert secret not in repr(parsed)
    entry = product("community-free", priority=1)
    write_model(tmp_path / "models", entry)
    manager = STTModelManager(
        runtime_root=tmp_path / "runtime",
        authority=[entry],
        intent=parsed,
        load_probe=lambda _candidate: (_ for _ in ()).throw(
            RuntimeError("native engine echoed {0}".format(secret))
        ),
    )
    manager.refresh()
    assert secret not in json.dumps(manager.status(), sort_keys=True)


def _ready_snapshot(revision=1):
    candidate = ModelCandidate(
        id="community-free",
        engine="kroko_onnx",
        path="C:/models/community-free.data",
        source_root="C:/models",
        state=LOAD_VERIFIED,
    )
    return ModelSnapshot(
        revision=revision,
        readiness=MINIMUM_READY,
        candidates=(candidate,),
        active={"final": candidate, "realtime": candidate},
    )


def _refresh_service(manager):
    from api_fastapi_server.server import ServerSettings, VoiceSTTService

    service = object.__new__(VoiceSTTService)
    service.settings = ServerSettings(
        transcription_engine="kroko_onnx",
        realtime_transcription_engine="kroko_onnx",
        model="community-free",
        realtime_model="community-free",
        stt_engine_settings={
            "kroko_onnx": {"runtime_variant": "pro", "key": "refresh-secret"}
        },
    )
    service.settings._resolved_stt_models = {
        "final": {
            "id": "community-free",
            "engine": "kroko_onnx",
            "path": "C:/models/community-free.data",
        },
        "realtime": {
            "id": "community-free",
            "engine": "kroko_onnx",
            "path": "C:/models/community-free.data",
        },
    }
    service.stt_model_manager = manager
    service._stt_refresh_lock = threading.Lock()
    service._stt_model_refresh_required = True
    return service


def test_explicit_refresh_adopts_pending_intent_only_after_ready_snapshot():
    previous = _ready_snapshot(1)
    replacement = _ready_snapshot(2)

    class Manager:
        def __init__(self):
            self.intent = object()

        def snapshot(self):
            return previous

        def refresh(self):
            return replacement

        def status(self):
            return replacement.public_dict()

    manager = Manager()
    old_intent = manager.intent
    service = _refresh_service(manager)
    result = service.refresh_stt_models()
    assert manager.intent is not old_intent
    assert manager.intent.kroko_runtime_variant == "pro"
    assert result["modelRefreshRequired"] is False
    assert result["management"]["refreshRequired"] is False


def test_failed_explicit_refresh_preserves_lkg_and_pending_intent_boundary():
    previous = _ready_snapshot(4)
    restored = []

    class Manager:
        def __init__(self):
            self.intent = object()

        def snapshot(self):
            return previous

        def refresh(self):
            raise RuntimeError("native key=refresh-secret load failure")

        def restore_last_known_good(self, snapshot, message):
            restored.append((snapshot, message))

    manager = Manager()
    old_intent = manager.intent
    service = _refresh_service(manager)
    with pytest.raises(RuntimeError) as caught:
        service.refresh_stt_models()
    assert manager.intent is old_intent
    assert restored[0][0] is previous
    assert "refresh-secret" not in restored[0][1]
    assert "refresh-secret" not in str(caught.value)
    assert service._stt_model_refresh_required is True


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


def test_server_admin_and_health_remain_available_when_stt_is_not_ready(
    tmp_path, monkeypatch
):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from api_fastapi_server.server import ServerSettings, create_app
    from VoiceSTT.core import wakeword_catalog

    monkeypatch.setattr(wakeword_catalog, "default_artifact_probers", lambda: {})

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

    initial_secret = "initial-kroko-secret"
    updated_secret = "updated-kroko-secret"
    app = create_app(
        ServerSettings(
            data_root_path=str(tmp_path / "runtime"),
            stt_engine_settings={
                "kroko_onnx": {
                    "runtime_variant": "free",
                    "key": initial_secret,
                    "beam_size": 4,
                }
            },
            event_store_enabled=False,
            log_live_enabled=False,
            request_logging_enabled=False,
            performance_logging_enabled=False,
            transcription_logging_enabled=False,
            system_event_logging_enabled=False,
        ),
        scheduler_factory=HealthyFakeScheduler,
    )
    service = app.state.voicestt_service
    original_intent = service.stt_model_manager.intent
    monkeypatch.setattr(
        service.stt_model_manager,
        "refresh",
        lambda: pytest.fail("PATCH /api/config must not refresh or provision models"),
    )
    with TestClient(app) as client:
        health = client.get("/health")
        management = client.get("/api/models/management")
        config = client.get("/api/config")
        update = client.patch(
            "/api/config",
            json={
                "settings": {
                    "stt_engine_settings": {
                        "kroko_onnx": {
                            "runtime_variant": "pro",
                            "api_key": updated_secret,
                            "beam_size": 7,
                        }
                    }
                }
            },
        )
        pending_management = client.get("/api/models/management")
        pending_health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["sttReady"] is False
    assert health.json()["ok"] is True  # process liveness is separate
    assert management.status_code == 200
    assert management.json()["state"] == "not_ready"
    assert config.status_code == 200
    assert update.status_code == 200
    assert update.json()["modelRefreshRequired"] is True
    assert update.json()["applied"]["stt_engine_settings"]["appliesTo"] == "model_refresh"
    assert pending_management.json()["refreshRequired"] is True
    assert pending_health.json()["sttModels"]["refreshRequired"] is True
    assert service.stt_model_manager.intent is original_intent
    public_payload = json.dumps(
        {
            "health": pending_health.json(),
            "management": pending_management.json(),
            "config": config.json(),
            "update": update.json(),
        },
        sort_keys=True,
    )
    assert initial_secret not in public_payload
    assert updated_secret not in public_payload
    persisted = json.loads(Path(service.settings.runtime_config_path).read_text("utf-8"))
    persisted_payload = json.dumps(persisted, sort_keys=True)
    assert initial_secret not in persisted_payload
    assert updated_secret not in persisted_payload
    persisted_settings = persisted["settings"]
    assert persisted_settings["stt_engine_settings"]["kroko_onnx"]["runtime_variant"] == "pro"
    assert persisted_settings["stt_engine_settings"]["kroko_onnx"]["beam_size"] == 7


def test_existing_yaml_settings_authority_parses_model_management_fields():
    from api_fastapi_server.server import parse_args, settings_from_args

    config_path = Path(__file__).resolve().parents[2] / "config.yaml"
    settings = settings_from_args(parse_args(["--config", str(config_path)]))
    assert settings.stt_auto_download_enabled is False
    assert settings.stt_engine_settings["faster_whisper"]["enabled"] is True
    assert settings.stt_engine_settings["kroko_onnx"]["auto_download_enabled"] is False
    assert settings.stt_engine_settings["kroko_onnx"]["runtime_variant"] == "free"
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
