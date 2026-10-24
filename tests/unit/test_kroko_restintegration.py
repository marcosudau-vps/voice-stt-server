"""Synthetic license/native fixtures and real local owner processes; no live keys."""
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from types import SimpleNamespace
from unittest import mock

import pytest

from VoiceSTT.kroko import license_runtime as license
from VoiceSTT.kroko import owner_process as owner
from VoiceSTT.kroko import supervisor as supervision
from VoiceSTT.kroko.native_status import NativeStatusVerifier
from tests.unit.test_kroko_unified_runtime import (
    isolated_env, ManualClock, ScriptedVerifier, PRO_ID, PRO_FILE, COMMUNITY_FILE,
)


def authority():
    clock = ManualClock()
    result = license.LicenseRuntimeAuthority(time_fn=clock)
    result.note_intent(key_present=True, force_community=False,
                       credential_revision="opaque", runtime_identity="payload:one",
                       requested_model_ids=(PRO_ID,), owner_generation="5")
    return result, clock


def native_reply(**updates):
    reply = dict(schemaVersion=1, ownerGeneration="5", modelId="native-model-uuid",
                 outcome="granted", proofAgeSeconds=2.0, maxProofAgeSeconds=10.0)
    reply.update(updates)
    return reply


@pytest.mark.parametrize("updates", [
    {"schemaVersion": 2}, {"schemaVersion": True}, {"ownerGeneration": "4"},
    {"modelId": "another-model"}, {"outcome": "unknown"},
    {"proofAgeSeconds": -1}, {"proofAgeSeconds": 10},
    {"proofAgeSeconds": float("nan")}, {"maxProofAgeSeconds": float("inf")},
    {"maxProofAgeSeconds": 61}, {"maxProofAgeSeconds": 0},
    {"proofAgeSeconds": "0"}, {"proofAgeSeconds": False},
])
def test_native_adapter_fails_closed_for_unqualified_snapshot(updates):
    state, _ = authority()
    verifier = NativeStatusVerifier(lambda: native_reply(**updates), {"native-model-uuid": PRO_ID})
    assert state.run_check(verifier, (PRO_ID,)) == license.LicenseStatus.CHECK_FAILED
    assert not state.pro_enabled_global()


def test_native_adapter_exact_model_owner_and_residual_ttl():
    state, clock = authority()
    verifier = NativeStatusVerifier(lambda: json.dumps(native_reply()), {"native-model-uuid": PRO_ID})
    assert state.run_check(verifier, (PRO_ID,)) == license.LicenseStatus.VALID
    assert state.pro_enabled_for(PRO_ID)
    assert not state.pro_enabled_for("another-id")
    assert state.public_snapshot()["maxProofAgeSeconds"] == 8
    clock.advance(8)
    assert not state.pro_enabled_global()


@pytest.mark.parametrize("outcome,expected", [("rejected", "INVALID"), ("unreachable", "CHECK_FAILED")])
def test_native_rejection_is_distinct_from_technical_failure(outcome, expected):
    state, _ = authority()
    verifier = NativeStatusVerifier(lambda: native_reply(outcome=outcome), {"native-model-uuid": PRO_ID})
    assert state.run_check(verifier, (PRO_ID,)).value == expected


def test_verifier_exception_and_reason_never_expose_raw_data():
    state, _ = authority()
    class Broken(license.LicenseVerifier):
        def verify(self, request):
            raise RuntimeError("private-key-and-provider-response")
    assert state.run_check(Broken(), (PRO_ID,)) == license.LicenseStatus.CHECK_FAILED
    state.begin_check()
    state.record_failure("private-key-and-provider-response")
    assert "private-key" not in repr(state.public_snapshot())


def test_parallel_checks_and_old_results_cannot_reauthorize_new_generation():
    state, _ = authority()
    entered, release = threading.Event(), threading.Event()
    class Slow(license.LicenseVerifier):
        def verify(self, request):
            entered.set()
            assert release.wait(5)
            return license.LicenseVerdict("granted", (PRO_ID,), 10)
    worker = threading.Thread(target=state.run_check, args=(Slow(), (PRO_ID,)))
    worker.start()
    assert entered.wait(5)
    second = ScriptedVerifier(license.LicenseVerdict("rejected"))
    assert state.run_check(second, (PRO_ID,)) == license.LicenseStatus.CHECKING
    assert second.requests == []
    state.note_intent(key_present=True, force_community=False, credential_revision="new",
                      runtime_identity="payload:one", requested_model_ids=("other",), owner_generation="6")
    fresh = ScriptedVerifier(license.LicenseVerdict("granted", ("other",), 10))
    state.run_check(fresh, ("other",))
    snapshot = state.public_snapshot()
    release.set()
    worker.join(5)
    assert not worker.is_alive()
    assert state.public_snapshot() == snapshot
    assert not state.pro_enabled_for(PRO_ID)
    assert state.pro_enabled_for("other")


@pytest.mark.parametrize("changed", [{"requested_model_ids": ("other",)}, {"owner_generation": "6"}])
def test_model_and_owner_change_invalidate_success(changed):
    state, _ = authority()
    state.run_check(ScriptedVerifier(license.LicenseVerdict("granted", (PRO_ID,), 10)), (PRO_ID,))
    intent = dict(key_present=True, force_community=False, credential_revision="opaque",
                  runtime_identity="payload:one", requested_model_ids=(PRO_ID,), owner_generation="5")
    intent.update(changed)
    assert state.note_intent(**intent)
    assert not state.pro_enabled_global()


@pytest.mark.parametrize("ttl", [float("nan"), float("inf"), 0, -1, 61])
def test_authority_refuses_unbounded_or_invalid_ttl(ttl):
    state, _ = authority()
    state.run_check(ScriptedVerifier(license.LicenseVerdict("granted", (PRO_ID,), ttl)), (PRO_ID,))
    assert not state.pro_enabled_global()


def test_verifier_cannot_grant_unrequested_rights():
    state, _ = authority()
    state.run_check(ScriptedVerifier(license.LicenseVerdict("granted", ("other",), 10)), (PRO_ID,))
    assert state.status == license.LicenseStatus.CHECK_FAILED


def test_stopped_or_dead_process_events_are_rejected():
    guard = supervision.OwnerSupervisor(backoff_base_seconds=0)
    spec = supervision.OwnerSpec([sys.executable, "-c", "import time; time.sleep(30)"])
    handle = guard.start(spec, config={})
    try:
        handle.process.kill()
        handle.process.wait(5)
        assert guard.accept_event(handle.generation, "late") is None
        assert not guard.is_current(handle.generation)
    finally:
        guard.stop()
    assert guard.accept_event(handle.generation, "stopped") is None
    assert supervision.OwnerSupervisor().accept_event(0, "never started") is None


def test_concurrent_starts_confirm_previous_real_exit():
    processes = []
    def spawn(*args, **kwargs):
        assert all(process.poll() is not None for process in processes)
        process = subprocess.Popen(*args, **kwargs)
        processes.append(process)
        return process
    guard = supervision.OwnerSupervisor(popen_factory=spawn, backoff_base_seconds=0)
    barrier = threading.Barrier(3)
    errors = []
    def start():
        try:
            barrier.wait(5)
            guard.start(supervision.OwnerSpec([sys.executable, "-c", "import time; time.sleep(30)"]), config={})
        except Exception as exc:
            errors.append(exc)
    workers = [threading.Thread(target=start) for _ in range(2)]
    try:
        for worker in workers:
            worker.start()
        barrier.wait(5)
        for worker in workers:
            worker.join(10)
        assert not errors
        assert len(processes) == 2
        assert processes[0].poll() is not None
        assert processes[1].poll() is None
    finally:
        guard.stop()


# A real child owns an OS lock (released even by terminate/os._exit). If the
# launcher overlaps owners, the next child cannot acquire it and exits 77.
CHILD = r'''import json, os, pathlib, sys, time
from VoiceSTT.kroko.owner_process import publish
mode, root = sys.argv[1:]
root = pathlib.Path(root)
lock = (root / "native-owner.lock").open("a+b")
lock.write(b"x"); lock.flush(); lock.seek(0)
try:
    if os.name == "nt":
        import msvcrt
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
except OSError:
    sys.exit(77)
fallback = os.environ.get("VOICESTT_KROKO_COMMUNITY_FALLBACK") == "1"
with (root / "starts.jsonl").open("a") as stream:
    stream.write(json.dumps({"pid": os.getpid(), "fallback": fallback,
                            "generation": os.environ["VOICESTT_KROKO_OWNER_GENERATION"]}) + "\n")
if not fallback:
    if mode == "crash":
        os._exit(9)
    if mode == "timeout":
        time.sleep(30)
    if mode == "stale":
        control = pathlib.Path(os.environ["VOICESTT_KROKO_OWNER_CONTROL"])
        (control / "ready.json").write_text(json.dumps({"generation": "0", "event": "ready"}))
        time.sleep(30)
    if mode == "loss":
        publish("ready"); publish("community"); time.sleep(30)
publish("ready")
time.sleep(0.15)
'''


@pytest.mark.parametrize("scenario", ["crash", "timeout", "stale", "loss"])
def test_real_owner_timeout_exit_stale_and_license_loss_fallback(tmp_path, scenario):
    class Tracking(supervision.OwnerSupervisor):
        def __init__(self):
            super().__init__(backoff_base_seconds=0)
            self.handles = []
        def start(self, *args, **kwargs):
            handle = super().start(*args, **kwargs)
            self.handles.append(handle)
            return handle
    guard = Tracking()
    with isolated_env():
        result = owner.supervise([], owner_argv=[sys.executable, "-c", CHILD, scenario, str(tmp_path)],
                                 start_timeout=2, poll_interval=0.01, supervisor=guard, max_transitions=3, graceful_shutdown=0.2)
    assert result == 0
    starts = [json.loads(line) for line in (tmp_path / "starts.jsonl").read_text().splitlines()]
    assert len(starts) == 2
    assert [row["fallback"] for row in starts] == [False, True]
    assert starts[0]["pid"] != starts[1]["pid"]
    assert all(handle.process.poll() is not None for handle in guard.handles)


def test_supervisor_spawn_error_redacts_environment_and_arguments():
    def broken(*args, **kwargs):
        raise OSError("secret-token-in-command")
    guard = supervision.OwnerSupervisor(popen_factory=broken)
    with pytest.raises(supervision.SupervisorError) as error:
        guard.start(supervision.OwnerSpec(["secret-token-in-command"]), config={})
    assert "secret-token" not in str(error.value)


def test_server_model_intent_and_effective_key_cascade():
    from tests.unit.test_kroko_unified_runtime import ServerLicenseGateTests
    helper = ServerLicenseGateTests()
    helper.setUp()
    stub = helper.make_stub(transcription_engine_options={"key": "lane-key"})
    with isolated_env({"KROKO_API_KEY": "unused-env-key"}):
        helper.intent(stub)
        generation = stub.kroko_license.generation
        revision = stub.kroko_license.public_snapshot()["credentialRevision"]
        with mock.patch.dict(os.environ, {"KROKO_API_KEY": "changed-unused-key"}):
            helper.intent(stub)
        assert stub.kroko_license.generation == generation
        assert stub.kroko_license.public_snapshot()["credentialRevision"] == revision
        stub.settings.model = "other.data"
        helper.intent(stub)
        assert stub.kroko_license.generation == generation + 1


def test_pending_handoff_drops_results_and_disallows_new_loads():
    from api_fastapi_server.server import VoiceSTTService
    stub = SimpleNamespace(_kroko_transition=threading.Event(), _kroko_native_candidate=False)
    stub._kroko_transition.set()
    assert VoiceSTTService._on_inference_result(stub, object()) is None
    with pytest.raises(RuntimeError, match="neu gestartet"):
        VoiceSTTService.ensure_models_loaded(stub)


def test_unconfirmed_exit_retains_handle_and_never_spawns_second_owner():
    process = mock.Mock()
    process.poll.return_value = None
    process.wait.side_effect = subprocess.TimeoutExpired("synthetic", 1)
    spawn = mock.Mock(return_value=process)
    guard = supervision.OwnerSupervisor(popen_factory=spawn, backoff_base_seconds=0)
    guard.start(supervision.OwnerSpec(["stub"]), config={})
    for _ in range(2):
        with pytest.raises(supervision.UnconfirmedExit):
            guard.start(supervision.OwnerSpec(["stub"]), config={})
    assert spawn.call_count == 1


def test_server_force_and_model_admin_paths_request_process_restart(tmp_path):
    from api_fastapi_server.server import ServerSettings, create_app
    from tests.unit.test_openai_compatible_endpoint import ImmediateScheduler
    settings = ServerSettings(data_root_path=str(tmp_path), model=COMMUNITY_FILE,
                              realtime_model=COMMUNITY_FILE)
    with isolated_env():
        app = create_app(settings, scheduler_factory=ImmediateScheduler)
        service = app.state.voicestt_service
        try:
            env = {owner.CONTROL_ENV: str(tmp_path), supervision.OWNER_GENERATION_ENV: "7"}
            with mock.patch.dict(os.environ, env):
                with mock.patch.object(service.stt_model_manager, "refresh", side_effect=AssertionError("must not probe old owner")):
                    result = service.switch_models({"model": "Kroko-EN-Community-64-L-Streaming-001.data"})
                assert result["changed"]
                assert service._kroko_transition.is_set()
                assert owner.read_event(tmp_path, "restart", 7)
                persisted = service.config_store.load()
                assert persisted["model"] == "Kroko-EN-Community-64-L-Streaming-001.data"
                assert "license" not in persisted
                service._kroko_transition.clear()
                service.update_settings({"kroko_force_community": True})
                assert service._kroko_transition.is_set()
                assert service.config_store.load()["kroko_force_community"] is True
        finally:
            service.stop()


def test_startup_fallback_does_not_persist_derived_community_selection(tmp_path):
    from api_fastapi_server.server import ServerSettings, create_app
    from tests.unit.test_openai_compatible_endpoint import ImmediateScheduler
    helper_module = __import__("tests.unit.test_kroko_unified_runtime", fromlist=["ServerLicenseGateTests"])
    helper = helper_module.ServerLicenseGateTests(); helper.setUp()
    stub = helper.make_stub()
    manifest = stub._kroko_manifest_cached()
    settings = ServerSettings(data_root_path=str(tmp_path), model=PRO_FILE, realtime_model=PRO_FILE,
                              transcription_engine="kroko_onnx", realtime_transcription_engine="kroko_onnx")
    with isolated_env(), mock.patch("api_fastapi_server.server.kroko_model_authority.load_manifest", return_value=manifest):
        app = create_app(settings, scheduler_factory=ImmediateScheduler)
        service = app.state.voicestt_service
        try:
            assert settings.model == COMMUNITY_FILE
            service.update_settings({"max_sessions": 3})
            assert service.config_store.load()["model"] == PRO_FILE
            with mock.patch.dict(os.environ, {owner.CONTROL_ENV: str(tmp_path), supervision.OWNER_GENERATION_ENV: "8"}):
                service.switch_models({"language": "en"})
            assert service.config_store.load()["model"] == PRO_FILE
        finally:
            service.stop()


ASGI_CHILD = r'''import os, sys, threading
from api_fastapi_server import server
from tests.unit.test_openai_compatible_endpoint import ImmediateScheduler
original = server.create_app
def create(settings):
    app = original(settings, scheduler_factory=ImmediateScheduler)
    @app.get("/fixture/pid")
    async def pid():
        return {"pid": os.getpid()}
    @app.post("/fixture/finish")
    async def finish():
        threading.Timer(0.2, lambda: os._exit(0)).start()
        return {"ok": True}
    return app
server.create_app = create
raise SystemExit(server.main(["--host", "127.0.0.1", "--port", sys.argv[1], "--data-root", sys.argv[2]]))
'''


def test_real_asgi_owner_model_restart_and_http_readiness(tmp_path):
    import socket
    import urllib.request
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0)); port = sock.getsockname()[1]
    result = []
    guard = supervision.OwnerSupervisor(backoff_base_seconds=0)
    def run():
        result.append(owner.supervise([], owner_argv=[sys.executable, "-c", ASGI_CHILD, str(port), str(tmp_path)],
                                      supervisor=guard, start_timeout=15, poll_interval=0.01, max_transitions=3))
    def request(path, data=None):
        body = None if data is None else json.dumps(data).encode()
        req = urllib.request.Request("http://127.0.0.1:" + str(port) + path, data=body,
                                     headers={"Content-Type": "application/json"},
                                     method="PUT" if path == "/api/models/active" else ("POST" if data is not None else "GET"))
        with urllib.request.urlopen(req, timeout=2) as response:
            return json.load(response)
    def wait_pid(previous=None):
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            try:
                pid = request("/fixture/pid")["pid"]
                if pid != previous:
                    return pid
            except (OSError, ValueError):
                pass
            time.sleep(0.05)
        pytest.fail("ASGI owner did not become reachable")
    with isolated_env():
        worker = threading.Thread(target=run)
        worker.start()
        try:
            first = wait_pid()
            assert "license" in request("/api/models/lifecycle")
            changed = request("/api/models/active", {"model": "Kroko-EN-Community-64-L-Streaming-001.data"})
            assert changed["changed"]
            second = wait_pid(first)
            assert first != second
            request("/fixture/finish", {})
            worker.join(20)
            assert not worker.is_alive()
            assert result == [0]
        finally:
            guard.stop()
            worker.join(20)


@pytest.mark.parametrize("change", ["key", "owner", "model"])
def test_old_native_snapshot_cannot_follow_key_owner_or_model_rotation(tmp_path, change):
    from api_fastapi_server.server import ServerSettings, create_app
    from tests.unit.test_openai_compatible_endpoint import ImmediateScheduler
    settings = ServerSettings(data_root_path=str(tmp_path), transcription_engine="kroko_onnx",
                              model=COMMUNITY_FILE, realtime_model=COMMUNITY_FILE)
    with isolated_env({"KROKO_API_KEY": "synthetic-original-key"}):
        service = create_app(settings, scheduler_factory=ImmediateScheduler).state.voicestt_service
        try:
            if change == "key":
                os.environ["KROKO_API_KEY"] = "synthetic-rotated-key"
            elif change == "owner":
                os.environ[supervision.OWNER_GENERATION_ENV] = "another-owner"
            else:
                settings.model = "another-model.data"
            with mock.patch("api_fastapi_server.server.loaded_snapshot_reader", side_effect=AssertionError("old native must not regrant")):
                assert service._check_native_license() is False
        finally:
            service.stop()


def test_native_patch_rejects_undeclared_sources_before_mutation(tmp_path):
    from VoiceSTT.kroko.native_status_patch import patch_native_license_status
    source = tmp_path / "sherpa-onnx/csrc/license.h"
    source.parent.mkdir(parents=True)
    source.write_text("source drift", encoding="utf-8")
    with pytest.raises(RuntimeError, match="declared source"):
        patch_native_license_status(tmp_path)
    assert source.read_text() == "source drift"


def test_community_bootstrap_requires_an_explicit_free_root_before_import(tmp_path):
    from VoiceSTT.kroko import bootstrap
    with pytest.raises(bootstrap.BootstrapConflictError, match="Community payload"):
        bootstrap.ensure_bootstrap_from_env(
            community_only=True, _environ={bootstrap.PAYLOAD_ROOT_ENV: str(tmp_path)})


def test_native_model_probe_becomes_serving_scheduler_without_second_load(tmp_path):
    import hashlib
    from api_fastapi_server.server import VoiceSTTService, ServerSettings
    model = tmp_path / PRO_FILE
    model.write_bytes(b"synthetic-native-model")
    entry = SimpleNamespace(id=PRO_ID, sha256=hashlib.sha256(model.read_bytes()).hexdigest())
    candidate = SimpleNamespace(engine="kroko_onnx", path=str(model))
    scheduler = mock.Mock()
    scheduler.wait_ready.return_value = True
    scheduler.healthy.return_value = True
    stub = SimpleNamespace(
        _kroko_native_candidate=True, _kroko_probe_attempted=False,
        _kroko_preloaded_scheduler=None, settings=ServerSettings(),
        _kroko_manifest_cached=lambda: SimpleNamespace(get=lambda _value: entry),
        _kroko_pro_entries=lambda: ([{"id": PRO_ID}], []),
        scheduler_factory=mock.Mock(return_value=scheduler),
        _on_inference_result=mock.Mock(), _on_scheduler_drop=mock.Mock(),
        _on_scheduler_error=mock.Mock(),
    )
    assert VoiceSTTService._probe_stt_model(stub, candidate)
    assert not VoiceSTTService._probe_stt_model(stub, candidate)
    assert VoiceSTTService._new_scheduler(stub) is scheduler
    assert scheduler._kroko_already_started is True
    assert stub._kroko_preloaded_scheduler is None
    scheduler.start.assert_called_once()
    scheduler.stop.assert_not_called()


def test_direct_asgi_native_force_change_is_rejected_before_mutation(tmp_path):
    from api_fastapi_server.server import ServerSettings, create_app
    from tests.unit.test_openai_compatible_endpoint import ImmediateScheduler
    with isolated_env():
        settings = ServerSettings(data_root_path=str(tmp_path))
        service = create_app(settings, scheduler_factory=ImmediateScheduler).state.voicestt_service
        try:
            with mock.patch.dict(sys.modules, {"_sherpa_onnx": SimpleNamespace()}):
                result = service.update_settings({"kroko_force_community": True})
            assert "kroko_force_community" in result["rejected"]
            assert settings.kroko_force_community is False
        finally:
            service.stop()


def test_slow_verifier_does_not_extend_original_proof_window():
    state, clock = authority()
    class Slow(license.LicenseVerifier):
        def verify(self, request):
            clock.advance(9)
            return license.LicenseVerdict("granted", (PRO_ID,), 10)
    state.run_check(Slow(), (PRO_ID,))
    assert state.public_snapshot()["maxProofAgeSeconds"] == 1
    clock.advance(1)
    assert not state.pro_enabled_global()


def test_shared_recognizer_ignores_unused_realtime_credential():
    from api_fastapi_server.server import ServerSettings, kroko_effective_credentials
    settings = ServerSettings(transcription_engine="kroko_onnx", realtime_transcription_engine="kroko_onnx",
                              use_main_model_for_realtime=True, transcription_engine_options={},
                              realtime_transcription_engine_options={"key": "unused-synthetic-key"})
    with isolated_env():
        assert kroko_effective_credentials(settings) == (False, "none")
        settings.transcription_engine_options = {"key": "active-synthetic-key"}
        before = kroko_effective_credentials(settings)
        settings.realtime_transcription_engine_options = {"key": "another-unused-key"}
        assert kroko_effective_credentials(settings) == before
