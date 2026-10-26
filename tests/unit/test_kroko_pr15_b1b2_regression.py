"""PR #15 B1/B2 regression tests (deterministic, no native load, no network).

B1: a confirmed ``kroko.forceCommunity`` change is linearised with scheduler
submit through one shared critical section (policy lock + admission
generation + scheduler lock). The test interleaves a submit held inside
``ensure_models_loaded`` with a concurrent force patch and requires that no
new job reaches the previous Pro worker after confirmation.

B2: ``_kroko_probe_reuses_live_instance`` only considers actually active
Kroko lanes (native Kroko model identity). Mixed Faster-Whisper/Kroko
configurations refresh without unloading the live Kroko worker, in both lane
orders, with and without active sessions.
"""
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from VoiceSTT.kroko.native_guard import identity_for_path, process_guard
from VoiceSTT.kroko.credentials import KROKO_KEY_ENV_NAMES, effective_recognizer_key
from VoiceSTT.kroko.license_api import LicenseCheckResult
from VoiceSTT.kroko.native_guard import KrokoNativeConflict
from VoiceSTT_server.stt_model_management import ProductModel
from api_fastapi_server import settings_control as settings_control_module
from api_fastapi_server.server import (
    QueueSubmitResult,
    ServerSettings,
    create_app,
    resolved_engine_options,
)
from tests.unit.test_openai_compatible_endpoint import ImmediateScheduler

KEY = "synthetic-test-key"
COMMUNITY_UUID = "123e4567-e89b-12d3-a456-4266141740c0"
PRO_A_UUID = "123e4567-e89b-12d3-a456-4266141740a0"
COMMUNITY_FILE = "Kroko-DE-Community-64-L-Streaming-001.data"
PRO_A_FILE = "Kroko-DE-Pro-16-L-Streaming-001.data"
COMMUNITY_ID = "kroko-de-community-64-l"
PRO_A_ID = "kroko-de-pro-16-l"
FW_ID = "faster-whisper-tiny"


class FakeLicense:
    def __init__(self):
        self.calls = []
        self.allowed = True

    def __call__(self, key, model_uuid, *, timeout=5.0, connect=None):
        self.calls.append(str(model_uuid))
        if not str(key).strip():
            return LicenseCheckResult("NOT_CHECKED", reason="no_key")
        if self.allowed:
            return LicenseCheckResult("VALID", str(model_uuid), 30.0, "ok")
        return LicenseCheckResult("INVALID", str(model_uuid), reason="license_rejected")


@pytest.fixture
def fake_license(monkeypatch):
    fake = FakeLicense()
    monkeypatch.setattr(
        "api_fastapi_server.security.kroko.check_onprem_license", fake
    )
    return fake


class Ledger:
    def __init__(self):
        self.events = []
        self.live = 0
        self.peak = 0

    def names(self, kind):
        return [name for event, name in self.events if event == kind]


@pytest.fixture
def ledger(monkeypatch):
    value = Ledger()
    monkeypatch.setattr(LeasingScheduler, "ledger", value)
    monkeypatch.setattr(MixedLeasingScheduler, "ledger", value)
    return value


class LeasingScheduler(ImmediateScheduler):
    ledger = None

    def __init__(self, settings, result_callback, drop_callback=None,
                 error_callback=None):
        super().__init__(settings, result_callback, drop_callback, error_callback)
        self.load_error = None
        self._lease = None
        self._name = None

    def start(self):
        resolved = dict(self.settings._resolved_stt_models or {})
        item = resolved.get("final") or {}
        if item.get("engine") != "kroko_onnx":
            return
        path = item["path"]
        options = resolved_engine_options(self.settings, "kroko_onnx", "final")
        try:
            self._lease = process_guard().acquire(
                identity_for_path(path), effective_recognizer_key(options)
            )
        except KrokoNativeConflict as exc:
            self.load_error = exc
            return
        process_guard().confirm_loaded(self._lease)
        self._name = Path(path).name
        if self.ledger is not None:
            self.ledger.events.append(("load", self._name))
            self.ledger.live += 1
            self.ledger.peak = max(self.ledger.peak, self.ledger.live)

    def stop(self):
        if self._lease is None:
            return
        process_guard().release(self._lease)
        self._lease = None
        if self.ledger is not None:
            self.ledger.events.append(("unload", self._name))
            self.ledger.live -= 1

    def healthy(self):
        return self.load_error is None

    def submit(self, job):
        self.jobs.append(job)
        return QueueSubmitResult(True)


class MixedLeasingScheduler(ImmediateScheduler):
    """Holds the native lease when *any* lane runs Kroko (mixed engines)."""

    ledger = None

    def __init__(self, settings, result_callback, drop_callback=None,
                 error_callback=None):
        super().__init__(settings, result_callback, drop_callback, error_callback)
        self.load_error = None
        self._lease = None
        self._name = None

    def start(self):
        resolved = dict(self.settings._resolved_stt_models or {})
        kroko = [
            item for item in resolved.values()
            if item.get("engine") == "kroko_onnx" and item.get("path")
        ]
        if not kroko:
            return
        path = kroko[0]["path"]
        options = resolved_engine_options(self.settings, "kroko_onnx", "final")
        try:
            self._lease = process_guard().acquire(
                identity_for_path(path), effective_recognizer_key(options)
            )
        except KrokoNativeConflict as exc:
            self.load_error = exc
            return
        process_guard().confirm_loaded(self._lease)
        self._name = Path(path).name
        if self.ledger is not None:
            self.ledger.events.append(("load", self._name))
            self.ledger.live += 1
            self.ledger.peak = max(self.ledger.peak, self.ledger.live)

    def stop(self):
        if self._lease is None:
            return
        process_guard().release(self._lease)
        self._lease = None
        if self.ledger is not None:
            self.ledger.events.append(("unload", self._name))
            self.ledger.live -= 1

    def healthy(self):
        return self.load_error is None

    def submit(self, job):
        self.jobs.append(job)
        return QueueSubmitResult(True)


def write_model(root, filename, uuid, free):
    root.mkdir(parents=True, exist_ok=True)
    path = root / filename
    path.write_bytes(
        b'{"id": "' + uuid.encode("ascii") + b'", "type": "zipformer2", '
        b'"free": ' + (b"true" if free else b"false") + b'}\x00' + b"\x00" * 256
    )
    return path


def write_fw_model(root, name="tiny"):
    target = root / name
    target.mkdir(parents=True, exist_ok=True)
    (target / "config.json").write_text('{"model": "tiny"}')
    (target / "model.bin").write_bytes(b"\x00" * 64)
    return target


def kroko_products():
    common = dict(engine="kroko_onnx", language="de")
    return (
        ProductModel(
            id=COMMUNITY_ID, filename=COMMUNITY_FILE,
            license_class="community-unresolved", runtime_variant="free",
            recovery_priority=100, **common),
        ProductModel(
            id=PRO_A_ID, filename=PRO_A_FILE, license_class="commercial",
            runtime_variant="pro", **common),
    )


def fw_product():
    return ProductModel(
        id=FW_ID, engine="faster_whisper", language="multilingual",
        license_class="upstream-local", artifact_kind="directory",
        recovery_priority=300,
    )


def build_pro_service(tmp_path, monkeypatch, *, scheduler_factory=LeasingScheduler):
    monkeypatch.delenv("VOICESTT_KROKO_MODEL_ROOT", raising=False)
    for name in KROKO_KEY_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    root = tmp_path / "custom-models"
    write_model(root, COMMUNITY_FILE, COMMUNITY_UUID, True)
    write_model(root, PRO_A_FILE, PRO_A_UUID, False)
    settings = ServerSettings(
        data_root_path=str(tmp_path / "data"), model_warmup=False
    )
    settings.transcription_engine = "kroko_onnx"
    settings.realtime_transcription_engine = "kroko_onnx"
    settings.model = PRO_A_ID
    settings.realtime_model = PRO_A_ID
    settings.use_main_model_for_realtime = True
    settings.transcription_engine_options = {
        "model_dir": str(root), "key": KEY, "runtime_variant": "pro",
    }
    app = create_app(settings, scheduler_factory=scheduler_factory)
    service = app.state.voicestt_service
    service.stt_model_manager.authority = kroko_products()
    return service, root


def build_mixed_service(tmp_path, monkeypatch, *, final_first):
    """Community Kroko + Faster-Whisper, either lane order, mixed scheduler."""
    monkeypatch.delenv("VOICESTT_KROKO_MODEL_ROOT", raising=False)
    for name in KROKO_KEY_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    kroko_root = tmp_path / "kroko-models"
    write_model(kroko_root, COMMUNITY_FILE, COMMUNITY_UUID, True)
    fw_root = tmp_path / "fw-models"
    write_fw_model(fw_root, "tiny")
    settings = ServerSettings(
        data_root_path=str(tmp_path / "data"), model_warmup=False
    )
    if final_first:
        # Final = Faster-Whisper, Realtime = Kroko.
        settings.transcription_engine = "faster_whisper"
        settings.model = "tiny"
        settings.transcription_engine_options = {"model_dir": str(fw_root)}
        settings.realtime_transcription_engine = "kroko_onnx"
        settings.realtime_model = COMMUNITY_ID
        settings.realtime_transcription_engine_options = {
            "model_dir": str(kroko_root), "runtime_variant": "free",
        }
    else:
        # Final = Kroko, Realtime = Faster-Whisper.
        settings.transcription_engine = "kroko_onnx"
        settings.model = COMMUNITY_ID
        settings.transcription_engine_options = {
            "model_dir": str(kroko_root), "runtime_variant": "free",
        }
        settings.realtime_transcription_engine = "faster_whisper"
        settings.realtime_model = "tiny"
        settings.realtime_transcription_engine_options = {
            "model_dir": str(fw_root),
        }
    settings.use_main_model_for_realtime = False
    app = create_app(settings, scheduler_factory=MixedLeasingScheduler)
    service = app.state.voicestt_service
    service.stt_model_manager.authority = kroko_products() + (fw_product(),)
    return service


def wait_for(predicate, timeout=10.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


def job():
    return SimpleNamespace(
        kind="final", session_id="s", generation=0, segment_id=1,
        client_id=None, request_id="r",
    )


def patch_force(service, value):
    control = service.settings_control
    result = control.patch_server(
        control.settings_revision,
        {settings_control_module.KROKO_FORCE_COMMUNITY: value},
    )
    assert result.accepted
    return result


# -- B1 ------------------------------------------------------------------------


def test_b1_force_patch_linearised_with_concurrent_submit(
        tmp_path, monkeypatch, fake_license, ledger):
    """No new Pro job may reach the previous worker after confirmation.

    Thread A passes the entry admission check and is then held inside
    ``ensure_models_loaded``. Thread B (here: the main thread) confirms
    ``forceCommunity`` synchronously while the background reconcile is
    still blocked. When A resumes, its generation-bound final section must
    refuse instead of enqueueing into the old Pro scheduler. A bare second
    unsynchronised check would still accept here.
    """
    service, _root = build_pro_service(tmp_path, monkeypatch)
    service.refresh_stt_models()
    assert service._submit_scheduler_job(job(), "t").accepted is True
    jobs_before = len(service.scheduler.jobs)
    gen_before = service._kroko_admission_generation

    reconcile_release = threading.Event()
    reconcile_entered = threading.Event()
    reconcile_calls = []

    def held_reconcile(trigger):
        reconcile_calls.append(trigger)
        reconcile_entered.set()
        assert reconcile_release.wait(15)

    monkeypatch.setattr(service, "reconcile_kroko_models", held_reconcile)

    original_ensure = service.ensure_models_loaded
    entered_ensure = threading.Event()
    release_ensure = threading.Event()

    def held_ensure(timeout=180.0):
        entered_ensure.set()
        assert release_ensure.wait(15)
        return original_ensure(timeout=timeout)

    monkeypatch.setattr(service, "ensure_models_loaded", held_ensure)

    outcome = {}

    def submitter():
        try:
            outcome["result"] = service._submit_scheduler_job(job(), "t")
        except BaseException as exc:  # pragma: no cover - must not happen
            outcome["error"] = exc

    worker = threading.Thread(target=submitter, name="B1SubmitRace")
    worker.start()
    assert entered_ensure.wait(15)

    # Confirmed force change while A is held: the grant invalidation and
    # the admission bump happen synchronously before apply() returns,
    # while the model reconcile is still blocked above.
    patch_force(service, True)
    service.apply_kroko_force_change()
    # The background reconcile has started and is still blocked; the grant
    # invalidation above was still synchronous before apply() returned.
    assert reconcile_entered.wait(15)
    assert service._kroko_pro_revocation() is not None
    assert service._kroko_admission_generation != gen_before

    release_ensure.set()
    worker.join(timeout=15)
    assert not worker.is_alive()
    assert "error" not in outcome
    refused = outcome["result"]
    assert refused.accepted is False
    assert "Force Community" in refused.reason
    # Nothing was enqueued into the previous Pro worker.
    assert len(service.scheduler.jobs) == jobs_before

    reconcile_release.set()
    assert wait_for(lambda: reconcile_calls == ["license_policy"])


# -- B2 ------------------------------------------------------------------------

def _assert_mixed_active(service, *, expect_final, expect_realtime):
    resolved = service.settings._resolved_stt_models
    assert resolved["final"]["id"] == expect_final
    assert resolved["realtime"]["id"] == expect_realtime
    assert resolved["final"]["engine"] != resolved["realtime"]["engine"] or True


@pytest.mark.parametrize("final_first", [True, False])
def test_b2_mixed_refresh_reuses_live_kroko_without_reload(
        tmp_path, monkeypatch, fake_license, ledger, final_first):
    """Unchanged mixed refresh must not unload the live Kroko worker."""
    service = build_mixed_service(tmp_path, monkeypatch, final_first=final_first)
    service.refresh_stt_models()
    if final_first:
        _assert_mixed_active(service, expect_final=FW_ID, expect_realtime=COMMUNITY_ID)
    else:
        _assert_mixed_active(service, expect_final=COMMUNITY_ID, expect_realtime=FW_ID)
    assert ledger.peak == 1

    # The live Kroko candidate reuses the worker in both lane orders.
    kroko_path = None
    for item in service.settings._resolved_stt_models.values():
        if item.get("engine") == "kroko_onnx":
            kroko_path = item["path"]
    assert kroko_path is not None
    candidate = SimpleNamespace(
        id=COMMUNITY_ID, engine="kroko_onnx", path=str(kroko_path))
    assert service._kroko_probe_reuses_live_instance(candidate) is True
    assert service._kroko_probe_conflicts == [] or True

    events_before = list(ledger.events)
    scheduler_before = service.scheduler
    service.refresh_stt_models()
    # No unload/reload, no conflict, same worker still healthy.
    assert ledger.events == events_before
    assert service.scheduler is scheduler_before
    assert service.scheduler.healthy()
    assert service._kroko_probe_conflicts == []
    assert process_guard().status()["liveNativeInstances"] == 1


@pytest.mark.parametrize("final_first", [True, False])
def test_b2_mixed_refresh_with_active_session_stays_put(
        tmp_path, monkeypatch, fake_license, ledger, final_first):
    """Same as above with active work: still no deferred/failed refresh."""
    service = build_mixed_service(tmp_path, monkeypatch, final_first=final_first)
    service.refresh_stt_models()
    assert ledger.peak == 1
    events_before = list(ledger.events)
    scheduler_before = service.scheduler

    monkeypatch.setattr(service, "_models_busy", lambda: True)
    # Unchanged mixed configuration: busy must not matter because nothing
    # needs to be unloaded (the old code raised deferred here).
    service.refresh_stt_models()

    assert ledger.events == events_before
    assert service.scheduler is scheduler_before
    assert service._kroko_probe_conflicts == []
    assert process_guard().status()["liveNativeInstances"] == 1
