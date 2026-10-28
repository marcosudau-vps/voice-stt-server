"""PR #15 Abschlusskorrektur: deterministic regression tests.

One test group per finding of the authoritative re-assessment (P0-01, P0-02,
P1-03 .. P1-06 and the key-context protection case). Everything runs through
the real chain gate -> state -> service -> model manager -> guard; only the
provider round trip and the native recognizer are replaced:

* ``FakeLicense`` stands in for the license server (never opens a socket and
  never sees or stores a real key),
* ``LeasingScheduler`` behaves like the native worker with respect to the
  process guard (it takes a lease on start and gives it back on stop), so the
  single-native-instance rule is observed from the outside via a ledger.
"""
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.usefixtures("pro_capable_test_runtime")

from VoiceSTT.kroko import native_guard
from VoiceSTT.kroko.credentials import KROKO_KEY_ENV_NAMES, effective_recognizer_key
from VoiceSTT.kroko.license_api import LicenseCheckResult
from VoiceSTT.kroko.native_guard import (
    CONCURRENT_IDENTITY,
    KEY_CONTEXT_CHANGE,
    PRO_IDENTITY_CHANGE,
    PRO_KEY_REQUIRED,
    KrokoNativeConflict,
    KrokoNativeGuard,
    NativeIdentity,
    identity_for_path,
    process_guard,
)
from VoiceSTT_server.stt_model_management import ProductModel
from api_fastapi_server import settings_control as settings_control_module
from api_fastapi_server.kroko_runtime import (
    enforce_kroko_single_identity,
    kroko_model_key,
)
from api_fastapi_server.security.kroko import KrokoLicenseGate
from api_fastapi_server.server import (
    QueueSubmitResult,
    ServerSettings,
    create_app,
    resolved_engine_options,
)
from tests.unit.test_openai_compatible_endpoint import ImmediateScheduler

KEY = "synthetic-test-key"
OTHER_KEY = "synthetic-rotated-key"
COMMUNITY_UUID = "123e4567-e89b-12d3-a456-4266141740c0"
PRO_A_UUID = "123e4567-e89b-12d3-a456-4266141740a0"
PRO_B_UUID = "123e4567-e89b-12d3-a456-4266141740a1"
COMMUNITY_FILE = "Kroko-DE-Community-64-L-Streaming-001.data"
PRO_A_FILE = "Kroko-DE-Pro-16-L-Streaming-001.data"
PRO_B_FILE = "Kroko-DE-Pro-32-L-Streaming-001.data"
COMMUNITY_ID = "kroko-de-community-64-l"
PRO_A_ID = "kroko-de-pro-16-l"
PRO_B_ID = "kroko-de-pro-32-l"


# -- fakes -------------------------------------------------------------------

class FakeLicense:
    """Replaces the provider round trip. Records model UUIDs, never keys."""

    def __init__(self):
        self.calls = []
        self.allowed = True
        self.seconds = 30.0
        self._hold = None

    def hold(self):
        entered, release = threading.Event(), threading.Event()
        self._hold = (entered, release)
        return entered, release

    def __call__(self, key, model_uuid, *, timeout=5.0, connect=None):
        self.calls.append(str(model_uuid))
        if self._hold is not None:
            entered, release = self._hold
            entered.set()
            assert release.wait(10)
        if not str(key).strip():
            return LicenseCheckResult("NOT_CHECKED", reason="no_key")
        if self.allowed:
            return LicenseCheckResult("VALID", str(model_uuid), self.seconds, "ok")
        return LicenseCheckResult(
            "INVALID", str(model_uuid), reason="license_rejected"
        )


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
    return value


class LeasingScheduler(ImmediateScheduler):
    """Fake worker that holds the native guard lease like the real engine."""

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


def write_model(root, filename, uuid, free):
    root.mkdir(parents=True, exist_ok=True)
    path = root / filename
    path.write_bytes(
        b'{"id": "' + uuid.encode("ascii") + b'", "type": "zipformer2", '
        b'"free": ' + (b"true" if free else b"false") + b'}\x00' + b"\x00" * 256
    )
    return path


def products():
    common = dict(engine="kroko_onnx", language="de")
    return (
        ProductModel(
            id=COMMUNITY_ID, filename=COMMUNITY_FILE,
            license_class="community-unresolved", runtime_variant="free",
            recovery_priority=100, **common),
        ProductModel(
            id=PRO_A_ID, filename=PRO_A_FILE, license_class="commercial",
            runtime_variant="pro", **common),
        ProductModel(
            id=PRO_B_ID, filename=PRO_B_FILE, license_class="commercial",
            runtime_variant="pro", **common),
    )


ALL_FILES = (
    (COMMUNITY_FILE, COMMUNITY_UUID, True),
    (PRO_A_FILE, PRO_A_UUID, False),
    (PRO_B_FILE, PRO_B_UUID, False),
)


def build_service(tmp_path, monkeypatch, *, model, key=KEY,
                  scheduler_factory=LeasingScheduler, files=ALL_FILES,
                  roots=True):
    monkeypatch.delenv("VOICESTT_KROKO_MODEL_ROOT", raising=False)
    for name in KROKO_KEY_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    root = tmp_path / "custom-models"
    for filename, uuid, free in files:
        write_model(root, filename, uuid, free)
    options = {"runtime_variant": "pro"}
    if roots:
        options["model_dir"] = str(root)
    if key:
        options["key"] = key
    settings = ServerSettings(
        data_root_path=str(tmp_path / "data"), model_warmup=False
    )
    settings.transcription_engine = "kroko_onnx"
    settings.realtime_transcription_engine = "kroko_onnx"
    settings.model = model
    settings.realtime_model = model
    settings.use_main_model_for_realtime = True
    settings.transcription_engine_options = options
    app = create_app(settings, scheduler_factory=scheduler_factory)
    service = app.state.voicestt_service
    service.stt_model_manager.authority = products()
    return service, root


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


def active_ids(service):
    return {
        role: item["id"]
        for role, item in service.settings._resolved_stt_models.items()
    }


def patch_force(service, value):
    control = service.settings_control
    result = control.patch_server(
        control.settings_revision,
        {settings_control_module.KROKO_FORCE_COMMUNITY: value},
    )
    assert result.accepted
    return result


# -- P0-01: a late license answer never restores older intent ------------------

def test_late_answer_cannot_restore_old_key_or_force(fake_license):
    gate = KrokoLicenseGate()
    entered, release = fake_license.hold()
    done = threading.Event()
    seen = []

    decision, started = gate.refresh(
        PRO_A_UUID, options={"key": KEY}, background=True,
        on_result=lambda current: (seen.append(current), done.set()),
    )
    assert started is True and decision["tier"] == "checking"
    assert entered.wait(10)

    # A newer operator intent arrives while the old worker is held back.
    gate.bind_intent(options={"key": OTHER_KEY}, force_community=True)
    before = gate.state.public_snapshot()
    release.set()
    assert done.wait(10)

    after = gate.state.public_snapshot()
    assert after["forceCommunity"] is True
    assert after["keyPresent"] is True
    assert after["generation"] == before["generation"]
    assert after["status"] != "VALID"
    assert gate.state.pro_enabled_for(PRO_A_UUID) is False
    assert seen[0]["tier"] == "community"
    assert seen[0]["reason"] == "force_community"
    # The newer binding is still the authoritative one (no re-bind of the old).
    assert gate.state.bind(key=OTHER_KEY, force_community=True) is False
    assert fake_license.calls == [PRO_A_UUID]


def test_late_answer_for_old_key_leaves_new_key_checkable(fake_license):
    gate = KrokoLicenseGate()
    entered, release = fake_license.hold()
    done = threading.Event()
    gate.refresh(
        PRO_A_UUID, options={"key": KEY}, background=True,
        on_result=lambda _current: done.set(),
    )
    assert entered.wait(10)
    gate.bind_intent(options={"key": OTHER_KEY}, force_community=False)
    release.set()
    assert done.wait(10)
    assert gate.state.pro_enabled_for(PRO_A_UUID) is False
    assert gate.state.public_snapshot()["keyPresent"] is True
    # The new key was not swallowed by the old in-flight check: it is checked.
    fake_license._hold = None
    decision, started = gate.refresh(
        PRO_A_UUID, options={"key": OTHER_KEY}, connect=None
    )
    assert started is True and decision["tier"] == "pro"
    assert fake_license.calls == [PRO_A_UUID, PRO_A_UUID]


def test_service_policy_read_and_bind_cannot_interleave(
        tmp_path, monkeypatch, fake_license):
    """A held old check + newer force intent: the service keeps the newer one."""
    service, _root = build_service(
        tmp_path, monkeypatch, model=PRO_A_ID, scheduler_factory=ImmediateScheduler)
    gate = service.security.kroko
    # Drop the init-time proof, then start a held background check.
    gate.state.bind(key="", force_community=False)
    entered, release = fake_license.hold()
    done = threading.Event()
    service.refresh_kroko_license_policy(
        background=True, on_result=lambda _d: done.set())
    assert entered.wait(10)
    patch_force(service, True)
    service.refresh_kroko_license_policy(network=False)
    release.set()
    assert done.wait(10)
    snapshot = gate.state.public_snapshot()
    assert snapshot["forceCommunity"] is True
    assert gate.state.pro_enabled_for(PRO_A_UUID) is False


# -- P0-02: force community / key withdrawal lock Pro out synchronously --------

def test_force_patch_blocks_pro_jobs_before_background_reconcile(
        tmp_path, monkeypatch, fake_license, ledger):
    service, _root = build_service(tmp_path, monkeypatch, model=PRO_A_ID)
    service.refresh_stt_models()
    assert set(active_ids(service).values()) == {PRO_A_ID}
    assert service.security.kroko.state.pro_enabled_for(PRO_A_UUID)
    assert service._submit_scheduler_job(job(), "t").accepted is True

    release = threading.Event()
    triggers = []

    def held(trigger):
        release.wait(10)
        triggers.append(trigger)

    monkeypatch.setattr(service, "reconcile_kroko_models", held)
    patch_force(service, True)
    service.apply_kroko_force_change()

    # The reconcile worker is still blocked: the lockout must already hold.
    assert triggers == []
    refused = service._submit_scheduler_job(job(), "t")
    assert refused.accepted is False
    assert "Force Community" in refused.reason
    assert service.security.kroko.state.pro_enabled_for(PRO_A_UUID) is False
    assert service.kroko_runtime_status()["proAdmissionRevoked"] is True
    release.set()
    assert wait_for(lambda: triggers == ["license_policy"])


def test_key_removal_blocks_pro_jobs_immediately(
        tmp_path, monkeypatch, fake_license, ledger):
    service, _root = build_service(tmp_path, monkeypatch, model=PRO_A_ID)
    service.refresh_stt_models()
    assert service._kroko_pro_revocation() is None
    del service.settings.transcription_engine_options["key"]
    service.refresh_kroko_license_policy(network=False)
    reason = service._kroko_pro_revocation()
    assert reason is not None and "Lizenzschluessel" in reason
    assert service._submit_scheduler_job(job(), "t").accepted is False
    assert service.security.kroko.state.pro_enabled_for(PRO_A_UUID) is False


def test_force_patch_switches_pro_to_community_through_one_native_instance(
        tmp_path, monkeypatch, fake_license, ledger):
    service, _root = build_service(tmp_path, monkeypatch, model=PRO_A_ID)
    service.refresh_stt_models()
    assert set(active_ids(service).values()) == {PRO_A_ID}
    calls_before = list(fake_license.calls)

    patch_force(service, True)
    service.apply_kroko_force_change()
    assert wait_for(lambda: service._kroko_reconcile_state is not None)

    assert service._kroko_reconcile_state["result"] == "changed"
    assert set(active_ids(service).values()) == {COMMUNITY_ID}
    assert ledger.peak == 1                     # never two native instances
    assert service._kroko_pro_revocation() is None   # Community is not Pro
    assert fake_license.calls == calls_before   # force => no external check
    runtime = service.kroko_runtime_status()
    assert runtime["activeProPresent"] is False
    assert runtime["activeKrokoModels"] == {
        "final": COMMUNITY_ID, "realtime": COMMUNITY_ID}
    # Honest about the native side: the Pro license context was initialised
    # in this process and a Community model does not reset it.
    assert runtime["nativeProContextActive"] is True
    assert service.stt_model_management_status()["krokoRuntime"] == runtime


def test_force_patch_with_active_sessions_defers_instead_of_hot_swapping(
        tmp_path, monkeypatch, fake_license, ledger):
    service, _root = build_service(tmp_path, monkeypatch, model=PRO_A_ID)
    service.refresh_stt_models()
    events_before = list(ledger.events)
    monkeypatch.setattr(service, "_models_busy", lambda: True)

    patch_force(service, True)
    service.apply_kroko_force_change()
    assert wait_for(lambda: service._kroko_reconcile_state is not None)

    state = service._kroko_reconcile_state
    assert state["result"] == "deferred"
    assert ledger.events == events_before        # nothing was unloaded/loaded
    assert set(active_ids(service).values()) == {PRO_A_ID}
    # Active Pro work is rejected for new jobs, and the model refresh is
    # visibly pending - no pretended Community switch.
    assert service._submit_scheduler_job(job(), "t").accepted is False
    runtime = service.kroko_runtime_status()
    assert runtime["modelRefreshPending"] is True
    assert runtime["proAdmissionRevoked"] is True


# -- P1-03: Pro entitlement is established from a Community configuration -------

def test_community_config_with_key_checks_local_pro_candidate(
        tmp_path, monkeypatch, fake_license, ledger):
    service, _root = build_service(tmp_path, monkeypatch, model=COMMUNITY_ID)
    # Init already ran the automatic pre-check against the local Pro file.
    assert fake_license.calls == [PRO_A_UUID]
    snapshot = service.security.kroko.state.public_snapshot()
    assert snapshot["status"] == "VALID"
    assert snapshot["modelUuid"] == PRO_A_UUID

    service.refresh_stt_models()
    # Selection right is separate from activation: Community stays active and
    # no Pro model was loaded natively.
    assert set(active_ids(service).values()) == {COMMUNITY_ID}
    assert PRO_A_FILE not in ledger.names("load")
    management = service.stt_model_management_status()
    pro = next(item for item in management["candidates"]
               if item["productId"] == PRO_A_ID)
    assert pro["eligible"] is True
    assert management["krokoRuntime"]["licenseEntitled"] is True
    assert management["krokoRuntime"]["activeProPresent"] is False


def test_community_config_without_key_or_with_force_makes_no_external_check(
        tmp_path, monkeypatch, fake_license, ledger):
    service, _root = build_service(
        tmp_path, monkeypatch, model=COMMUNITY_ID, key="")
    assert fake_license.calls == []
    assert service.refresh_kroko_license_policy()[0]["reason"] == "no_key"

    service, _root = build_service(
        tmp_path / "second", monkeypatch, model=COMMUNITY_ID)
    fake_license.calls.clear()
    service.security.kroko.state.bind(key="", force_community=False)
    patch_force(service, True)
    decision = service.refresh_kroko_license_policy()[0]
    assert decision["reason"] == "force_community"
    assert fake_license.calls == []


def test_without_local_pro_model_the_state_is_honestly_not_checked(
        tmp_path, monkeypatch, fake_license, ledger):
    service, _root = build_service(
        tmp_path, monkeypatch, model=COMMUNITY_ID,
        files=((COMMUNITY_FILE, COMMUNITY_UUID, True),))
    decision = service.refresh_kroko_license_policy()[0]
    assert decision["tier"] == "community"
    assert decision["reason"] == "pro_model_not_local"
    assert fake_license.calls == []
    assert service.security.kroko.state.public_snapshot()["status"] == "NOT_CHECKED"


# -- P1-04: one native Kroko identity per process, rejected before the load -----

def test_enforce_rejects_two_different_kroko_models_and_shares_one():
    different = ServerSettings(
        transcription_engine="kroko_onnx", model=PRO_A_ID,
        realtime_transcription_engine="kroko_onnx", realtime_model=COMMUNITY_ID)
    with pytest.raises(ValueError, match="zwei unterschiedliche native"):
        enforce_kroko_single_identity(different)

    spelled = ServerSettings(
        transcription_engine="kroko_onnx", model=COMMUNITY_ID,
        realtime_transcription_engine="kroko_onnx", realtime_model=COMMUNITY_FILE,
        use_main_model_for_realtime=False)
    from VoiceSTT.kroko.models import load_manifest
    enforce_kroko_single_identity(spelled, load_manifest())
    assert spelled.use_main_model_for_realtime is True

    mixed = ServerSettings(
        transcription_engine="kroko_onnx", model=COMMUNITY_ID,
        realtime_transcription_engine="faster_whisper", realtime_model="tiny")
    enforce_kroko_single_identity(mixed)       # only one Kroko lane: fine
    assert kroko_model_key(COMMUNITY_FILE) == COMMUNITY_FILE.lower()


def test_final_and_realtime_share_one_kroko_instance(
        tmp_path, monkeypatch, fake_license, ledger):
    service, _root = build_service(tmp_path, monkeypatch, model=PRO_A_ID)
    service.refresh_stt_models()
    assert service.settings.use_main_model_for_realtime is True
    assert active_ids(service) == {"final": PRO_A_ID, "realtime": PRO_A_ID}
    # Load probe + activation, one instance at a time, only this model.
    assert set(ledger.names("load")) == {PRO_A_FILE}
    assert ledger.peak == 1
    assert process_guard().status()["liveNativeInstances"] == 1


def test_scheduler_creation_refuses_two_kroko_identities_before_native_load(
        tmp_path, monkeypatch, fake_license, ledger):
    created = []

    def factory(*args, **kwargs):
        created.append(1)
        return LeasingScheduler(*args, **kwargs)

    service, _root = build_service(
        tmp_path, monkeypatch, model=COMMUNITY_ID, scheduler_factory=factory)
    created.clear()
    service.settings._resolved_stt_models = {
        "final": {"id": PRO_A_ID, "engine": "kroko_onnx",
                  "path": str(_root / PRO_A_FILE)},
        "realtime": {"id": COMMUNITY_ID, "engine": "kroko_onnx",
                     "path": str(_root / COMMUNITY_FILE)},
    }
    service.settings.use_main_model_for_realtime = False
    with pytest.raises(KrokoNativeConflict) as caught:
        service._new_scheduler()
    assert caught.value.code == CONCURRENT_IDENTITY
    assert created == []                                  # factory not reached


def test_probe_refuses_other_pro_identity_before_native_load(
        tmp_path, monkeypatch, fake_license, ledger):
    created = []

    def factory(*args, **kwargs):
        created.append(1)
        return LeasingScheduler(*args, **kwargs)

    service, root = build_service(
        tmp_path, monkeypatch, model=COMMUNITY_ID, scheduler_factory=factory)
    guard = process_guard()
    lease = guard.acquire(identity_for_path(root / PRO_A_FILE), KEY)
    guard.release(lease)                       # Pro A was natively initialised
    created.clear()
    candidate = SimpleNamespace(
        id=PRO_B_ID, engine="kroko_onnx", path=str(root / PRO_B_FILE))
    with pytest.raises(KrokoNativeConflict) as caught:
        service._probe_stt_model(candidate)
    assert caught.value.code == PRO_IDENTITY_CHANGE
    assert caught.value.restart_required is True
    assert created == []


def test_probe_never_loads_a_second_instance_next_to_a_live_one(
        tmp_path, monkeypatch, fake_license, ledger):
    service, root = build_service(tmp_path, monkeypatch, model=COMMUNITY_ID)
    service.refresh_stt_models()
    live = ledger.names("load")
    other = SimpleNamespace(
        id=PRO_A_ID, engine="kroko_onnx", path=str(root / PRO_A_FILE))
    with pytest.raises(KrokoNativeConflict) as caught:
        service._probe_stt_model(other)
    assert caught.value.code == CONCURRENT_IDENTITY
    assert ledger.names("load") == live and ledger.peak == 1
    # The very model that already runs healthy is not loaded a second time.
    same = SimpleNamespace(
        id=COMMUNITY_ID, engine="kroko_onnx", path=str(root / COMMUNITY_FILE))
    assert service._probe_stt_model(same) is True
    assert ledger.names("load") == live


# -- P1-05: one path authority for the pre-check and for admission --------------

def test_license_check_and_eligibility_use_engine_model_dir_only(
        tmp_path, monkeypatch, fake_license, ledger):
    service, root = build_service(tmp_path, monkeypatch, model=PRO_A_ID)
    import os
    assert os.environ.get("VOICESTT_KROKO_MODEL_ROOT") is None
    # The pre-check addressed the header UUID of the file found via the
    # engine option ``model_dir`` - the only root that is configured.
    assert fake_license.calls == [PRO_A_UUID]
    pro = products()[1]
    manager = service.stt_model_manager
    assert manager.locate_local_path(pro) == str(root / PRO_A_FILE)
    assert manager._eligible(pro, "kroko_onnx", []) is True
    # Admission and snapshot agree: the Pro model becomes active.
    service.refresh_stt_models()
    assert set(active_ids(service).values()) == {PRO_A_ID}
    # Without that root the same product is honestly not entitled.
    manager.intent = type(manager.intent)(
        engines={"kroko_onnx": {"enabled": True, "custom_paths": []}},
        kroko_runtime_variant="pro")
    assert manager._eligible(pro, "kroko_onnx", []) is False


# -- P1-06: background result updates entitlement, snapshot and status ---------

def test_background_check_promotes_pro_only_after_reconcile(
        tmp_path, monkeypatch, fake_license, ledger):
    fake_license.allowed = False
    service, _root = build_service(tmp_path, monkeypatch, model=PRO_A_ID)
    service.refresh_stt_models()
    assert set(active_ids(service).values()) == {COMMUNITY_ID}   # fallback

    fake_license.allowed = True
    entered, release = fake_license.hold()
    service.security.kroko.state.bind(key="", force_community=False)
    decisions = service.refresh_kroko_license_policy(
        background=True, reconcile=True)
    assert decisions[0]["tier"] == "checking"
    assert entered.wait(10)
    # While only the check runs: no claim of an active Pro instance.
    runtime = service.stt_model_management_status()["krokoRuntime"]
    assert runtime["activeKrokoModels"] == {
        "final": COMMUNITY_ID, "realtime": COMMUNITY_ID}
    assert runtime["activeProPresent"] is False
    assert PRO_A_FILE not in ledger.names("load")

    release.set()
    assert wait_for(lambda: service._kroko_reconcile_state is not None)
    assert service._kroko_reconcile_state["result"] == "changed"
    assert active_ids(service) == {"final": PRO_A_ID, "realtime": PRO_A_ID}
    status = service.stt_model_management_status()
    assert status["active"]["final"]["id"] == PRO_A_ID
    assert status["krokoLicense"]["proEnabled"] is True
    assert status["krokoRuntime"]["activeProPresent"] is True
    assert ledger.peak == 1
    # Community was unloaded before Pro was loaded (probe + activation).
    events = [name for kind, name in ledger.events if kind == "load"]
    assert events[0] == COMMUNITY_FILE and events[-1] == PRO_A_FILE


def test_busy_server_defers_community_to_pro_transition(
        tmp_path, monkeypatch, fake_license, ledger):
    fake_license.allowed = False
    service, _root = build_service(tmp_path, monkeypatch, model=PRO_A_ID)
    service.refresh_stt_models()
    assert set(active_ids(service).values()) == {COMMUNITY_ID}
    events_before = list(ledger.events)

    fake_license.allowed = True
    service.security.kroko.state.bind(key="", force_community=False)
    monkeypatch.setattr(service, "_models_busy", lambda: True)
    with pytest.raises(RuntimeError, match="Kroko-Instanz"):
        service.refresh_stt_models()
    assert ledger.events == events_before          # no Pro load next to Community
    assert set(active_ids(service).values()) == {COMMUNITY_ID}
    assert service.kroko_runtime_status()["modelRefreshPending"] is True


# -- restart-required cases (key context, other Pro model) ---------------------

def test_key_rotation_after_native_pro_requires_restart_without_fake_grant(
        tmp_path, monkeypatch, fake_license, ledger):
    service, root = build_service(tmp_path, monkeypatch, model=PRO_A_ID)
    service.refresh_stt_models()                 # Pro A natively initialised
    calls = list(fake_license.calls)

    service.settings.transcription_engine_options["key"] = OTHER_KEY
    decision = service.refresh_kroko_license_policy()[0]
    assert decision["reason"] == KEY_CONTEXT_CHANGE
    assert decision["restart_required"] is True
    assert decision["tier"] == "community"
    assert fake_license.calls == calls           # no new grant for a stale context
    entitled, reason = service._kroko_license_entitlement(
        products()[1], str(root / PRO_A_FILE))
    assert entitled is False
    runtime = service.kroko_runtime_status()
    assert runtime["restartRequired"] is True
    assert runtime["restartReason"] == KEY_CONTEXT_CHANGE


def test_switch_to_other_pro_model_is_refused_and_keeps_the_instance(
        tmp_path, monkeypatch, fake_license, ledger):
    service, _root = build_service(tmp_path, monkeypatch, model=PRO_A_ID)
    service.refresh_stt_models()
    events_before = list(ledger.events)
    with pytest.raises(KrokoNativeConflict) as caught:
        service.switch_models({
            "model": PRO_B_ID, "realtime_model": PRO_B_ID,
            "use_main_model_for_realtime": True,
        })
    assert caught.value.code == PRO_IDENTITY_CHANGE
    assert ledger.events == events_before         # the working Pro A stays
    assert set(active_ids(service).values()) == {PRO_A_ID}
    assert service.settings.model == PRO_A_ID


def test_same_pro_model_can_be_reloaded_after_unload(
        tmp_path, monkeypatch, fake_license, ledger):
    service, _root = build_service(tmp_path, monkeypatch, model=PRO_A_ID)
    service.refresh_stt_models()
    loads_before = len(ledger.names("load"))
    service.unload_models(reason="test")
    assert process_guard().status()["liveNativeInstances"] == 0
    service.ensure_models_loaded()
    assert len(ledger.names("load")) == loads_before + 1
    assert set(ledger.names("load")) == {PRO_A_FILE}
    assert ledger.peak == 1


# -- the guard itself -----------------------------------------------------------

def ident(tier, name):
    return NativeIdentity(tier, name)


def test_guard_rules_table():
    guard = KrokoNativeGuard()
    community, pro_a, pro_b = (
        ident("community", "c"), ident("pro", "a"), ident("pro", "b"))
    assert guard.evaluate(pro_a, "") .code == PRO_KEY_REQUIRED
    lease = guard.acquire(community, "")
    assert guard.evaluate(community, "").code == CONCURRENT_IDENTITY
    assert guard.evaluate(pro_a, KEY).code == CONCURRENT_IDENTITY
    guard.release(lease)
    lease = guard.acquire(pro_a, KEY)
    guard.release(lease)
    # Community after Pro: allowed; same Pro again: allowed.
    guard.release(guard.acquire(community, ""))
    guard.release(guard.acquire(pro_a, KEY))
    # Another Pro model, or the same one under another key: restart only.
    assert guard.evaluate(pro_b, KEY).code == PRO_IDENTITY_CHANGE
    assert guard.evaluate(pro_a, OTHER_KEY).code == KEY_CONTEXT_CHANGE
    assert guard.restart_conflict(pro_b, KEY).restart_required is True
    assert guard.restart_conflict(pro_a, KEY) is None
    status = guard.status()
    assert status["nativeProContextActive"] is True
    assert KEY not in repr(status) and "revision" not in repr(status).lower()


def test_guard_does_not_depend_on_key_text_leaking():
    guard = KrokoNativeGuard()
    guard.release(guard.acquire(ident("pro", "a"), KEY))
    assert KEY not in repr(vars(guard))


# -- engine level: the last line of defence before the native singleton ---------

@pytest.fixture
def native_stub(monkeypatch):
    """A stand-in for the *native* recognizer class (not an injected double)."""
    import numpy as np
    from VoiceSTT.transcription_engines import kroko_onnx_engine

    calls = []

    class NativeRecognizer:
        @classmethod
        def from_transducer(cls, **kwargs):
            calls.append(Path(kwargs["model_path"]).name)
            return cls()

    monkeypatch.setattr(
        kroko_onnx_engine, "_load_online_recognizer_class",
        lambda: NativeRecognizer)

    def make(path, key=""):
        from VoiceSTT.transcription_engines import TranscriptionEngineConfig
        options = {"key": key} if key else {}
        return kroko_onnx_engine.KrokoOnnxBackend(
            TranscriptionEngineConfig(model=str(path), engine_options=options),
            numpy_module=np)

    make.calls = calls
    return make


def test_engine_refuses_other_pro_model_before_the_native_call(
        tmp_path, native_stub):
    pro_a = write_model(tmp_path, PRO_A_FILE, PRO_A_UUID, False)
    pro_b = write_model(tmp_path, PRO_B_FILE, PRO_B_UUID, False)
    first = native_stub(pro_a, KEY)
    first.close()
    with pytest.raises(KrokoNativeConflict) as caught:
        native_stub(pro_b, KEY)
    assert caught.value.code == PRO_IDENTITY_CHANGE
    assert native_stub.calls == [PRO_A_FILE]           # no native call for B
    native_stub(pro_a, KEY).close()                     # same Pro: fine
    assert native_stub.calls == [PRO_A_FILE, PRO_A_FILE]


def test_engine_refuses_rekeyed_pro_context_and_keyless_pro(
        tmp_path, native_stub):
    pro_a = write_model(tmp_path, PRO_A_FILE, PRO_A_UUID, False)
    with pytest.raises(KrokoNativeConflict) as caught:
        native_stub(pro_a, "")
    assert caught.value.code == PRO_KEY_REQUIRED
    assert native_stub.calls == []
    native_stub(pro_a, KEY).close()
    with pytest.raises(KrokoNativeConflict) as caught:
        native_stub(pro_a, OTHER_KEY)
    assert caught.value.code == KEY_CONTEXT_CHANGE
    assert native_stub.calls == [PRO_A_FILE]


def test_engine_allows_community_around_pro_but_only_one_instance(
        tmp_path, native_stub):
    community = write_model(tmp_path, COMMUNITY_FILE, COMMUNITY_UUID, True)
    pro_a = write_model(tmp_path, PRO_A_FILE, PRO_A_UUID, False)
    native_stub(community).close()                      # Community, no key
    native_stub(pro_a, KEY).close()                     # Community -> Pro
    live = native_stub(community)                       # Pro -> Community
    with pytest.raises(KrokoNativeConflict) as caught:
        native_stub(community)                          # second copy
    assert caught.value.code == CONCURRENT_IDENTITY
    live.close()
    assert process_guard().status()["liveNativeInstances"] == 0
    native_stub(community).close()


def test_engine_releases_the_lease_when_the_native_load_fails(
        tmp_path, monkeypatch, native_stub):
    import numpy as np
    from VoiceSTT.transcription_engines import (
        TranscriptionEngineConfig, kroko_onnx_engine)

    class Broken:
        @classmethod
        def from_transducer(cls, **_kwargs):
            raise RuntimeError("synthetic native failure")

    monkeypatch.setattr(
        kroko_onnx_engine, "_load_online_recognizer_class", lambda: Broken)
    community = write_model(tmp_path, COMMUNITY_FILE, COMMUNITY_UUID, True)
    with pytest.raises(RuntimeError, match="synthetic native failure"):
        kroko_onnx_engine.KrokoOnnxBackend(
            TranscriptionEngineConfig(model=str(community)), numpy_module=np)
    assert process_guard().status()["liveNativeInstances"] == 0


# -- the native license context is the evidence once Pro runs in this process ---

def test_native_pro_context_keeps_entitlement_without_a_provider_recheck(
        tmp_path, monkeypatch, fake_license, ledger):
    """Observed: the provider rejects an external check for a key whose native
    reporter is alive. A confirmed native context for the same model and key
    therefore stands in for the (unrenewable) 60 s proof - and a rejected
    recheck must never demote the working Pro instance."""
    service, _root = build_service(tmp_path, monkeypatch, model=PRO_A_ID)
    service.refresh_stt_models()
    calls = list(fake_license.calls)
    fake_license.allowed = False                 # provider now says no
    service.security.kroko.state.bind(key="", force_community=False)  # proof gone

    decision = service.refresh_kroko_license_policy()[0]
    assert decision["tier"] == "pro"
    assert decision["reason"] == "native_license_context"
    service.refresh_stt_models()                 # e.g. an admin refresh
    assert fake_license.calls == calls           # no pointless provider contact
    assert set(active_ids(service).values()) == {PRO_A_ID}
    assert service._submit_scheduler_job(job(), "t").accepted is True
    runtime = service.kroko_runtime_status()
    assert runtime["licenseEntitled"] is True
    assert runtime["licenseSource"] == "native_context"


def test_native_context_never_covers_other_model_other_key_or_force(
        tmp_path, monkeypatch, fake_license, ledger):
    service, root = build_service(tmp_path, monkeypatch, model=PRO_A_ID)
    service.refresh_stt_models()
    fake_license.allowed = False
    service.security.kroko.state.bind(key="", force_community=False)
    other = service._kroko_license_entitlement(
        products()[2], str(root / PRO_B_FILE))
    assert other[0] is False                     # other Pro model
    patch_force(service, True)
    forced = service._kroko_license_entitlement(
        products()[1], str(root / PRO_A_FILE))
    assert forced == (False, "force_community")  # force always wins
    assert service.refresh_kroko_license_policy()[0]["tier"] == "community"


def test_pro_again_after_force_release_uses_the_native_context(
        tmp_path, monkeypatch, fake_license, ledger):
    service, _root = build_service(tmp_path, monkeypatch, model=PRO_A_ID)
    service.refresh_stt_models()
    patch_force(service, True)
    service.apply_kroko_force_change()
    assert wait_for(lambda: service._kroko_reconcile_state is not None)
    assert set(active_ids(service).values()) == {COMMUNITY_ID}
    calls = list(fake_license.calls)
    previous = service._kroko_reconcile_state["at"]

    fake_license.allowed = False                 # a recheck would be rejected
    patch_force(service, False)
    service.apply_kroko_force_change()
    assert wait_for(lambda: service._kroko_reconcile_state["at"] != previous)

    assert service._kroko_reconcile_state["result"] == "changed"
    assert set(active_ids(service).values()) == {PRO_A_ID}
    assert fake_license.calls == calls
    assert ledger.peak == 1


def test_guard_native_license_confirmation_is_model_and_key_bound():
    guard = KrokoNativeGuard()
    pro = ident("pro", "aaaaaaaa-0000-0000-0000-000000000001")
    lease = guard.acquire(pro, KEY)
    assert guard.native_license_confirmed(pro.ident, KEY) is False   # not yet
    guard.confirm_loaded(lease)
    assert guard.native_license_confirmed(pro.ident, KEY) is True
    assert guard.native_license_confirmed(pro.ident.upper(), KEY) is True
    assert guard.native_license_confirmed(pro.ident, OTHER_KEY) is False
    assert guard.native_license_confirmed(pro.ident, "") is False
    assert guard.native_license_confirmed("other", KEY) is False
    community_lease = None
    guard.release(lease)
    community_lease = guard.acquire(ident("community", "c"), "")
    guard.confirm_loaded(community_lease)         # Community never confirms Pro
    guard.reset_for_tests()
    assert guard.native_license_confirmed(pro.ident, KEY) is False


def test_engine_confirms_the_native_license_context_only_after_a_successful_load(
        tmp_path, monkeypatch, native_stub):
    import numpy as np
    from VoiceSTT.transcription_engines import (
        TranscriptionEngineConfig, kroko_onnx_engine)

    pro_a = write_model(tmp_path, PRO_A_FILE, PRO_A_UUID, False)
    guard = process_guard()
    native_stub(pro_a, KEY)
    assert guard.native_license_confirmed(PRO_A_UUID, KEY) is True

    guard.reset_for_tests()

    class Broken:
        @classmethod
        def from_transducer(cls, **_kwargs):
            raise RuntimeError("synthetic native failure")

    monkeypatch.setattr(
        kroko_onnx_engine, "_load_online_recognizer_class", lambda: Broken)
    with pytest.raises(RuntimeError):
        kroko_onnx_engine.KrokoOnnxBackend(
            TranscriptionEngineConfig(
                model=str(pro_a), engine_options={"key": KEY}),
            numpy_module=np)
    # The failed Pro load keeps the (conservative) Pro identity bound, but it
    # proves nothing about the license.
    assert guard.status()["nativeProContextActive"] is True
    assert guard.native_license_confirmed(PRO_A_UUID, KEY) is False
