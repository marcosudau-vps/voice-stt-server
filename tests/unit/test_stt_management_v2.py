from dataclasses import replace
import hashlib
import json
from pathlib import Path
import threading

from fastapi.testclient import TestClient
import pytest

from api_fastapi_server.server import ServerSettings, create_app
from VoiceSTT.core import wakeword_catalog
from VoiceSTT_server.stt_model_management import (
    AtomicModelProvisioner, ModelCandidate, OperatorIntent, ProductModel, STTModelManager,
)
from tests.unit.test_fastapi_server_multi_user import ManualScheduler, FakeRecorder
from tests.unit.test_stt_download_jobs import wait_job
from voice_stt_server.models.inventory import installation_id, project_inventory
from voice_stt_server.models.storage import ArtifactFile


AUTH = {"X-Admin-Key": "sttm-admin-fixture"}


@pytest.fixture
def app_client(tmp_path, monkeypatch):
    monkeypatch.setattr(wakeword_catalog, "default_artifact_probers", lambda: {})
    app = create_app(ServerSettings(
        data_root_path=str(tmp_path), admin_api_key=AUTH["X-Admin-Key"],
        event_store_enabled=False, log_live_enabled=False,
        request_logging_enabled=False, performance_logging_enabled=False,
        transcription_logging_enabled=False, system_event_logging_enabled=False),
        scheduler_factory=ManualScheduler, recorder_factory=FakeRecorder)
    client = TestClient(app)
    service = app.state.voicestt_service
    yield client, service
    service.stop()


def synthetic(engine="faster_whisper", model_id="fixture"):
    digest = hashlib.sha256(b"model").hexdigest()
    directory = engine == "faster_whisper"
    files = tuple(ArtifactFile(name, digest, 5) for name in (
        "config.json", "model.bin", "tokenizer.json")) if directory else ()
    return ProductModel(id=model_id, engine=engine, filename=model_id if directory else model_id + ".data",
                        artifact_kind="directory" if directory else "file", revision="fixture-revision",
                        files=files, sha256=digest, bytes=15 if directory else 5,
                        source="fixture://" + model_id, provisioning_allowed=True,
                        rights_status="SIMULATED")


def test_public_catalog_has_124_distinct_portal_ids_and_no_paths_or_urls(app_client):
    client, service = app_client
    payload = client.get("/api/v2/stt/models").json()
    catalog = [item for item in payload["models"] if item["engine"] == "kroko_onnx"]
    assert len(catalog) == 124
    assert len({item["catalogId"] for item in catalog}) == 124
    assert all(not item["downloadAllowed"] for item in catalog)
    assert str(service.settings.data_root_path) not in json.dumps(payload)
    assert "https://" not in json.dumps(payload)


@pytest.mark.parametrize("method,path", [
    ("post", "/api/v2/stt/models/refresh"),
    ("post", "/api/v2/stt/models/faster-whisper-tiny/download"),
    ("get", "/api/v2/stt/downloads"),
    ("get", "/api/v2/stt/downloads/unknown"),
    ("post", "/api/v2/stt/downloads/unknown/cancel"),
    ("delete", "/api/v2/stt/installations/unknown"),
])
def test_all_management_mutations_are_guarded_before_side_effects(app_client, method, path):
    client, service = app_client
    assert getattr(client, method)(path).status_code == 401
    assert service.stt_model_manager.downloads.snapshot() == []


def test_http_jobs_dedupe_cancel_and_machine_readable_gate_failures(app_client):
    client, service = app_client
    path = "/api/v2/stt/models/faster-whisper-tiny/download"
    response = client.post(path, headers=AUTH)
    assert response.status_code == 202
    job_id = response.json()["jobId"]
    assert client.post(path, headers=AUTH).status_code == 200
    assert client.get("/api/v2/stt/downloads/" + job_id, headers=AUTH).json()["state"] == "queued"
    assert client.post(f"/api/v2/stt/downloads/{job_id}/cancel", headers=AUTH).status_code == 200
    assert client.post(f"/api/v2/stt/downloads/{job_id}/cancel", headers=AUTH).status_code == 409
    assert client.post("/api/v2/stt/models/unknown/download", headers=AUTH).status_code == 404
    kroko = next(item for item in service.stt_model_manager.authority if item.engine == "kroko_onnx")
    blocked = client.post(f"/api/v2/stt/models/{kroko.id}/download", headers=AUTH)
    assert blocked.status_code == 422
    assert blocked.json()["error"]["code"] == "model_download_not_qualified"


def test_refresh_routes_never_load_download_or_change_effective_roles(app_client, monkeypatch):
    client, service = app_client
    manager = service.stt_model_manager
    monkeypatch.setattr(manager, "load_probe", lambda item: pytest.fail("unexpected native load"))
    monkeypatch.setattr(manager, "reconcile_downloads", lambda: pytest.fail("unexpected download trigger"))
    previous = dict(manager.snapshot().active)
    for route in ("/api/v2/stt/models/refresh", "/api/models/refresh"):
        assert client.post(route, headers=AUTH).status_code == 200
    assert manager.snapshot().active == previous
    assert manager.downloads.snapshot() == []


def test_v2_and_legacy_settings_share_revision_persistence_and_restart(app_client):
    client, service = app_client
    response = client.patch("/api/v2/settings/server", headers=AUTH, json={
        "baseSettingsRevision": 0, "changes": {
            "stt.autoDownload.enabled": True,
            "stt.autoDownload.selectedModelIds": ["faster-whisper-tiny"]}})
    assert response.status_code == 200 and response.json()["settingsRevision"] == 1
    assert service.settings.stt_auto_download_enabled
    assert len(service.stt_model_manager.downloads.snapshot()) == 1
    update = client.patch("/api/config", headers=AUTH, json={"settings": {
        "stt_auto_download_enabled": False, "max_sessions": 7}})
    assert update.status_code == 200
    assert service.settings_control.settings_revision == 2
    assert service.settings.max_sessions == 7
    persisted = json.loads(Path(service.settings.runtime_config_path).read_text(encoding="utf-8"))
    assert persisted["settingsControlOverlay"]["stt.autoDownload.enabled"] is False
    assert "stt_auto_download_enabled" not in persisted["settings"]
    assert "stt_auto_download_model_ids" not in persisted["settings"]
    assert service.stt_model_manager.downloads.snapshot()[0]["state"] == "cancelled"
    app = create_app(replace(service.settings), scheduler_factory=ManualScheduler, recorder_factory=FakeRecorder)
    restored = app.state.voicestt_service
    try:
        assert restored.settings_control.settings_revision == 2
        assert restored.settings.stt_auto_download_enabled is False
        assert restored.settings.stt_auto_download_model_ids == ["faster-whisper-tiny"]
        assert restored.stt_model_manager.downloads.snapshot() == []
    finally:
        restored.stop()


def test_unknown_ids_stale_revision_nochange_and_persistence_failure_are_atomic(app_client, monkeypatch):
    client, service = app_client
    base = {"baseSettingsRevision": 0}
    unknown = client.patch("/api/v2/settings/server", headers=AUTH, json={**base,
        "changes": {"stt.autoDownload.enabled": True, "stt.autoDownload.selectedModelIds": ["unknown"]}})
    assert unknown.status_code == 422
    assert service.settings_control.settings_revision == 0 and not service.settings.stt_auto_download_enabled
    stale = client.patch("/api/v2/settings/server", headers=AUTH, json={
        "baseSettingsRevision": 1, "changes": {"stt.autoDownload.enabled": True}})
    assert stale.status_code == 409
    nochange = client.patch("/api/v2/settings/server", headers=AUTH, json={**base,
        "changes": {"stt.autoDownload.enabled": False}})
    assert nochange.json()["result"] == "no_change"
    monkeypatch.setattr(service.config_store, "_write_merged", lambda *a: (_ for _ in ()).throw(OSError("secret")))
    for route, payload in [
        ("/api/v2/settings/server", {**base, "changes": {"stt.autoDownload.enabled": True}}),
        ("/api/config", {"settings": {"stt_auto_download_enabled": True, "max_sessions": 7}}),
    ]:
        response = client.patch(route, headers=AUTH, json=payload)
        assert response.status_code == 500
        assert "secret" not in response.text
        assert service.settings_control.settings_revision == 0
        assert not service.settings.stt_auto_download_enabled
        assert service.settings.max_sessions == 4
        assert service.stt_model_manager.downloads.snapshot() == []


@pytest.mark.parametrize("engine", ["faster_whisper", "kroko_onnx"])
def test_both_engines_use_one_queue_and_download_does_not_select_models(tmp_path, engine):
    entry = synthetic(engine)
    calls = []

    def fetch(source, path):
        calls.append(source)
        path.write_bytes(b"model")
        return source

    manager = STTModelManager(runtime_root=tmp_path, authority=[entry],
        intent=OperatorIntent(global_auto_download=True, selected_model_ids=(entry.id,)),
        provisioner=AtomicModelProvisioner(fetcher=fetch))
    manager.download_rights = lambda product: True  # synthetic gate, no provider claim
    manager.refresh()
    assert calls == []
    manager.reconcile_downloads()
    manager.downloads.start()
    try:
        wait_job(manager.downloads, manager.downloads.snapshot()[0]["jobId"], "completed")
        assert manager.is_installed(entry)
        assert manager.snapshot().active == {} and not manager.snapshot().minimum_ready
        assert len(calls) == (3 if engine == "faster_whisper" else 1)
    finally:
        manager.downloads.stop()


def test_selected_errors_do_not_retry_when_unrelated_model_is_selected(tmp_path):
    a, b = synthetic(model_id="a"), synthetic(model_id="b")
    manager = STTModelManager(runtime_root=tmp_path, authority=[a, b],
        intent=OperatorIntent(global_auto_download=True, selected_model_ids=("a",)))
    manager.reconcile_downloads()
    first = manager.downloads.snapshot()[0]
    manager.downloads.cancel(first["jobId"])
    manager.intent = replace(manager.intent, selected_model_ids=("a", "b"))
    manager.reconcile_downloads()
    assert [job["modelId"] for job in manager.downloads.snapshot()] == ["a", "b"]
    manager.reconcile_downloads()
    assert len(manager.downloads.snapshot()) == 2


def test_delete_only_one_unreferenced_managed_copy_and_preserve_external(app_client, tmp_path):
    client, service = app_client
    manager = service.stt_model_manager
    root = manager.default_root("faster_whisper")
    root.mkdir(parents=True)
    external = tmp_path / "external"
    for path in (root / "unused", external / "unused"):
        path.mkdir(parents=True)
        (path / "config.json").write_text("{}")
        (path / "model.bin").write_bytes(b"model")
    manager.intent = replace(manager.intent, engines={"faster_whisper": {"custom_paths": [str(external)]}})
    manager.refresh_inventory()
    copies = project_inventory(manager, admin=True)["installations"]
    assert len(copies) == 2 and len({item["installationId"] for item in copies}) == 2
    outside = next(item for item in copies if item["origin"] == "external")
    inside = next(item for item in copies if item["origin"] == "managed")
    assert client.delete("/api/v2/stt/installations/" + outside["installationId"], headers=AUTH).status_code == 409
    assert client.delete("/api/v2/stt/installations/" + inside["installationId"], headers=AUTH).status_code == 200
    assert (external / "unused" / "model.bin").exists() and not (root / "unused").exists()


def test_public_status_distinguishes_initialized_inventory_and_ram(app_client):
    client, service = app_client
    service.ready.set()
    service.scheduler = None
    service._model_state = "unloaded"
    public = client.get("/api/v2/server/status").json()
    assert public["ready"] and public["ok"] and not public["loaded"] and not public["sttReady"]
    assert public["stt"]["lanes"]["final"]["requested"]["modelId"] == "faster-whisper-small"
    assert "jobs" not in public["downloads"]
    assert service.settings.data_root_path not in json.dumps(public)
    assert AUTH["X-Admin-Key"] not in json.dumps(public)
    assert "jobs" in client.get("/api/v2/server/status", headers=AUTH).json()["downloads"]


@pytest.mark.parametrize("reason", ["configured", "effective", "loading", "admission", "job"])
def test_delete_refuses_every_runtime_and_job_reference(app_client, reason):
    client, service = app_client
    manager = service.stt_model_manager
    entry = synthetic(model_id="unused")
    manager.authority = (*manager.authority, entry)
    if reason == "job":
        manager.downloads.enqueue(entry.id)
    target = manager.default_root(entry.engine) / entry.filename
    target.mkdir(parents=True)
    for file in entry.files:
        (target / file.path).write_bytes(b"model")
    snapshot = manager.refresh_inventory()
    candidate = next(item for item in snapshot.candidates if item.product_id == entry.id)
    if reason == "configured":
        service.settings.model = entry.id
    elif reason == "effective":
        manager._snapshot = replace(snapshot, active={"final": candidate})
    elif reason == "loading":
        service._model_state = "loading"
    elif reason == "admission":
        service.sessions.reserve("pending")
    response = client.delete("/api/v2/stt/installations/" + installation_id(candidate), headers=AUTH)
    assert response.status_code == 409 and target.exists()
    service.sessions.release_reservation("pending")


def test_requested_engine_disable_gates_jobs_before_runtime_refresh(app_client):
    client, service = app_client
    previous = service.stt_model_manager.intent
    response = client.patch("/api/config", headers=AUTH, json={"settings": {
        "stt_engine_settings": {"faster_whisper": {"enabled": False}}}})
    assert response.status_code == 200
    assert service.stt_model_manager.intent is previous
    refused = client.post("/api/v2/stt/models/faster-whisper-tiny/download", headers=AUTH)
    assert refused.status_code == 422 and refused.json()["error"]["code"] == "model_disabled"
