"""Isolated child process for the opt-in native Kroko integration tests.

Not a test module (no ``test_`` prefix). ``test_kroko_native_integration.py``
starts one fresh interpreter per scenario so the native Kroko license
singleton never leaks between scenarios, and so a native hang can be killed
without taking the test run with it. Output is one redacted JSON line per
scenario (``RESULT {...}``); the key is read from a local file at runtime and
is never printed, logged or passed on a command line.

Deliberately absent: any Pro-model-A -> Pro-model-B scenario. That transition
crashes or hangs the native runtime and is blocked by the process guard.
"""
import faulthandler
import json
import os
import sys
import tempfile
import threading
import time
import wave

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO)

import numpy as np  # noqa: E402

faulthandler.dump_traceback_later(int(os.getenv("VOICESTT_KROKO_NATIVE_CHILD_TIMEOUT", "900")), exit=True)

COMMUNITY_FILE = "Kroko-DE-Community-64-L-Streaming-001.data"
PRO_FILE = "Kroko-DE-Pro-16-L-Streaming-001.data"
COMMUNITY_ID = "kroko-de-community-64-l"
PRO_ID = "kroko-de-pro-16-l"
KEY_NAMES = (
    "KROKO_ASR_API_KEY", "KROKO_ASR_API_KEY_SECOND", "KROKO_API_KEY",
    "KROKO_ONNX_KEY", "VOICESTT_KROKO_ONNX_KEY", "KROKO_KEY",
)
MODEL_DIR = os.environ["KROKO_NATIVE_MODEL_DIR"]
AUDIO = os.environ["KROKO_NATIVE_AUDIO"]
EXPECT = [
    word.strip().lower()
    for word in os.environ.get("KROKO_NATIVE_EXPECT", "guten,test").split(",")
    if word.strip()
]


def load_key():
    path = os.environ["KROKO_NATIVE_KEY_FILE"]
    values = {}
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle.read().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, _, value = line.partition("=")
            values[name.strip()] = value.strip().strip("'\"")
    for name in KEY_NAMES:
        if values.get(name):
            return values[name]
    raise SystemExit("no Kroko key variable in the key file")


def audio():
    with wave.open(AUDIO, "rb") as handle:
        assert handle.getframerate() == 16000 and handle.getnchannels() == 1
        raw = handle.readframes(handle.getnframes())
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


def hits(text):
    return [word for word in EXPECT if word in (text or "").lower()]


def emit(**fields):
    print("RESULT " + json.dumps(fields, ensure_ascii=False), flush=True)


def guard_status():
    from VoiceSTT.kroko.native_guard import process_guard
    return process_guard().status()


def engine_options(key=None, **extra):
    options = {
        "provider": "cpu", "num_threads": 1, "suppress_native_output": True,
    }
    if key is not None:
        options["key"] = key
    options.update(extra)
    return options


def scenario_community_no_key():
    from VoiceSTT.transcription_engines import TranscriptionEngineConfig
    from VoiceSTT.transcription_engines.kroko_onnx_engine import KrokoOnnxBackend

    # The explicit empty nested key suppresses any environment key.
    backend = KrokoOnnxBackend(TranscriptionEngineConfig(
        model=os.path.join(MODEL_DIR, COMMUNITY_FILE),
        engine_options=engine_options(recognizer={"key": ""}),
    ))
    text = backend.transcribe(audio(), language="de").text
    emit(scenario="community_no_key", loaded=True, text=text, hits=hits(text),
         guard=guard_status())
    backend.close()


def scenario_pro_with_key():
    from VoiceSTT.transcription_engines import TranscriptionEngineConfig
    from VoiceSTT.transcription_engines.kroko_onnx_engine import KrokoOnnxBackend

    backend = KrokoOnnxBackend(TranscriptionEngineConfig(
        model=os.path.join(MODEL_DIR, PRO_FILE),
        engine_options=engine_options(load_key()),
    ))
    text = backend.transcribe(audio(), language="de").text
    emit(scenario="pro_with_key", loaded=True, text=text, hits=hits(text),
         guard=guard_status())
    backend.close()


def _server_settings(key, model_id, resolved_file):
    from api_fastapi_server.server import ServerSettings

    settings = ServerSettings(
        data_root_path=tempfile.mkdtemp(prefix="kroko-native-"),
        model_warmup=False,
        model_idle_unload_enabled=False,
    )
    settings.transcription_engine = "kroko_onnx"
    settings.realtime_transcription_engine = "kroko_onnx"
    settings.model = model_id
    settings.realtime_model = model_id
    settings.use_main_model_for_realtime = True
    settings.transcription_engine_options = engine_options(
        key, runtime_variant="pro", model_dir=MODEL_DIR)
    if resolved_file:
        settings._resolved_stt_models = {
            role: {
                "id": model_id, "engine": "kroko_onnx",
                "path": os.path.join(MODEL_DIR, resolved_file),
            }
            for role in ("final", "realtime")
        }
    return settings


def scenario_pro_shared_final_realtime():
    """The real scheduler: final and realtime lanes on ONE Pro instance."""
    from api_fastapi_server.server import InferenceJob, InferenceScheduler

    settings = _server_settings(load_key(), PRO_ID, PRO_FILE)
    results, errors = {}, []
    arrived = threading.Condition()

    def on_result(result):
        with arrived:
            results[result.kind] = result
            arrived.notify_all()

    scheduler = InferenceScheduler(
        settings, on_result, None, lambda name, exc: errors.append(str(exc)))
    scheduler.start()
    try:
        ready = scheduler.wait_ready(timeout=420) and scheduler.healthy()
        samples = audio()
        for kind in ("final", "realtime"):
            scheduler.submit(InferenceJob(
                request_id=kind, session_id="native-" + kind, kind=kind,
                audio=samples, language="de", use_prompt=False, segment_id=0,
                sequence=0, generation=0, created_at=time.monotonic(),
                request_options={}, client_id=None))
        with arrived:
            arrived.wait_for(lambda: len(results) == 2, timeout=180)
        emit(
            scenario="pro_shared_final_realtime", ready=bool(ready),
            sharedInstance=scheduler.realtime_worker is None,
            texts={kind: res.text for kind, res in results.items()},
            hits={kind: hits(res.text) for kind, res in results.items()},
            errors=errors, guard=guard_status())
    finally:
        scheduler.stop()


def _runtime(service):
    status = service.kroko_runtime_status()
    return {
        key: status[key] for key in (
            "licenseEntitled", "licenseSource", "activeKrokoModels", "activeProPresent",
            "nativeProContextActive", "restartRequired", "proAdmissionRevoked",
            "modelRefreshPending", "liveNativeInstances")
    }


def scenario_service_community_pro_switch():
    """Productive Community <-> Pro transitions over the existing server path."""
    from fastapi.testclient import TestClient
    from api_fastapi_server import settings_control as sc
    from api_fastapi_server.server import create_app

    key = load_key()
    settings = _server_settings(key, COMMUNITY_ID, None)
    app = create_app(settings)
    service = app.state.voicestt_service
    steps = []
    samples = audio()

    def transcribe(lane):
        result = service.transcribe_openai(lane, samples, language="de",
                                           timeout=180)
        return result.text

    def record(name, **fields):
        snapshot = service.security.kroko.state.public_snapshot()
        fields.update(step=name, runtime=_runtime(service),
                      license={k: snapshot[k] for k in (
                          "status", "reasonCode", "keyPresent",
                          "forceCommunity", "proEnabled")},
                      active={r: v["id"] for r, v in
                              service.settings._resolved_stt_models.items()})
        steps.append(fields)

    def wait_reconcile(previous):
        deadline = time.monotonic() + 600
        while time.monotonic() < deadline:
            state = service._kroko_reconcile_state
            if state is not None and state.get("at") != previous:
                return state
            time.sleep(0.2)
        raise SystemExit("reconcile did not finish")

    with TestClient(app):
        assert service.ready.wait(420), "models not ready"
        text = transcribe("final")
        record("community_start", text=text, hits=hits(text))

        # Community -> Pro through the regular operator switch path.
        service.switch_models({
            "model": PRO_ID, "realtime_model": PRO_ID,
            "use_main_model_for_realtime": True,
        }, timeout=420)
        final_text = transcribe("final")
        realtime_text = transcribe("realtime")
        record("switched_to_pro", final=final_text, realtime=realtime_text,
               hits=hits(final_text) + hits(realtime_text))

        # Force Community: lock-out first, then the Pro -> Community switch.
        previous = (service._kroko_reconcile_state or {}).get("at")
        control = service.settings_control
        control.patch_server(control.settings_revision,
                             {sc.KROKO_FORCE_COMMUNITY: True})
        service.apply_kroko_force_change()
        refused = service._kroko_pro_revocation()
        record("force_community_locked", refusedImmediately=refused is not None)
        state = wait_reconcile(previous)
        text = transcribe("final")
        record("force_community_done", reconcile=state.get("result"),
               text=text, hits=hits(text))

        # Release force: new check, then Community -> same Pro again.
        previous = state.get("at")
        control.patch_server(control.settings_revision,
                             {sc.KROKO_FORCE_COMMUNITY: False})
        service.apply_kroko_force_change()
        state = wait_reconcile(previous)
        final_text = transcribe("final")
        realtime_text = transcribe("realtime")
        record("pro_again", reconcile=state.get("result"), final=final_text,
               realtime=realtime_text,
               hits=hits(final_text) + hits(realtime_text))
    emit(scenario="service_community_pro_switch", steps=steps)


SCENARIOS = {
    "community_no_key": scenario_community_no_key,
    "pro_with_key": scenario_pro_with_key,
    "pro_shared_final_realtime": scenario_pro_shared_final_realtime,
    "service_community_pro_switch": scenario_service_community_pro_switch,
}

if __name__ == "__main__":
    SCENARIOS[sys.argv[1]]()
