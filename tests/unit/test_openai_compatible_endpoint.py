import io
import json
import threading
import time
import wave

import numpy as np
import pytest
from fastapi.testclient import TestClient

from api_fastapi_server.server import (
    InferenceResult,
    QueueSubmitResult,
    ServerSettings,
    create_app,
    enforce_cpu_model_policy,
)
from VoiceSTT_server.openai_compat import OpenAIRequestError, parse_transcription_form


def wav_bytes(seconds=0.15):
    output = io.BytesIO()
    samples = np.zeros(int(16000 * seconds), dtype=np.int16)
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(samples.tobytes())
    return output.getvalue()


class MultiForm(dict):
    def __init__(self, pairs):
        super().__init__()
        self.pairs = list(pairs)
        for key, value in self.pairs:
            self[key] = value

    def getlist(self, name):
        return [value for key, value in self.pairs if key == name]


class ImmediateScheduler:
    def __init__(self, settings, result_callback, drop_callback=None, error_callback=None):
        self.settings = settings
        self.result_callback = result_callback
        self.jobs = []

    def start(self):
        pass

    def stop(self):
        pass

    def wait_ready(self, timeout=None):
        return True

    def healthy(self):
        return True

    def submit(self, job):
        self.jobs.append(job)
        callback = (job.request_options or {}).get("stream_callback")
        detail = {
            "id": 0, "seek": 0, "start": 0.0, "end": 0.15, "text": "hello world",
            "tokens": [1, 2], "temperature": 0.0, "avg_logprob": -0.1,
            "compression_ratio": 1.0, "no_speech_prob": 0.0,
            "words": [{"word": "hello", "start": 0.0, "end": 0.08, "probability": 0.9}],
        }
        if callback:
            callback("hello world", detail)
        now = time.monotonic()
        self.result_callback(InferenceResult(
            request_id=job.request_id,
            session_id=job.session_id,
            kind=job.kind,
            segment_id=job.segment_id,
            sequence=job.sequence,
            generation=job.generation,
            text="hello world",
            error=None,
            created_at=job.created_at,
            started_at=now,
            completed_at=now,
            queue_delay=0.0,
            inference_duration=0.0,
            total_latency=0.0,
            details={"duration": 0.15, "segments": [detail], "words": detail["words"]},
        ))
        return QueueSubmitResult(True)

    def cancel_session(self, session_id):
        pass

    def snapshot(self):
        return {"jobs": len(self.jobs)}


def test_parser_accepts_every_official_form_parameter():
    form = MultiForm([
        ("model", "whisper-1"),
        ("language", "en"),
        ("prompt", "names and spelling"),
        ("response_format", "diarized_json"),
        ("temperature", "0.2"),
        ("stream", "true"),
        ("include[]", "logprobs"),
        ("threshold", "0.7"),
        ("known_speaker_names[]", "Marco"),
        ("known_speaker_references[]", "data:audio/wav;base64,AAAA"),
    ])
    request = parse_transcription_form(form)
    assert request.model == "whisper-1"
    assert request.stream is True
    assert request.include == ["logprobs"]
    assert request.known_speaker_references == ["data:audio/wav;base64,AAAA"]


def test_parser_validates_word_timestamps_require_verbose_json():
    with pytest.raises(OpenAIRequestError, match="verbose_json"):
        parse_transcription_form(MultiForm([
            ("model", "whisper-1"),
            ("timestamp_granularities[]", "word"),
        ]))


def test_endpoint_supports_json_text_verbose_srt_vtt_and_diarized():
    app = create_app(ServerSettings(model_warmup=False), scheduler_factory=ImmediateScheduler)
    with TestClient(app) as client:
        for response_format in ("json", "text", "verbose_json", "srt", "vtt", "diarized_json"):
            data = {"model": "whisper-1", "response_format": response_format}
            if response_format == "verbose_json":
                data["timestamp_granularities[]"] = "word"
            response = client.post(
                "/v1/audio/transcriptions",
                data=data,
                files={"file": ("sample.wav", wav_bytes(), "audio/wav")},
            )
            assert response.status_code == 200, response.text
            assert "hello" in response.text


def test_endpoint_streams_openai_sse_events():
    app = create_app(ServerSettings(model_warmup=False), scheduler_factory=ImmediateScheduler)
    with TestClient(app) as client:
        response = client.post(
            "/v1/audio/transcriptions",
            data={"model": "whisper-1", "stream": "true"},
            files={"file": ("sample.wav", wav_bytes(), "audio/wav")},
        )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert '"type":"transcript.text.delta"' in response.text
    assert '"type":"transcript.text.done"' in response.text


def test_endpoint_routes_two_models_and_handles_parallel_requests():
    settings = ServerSettings(model="small", realtime_model="tiny", model_warmup=False)
    app = create_app(settings, scheduler_factory=ImmediateScheduler)
    statuses = []
    with TestClient(app) as client:
        def request_model(model):
            response = client.post(
                "/v1/audio/transcriptions",
                data={"model": model},
                files={"file": ("sample.wav", wav_bytes(), "audio/wav")},
            )
            statuses.append(response.status_code)

        threads = [threading.Thread(target=request_model, args=(model,)) for model in ("small", "tiny")]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
    assert statuses == [200, 200]


def test_endpoint_optional_bearer_auth():
    app = create_app(
        ServerSettings(model_warmup=False, openai_api_key="secret"),
        scheduler_factory=ImmediateScheduler,
    )
    with TestClient(app) as client:
        response = client.post(
            "/v1/audio/transcriptions",
            data={"model": "whisper-1"},
            files={"file": ("sample.wav", wav_bytes(), "audio/wav")},
        )
        assert response.status_code == 401
        response = client.post(
            "/v1/audio/transcriptions",
            headers={"Authorization": "Bearer secret"},
            data={"model": "whisper-1"},
            files={"file": ("sample.wav", wav_bytes(), "audio/wav")},
        )
        assert response.status_code == 200


def test_cpu_policy_reuses_same_model_and_rejects_large_plus_tiny():
    same = ServerSettings(
        model="medium",
        realtime_model="medium",
        realtime_transcription_engine="faster_whisper",
    )
    enforce_cpu_model_policy(same)
    assert same.use_main_model_for_realtime is True

    with pytest.raises(ValueError, match="CPU-Modellrichtlinie"):
        enforce_cpu_model_policy(ServerSettings(model="large-v3", realtime_model="tiny"))


def test_cpu_policy_allows_two_medium_equivalents_and_counts_standard_turbo_as_medium():
    two_medium = ServerSettings(
        model="medium",
        realtime_model="medium.en",
        realtime_transcription_engine="faster_whisper",
    )
    enforce_cpu_model_policy(two_medium)
    assert two_medium.use_main_model_for_realtime is False

    turbo_and_medium = ServerSettings(
        model="large-v3-turbo",
        realtime_model="medium",
        realtime_transcription_engine="faster_whisper",
    )
    enforce_cpu_model_policy(turbo_and_medium)

    with pytest.raises(ValueError, match="CPU-Modellrichtlinie"):
        enforce_cpu_model_policy(ServerSettings(
            model="large-v3-turbo-german",
            realtime_model="tiny",
            realtime_transcription_engine="faster_whisper",
        ))

    legacy_limit = ServerSettings(
        model="medium",
        realtime_model="medium.en",
        realtime_transcription_engine="faster_whisper",
        allow_two_medium_models=False,
    )
    with pytest.raises(ValueError, match="CPU-Modellrichtlinie"):
        enforce_cpu_model_policy(legacy_limit)

    disabled = ServerSettings(
        model="large-v3",
        realtime_model="large-v3",
        realtime_transcription_engine="faster_whisper",
        model_memory_policy_enabled=False,
    )
    enforce_cpu_model_policy(disabled)


def test_server_defaults_are_german_and_use_the_small_cpu_model_pair():
    settings = ServerSettings()
    assert settings.model == "small"
    assert settings.language == "de"
    assert settings.realtime_transcription_engine == "kroko_onnx"
    assert settings.realtime_model == "Kroko-DE-Community-64-L-Streaming-001.data"
    enforce_cpu_model_policy(settings)


def test_whisper_alias_accepts_explicit_header_and_form_model_overrides():
    settings = ServerSettings(model="small", realtime_model="tiny", model_warmup=False)
    app = create_app(settings, scheduler_factory=ImmediateScheduler)
    with TestClient(app) as client:
        header_response = client.post(
            "/v1/audio/transcriptions",
            headers={"X-VoiceSTT-Model": "tiny"},
            data={"model": "whisper-1"},
            files={"file": ("sample.wav", wav_bytes(), "audio/wav")},
        )
        form_response = client.post(
            "/v1/audio/transcriptions",
            data={"model": "whisper-1", "voicestt_model": "small"},
            files={"file": ("sample.wav", wav_bytes(), "audio/wav")},
        )

    assert header_response.status_code == 200
    assert header_response.headers["x-voicestt-resolved-model"] == "tiny"
    assert header_response.headers["x-voicestt-route"] == "realtime"
    assert header_response.headers["x-voicestt-override-source"] == "header.x-voicestt-model"
    assert form_response.status_code == 200
    assert form_response.headers["x-voicestt-resolved-model"] == "small"
    assert form_response.headers["x-voicestt-route"] == "final"


def test_override_is_rejected_unless_official_model_is_whisper_one():
    settings = ServerSettings(model="small", realtime_model="tiny", model_warmup=False)
    app = create_app(settings, scheduler_factory=ImmediateScheduler)
    with TestClient(app) as client:
        response = client.post(
            "/v1/audio/transcriptions",
            headers={"X-VoiceSTT-Model": "tiny"},
            data={"model": "small"},
            files={"file": ("sample.wav", wav_bytes(), "audio/wav")},
        )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_model_override"


def test_admin_api_requires_key_and_typed_endpoints_persist(tmp_path, monkeypatch):
    runtime_path = tmp_path / "runtime.json"
    wake_root = tmp_path / "wakewords"
    wake_root.mkdir()
    (wake_root / "hey_jarvis_v0.1.onnx").write_bytes(b"wake")
    monkeypatch.setenv("VOICESTT_OPENWAKEWORD_MODEL_ROOT", str(wake_root))
    settings = ServerSettings(
        model_warmup=False,
        admin_api_key="admin-secret",
        runtime_config_path=str(runtime_path),
        request_logging_enabled=False,
    )
    app = create_app(settings, scheduler_factory=ImmediateScheduler)
    headers = {"X-VoiceSTT-Admin-Key": "admin-secret"}
    with TestClient(app) as client:
        assert client.get("/api/models").status_code == 401
        assert client.patch("/api/config", json={"beam_size": 3}).status_code == 401
        assert client.get("/api/models", headers=headers).status_code == 200
        assert client.put("/api/language", headers=headers, json={"language": "de"}).status_code == 200
        wake = client.put("/api/wake-word", headers=headers, json={
            "enabled": True, "backend": "openwakeword", "words": "hey_jarvis",
            "sensitivity": 0.6,
        })
        assert wake.status_code == 200
        wake_config = client.get("/api/wake-word", headers=headers).json()
        assert wake_config["availableModels"]["openwakeword"][0]["id"] == "hey_jarvis"
        assert set(wake_config["availableModels"]) == {"openwakeword"}
        logging_response = client.put("/api/logging", headers=headers, json={
            "enabled": True, "stdout": False, "transcripts": False,
            "file": str(tmp_path / "audit.jsonl"),
            "performanceEnabled": True,
            "performanceStdout": False,
            "performanceFile": str(tmp_path / "performance.jsonl"),
        })
        assert logging_response.status_code == 200
        logging_config = client.get("/api/logging", headers=headers).json()
        assert logging_config["performance"]["enabled"] is True
        assert logging_config["performance"]["file"].endswith("performance.jsonl")

    persisted = json.loads(runtime_path.read_text(encoding="utf-8"))["settings"]
    assert persisted["language"] == "de"
    assert persisted["wakeword_backend"] == "openwakeword"
    assert persisted["request_log_transcripts"] is False
    assert persisted["performance_logging_enabled"] is True
    assert "admin_api_key" not in persisted


def test_model_lifecycle_api_unloads_and_lazy_reloads_for_real_request_flow():
    settings = ServerSettings(model_warmup=False, request_logging_enabled=False)
    app = create_app(settings, scheduler_factory=ImmediateScheduler)
    with TestClient(app) as client:
        initial = client.get("/api/models/lifecycle")
        assert initial.status_code == 200
        assert initial.json()["loaded"] is True

        unloaded = client.post("/api/models/unload")
        assert unloaded.status_code == 200, unloaded.text
        assert unloaded.json()["lifecycle"]["loaded"] is False
        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["ok"] is True
        assert health.json()["models"]["state"] == "unloaded"

        response = client.post(
            "/v1/audio/transcriptions",
            data={"model": "whisper-1"},
            files={"file": ("sample.wav", wav_bytes(), "audio/wav")},
        )
        assert response.status_code == 200, response.text
        reloaded = client.get("/api/models/lifecycle").json()
        assert reloaded["loaded"] is True
        assert reloaded["state"] == "loaded"


def test_model_lifecycle_configuration_and_ui_controls_are_exposed():
    settings = ServerSettings(model_warmup=False, request_logging_enabled=False)
    app = create_app(settings, scheduler_factory=ImmediateScheduler)
    with TestClient(app) as client:
        configured = client.put("/api/models/lifecycle", json={
            "automaticUnloadEnabled": True,
            "idleTimeoutSeconds": 120,
            "memoryPolicyEnabled": True,
            "allowTwoMediumModels": True,
        })
        html = client.get("/").text

    assert configured.status_code == 200, configured.text
    assert configured.json()["idleTimeoutSeconds"] == 120
    assert configured.json()["mediumEquivalentLimit"] == 2
    assert 'id="modelsUnload"' in html
    assert 'id="modelIdleUnload"' in html
    assert 'id="allowTwoMediumModels"' in html
    assert '<select id="wakeWords"' in html
    assert '<input id="wakeWords"' not in html
    assert "Servereinstellungen" in html
    assert "Keine verfügbaren Weckwort-Modelle" in html
    assert 'entry.engine === "faster_whisper"' not in html


def test_idle_timer_unloads_models_without_making_health_fail():
    settings = ServerSettings(
        model_warmup=False,
        request_logging_enabled=False,
        model_idle_unload_enabled=True,
        model_idle_timeout_seconds=0.2,
    )
    app = create_app(settings, scheduler_factory=ImmediateScheduler)
    with TestClient(app) as client:
        deadline = time.monotonic() + 2
        status = client.get("/api/models/lifecycle").json()
        while status["loaded"] and time.monotonic() < deadline:
            time.sleep(0.05)
            status = client.get("/api/models/lifecycle").json()
        health = client.get("/health").json()

    assert status["state"] == "unloaded"
    assert health["ok"] is True


def test_health_stays_responsive_while_lazy_model_load_is_in_progress():
    load_gate = threading.Event()

    class BlockingReloadScheduler(ImmediateScheduler):
        created = 0

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.instance_number = type(self).created
            type(self).created += 1

        def wait_ready(self, timeout=None):
            if self.instance_number == 0:
                return True
            return load_gate.wait(timeout=timeout)

    settings = ServerSettings(model_warmup=False, request_logging_enabled=False)
    app = create_app(settings, scheduler_factory=BlockingReloadScheduler)
    responses = []
    with TestClient(app) as client:
        assert client.post("/api/models/unload").status_code == 200

        request_thread = threading.Thread(target=lambda: responses.append(client.post(
            "/v1/audio/transcriptions",
            data={"model": "whisper-1"},
            files={"file": ("sample.wav", wav_bytes(), "audio/wav")},
        )))
        request_thread.start()
        deadline = time.monotonic() + 2
        lifecycle = client.get("/api/models/lifecycle").json()
        while lifecycle["state"] != "loading" and time.monotonic() < deadline:
            time.sleep(0.01)
            lifecycle = client.get("/api/models/lifecycle").json()

        started = time.monotonic()
        health = client.get("/health")
        health_latency = time.monotonic() - started
        load_gate.set()
        request_thread.join(timeout=3)

    assert lifecycle["state"] == "loading"
    assert health.status_code == 200
    assert health.json()["models"]["state"] == "loading"
    assert health_latency < 0.5
    assert responses and responses[0].status_code == 200


def test_openai_model_list_and_default_language_are_exposed():
    settings = ServerSettings(model="small", realtime_model="tiny", language="de", model_warmup=False)
    app = create_app(settings, scheduler_factory=ImmediateScheduler)
    with TestClient(app) as client:
        models = client.get("/v1/models")
        response = client.post(
            "/v1/audio/transcriptions",
            data={"model": "whisper-1"},
            files={"file": ("sample.wav", wav_bytes(), "audio/wav")},
        )

    assert models.status_code == 200
    assert any(item["id"] == "whisper-1" for item in models.json()["data"])
    assert response.status_code == 200
    assert app.state.voicestt_service.scheduler.jobs[-1].language == "de"


def test_structured_request_log_contains_completed_event(tmp_path):
    log_path = tmp_path / "requests.jsonl"
    settings = ServerSettings(
        model_warmup=False,
        request_logging_enabled=True,
        request_log_stdout=False,
        request_log_path=str(log_path),
    )
    app = create_app(settings, scheduler_factory=ImmediateScheduler)
    with TestClient(app) as client:
        response = client.post(
            "/v1/audio/transcriptions",
            data={"model": "whisper-1"},
            files={"file": ("sample.wav", wav_bytes(), "audio/wav")},
        )

    assert response.status_code == 200
    log_files = list((tmp_path / "requests").glob("*/*.jsonl"))
    assert len(log_files) == 1
    events = [
        json.loads(line)
        for line in log_files[0].read_text(encoding="utf-8").splitlines()
    ]
    completed = next(event for event in events if event["event"] == "transcription.completed")
    assert completed["data"]["text"] == "hello world"
    assert completed["data"]["language"] == "de"
    assert completed["requestId"] == response.headers["x-request-id"]


def test_log_history_api_returns_unified_http_transcription_events(tmp_path):
    settings = ServerSettings(
        model_warmup=False,
        request_log_stdout=False,
        request_log_path=str(tmp_path / "audit"),
        performance_log_stdout=False,
        performance_log_path=str(tmp_path / "performance"),
        transcription_log_path=str(tmp_path / "transcription"),
        system_event_log_path=str(tmp_path / "system"),
        event_store_path=str(tmp_path / "events.sqlite3"),
    )
    app = create_app(settings, scheduler_factory=ImmediateScheduler)
    with TestClient(app) as client:
        response = client.post(
            "/v1/audio/transcriptions",
            data={"model": "whisper-1"},
            files={"file": ("sample.wav", wav_bytes(), "audio/wav")},
        )
        request_id = response.headers["x-request-id"]
        history = client.get(
            "/api/logs/events",
            params={
                "sessionId": request_id,
                "channels": "transcription,performance",
            },
        )

    assert history.status_code == 200
    events = history.json()["data"]
    names = {event["event"] for event in events}
    assert "transcription.started" in names
    assert "transcription.completed" in names
    assert all(event["sessionId"] == request_id for event in events)
    assert all(event["transport"] == "http" for event in events)


def test_model_switch_uses_only_mounted_models_and_reloads_workers(tmp_path, monkeypatch):
    faster_root = tmp_path / "ctranslate2"
    for name in ("small", "tiny"):
        folder = faster_root / f"models--Systran--faster-whisper-{name}"
        folder.mkdir(parents=True)
        (folder / "config.json").write_text("{}", encoding="utf-8")
        (folder / "model.bin").write_bytes(b"model")
    (faster_root / "stt_models.json").write_text(json.dumps({
        "stt": {"models": {
            "small": "models--Systran--faster-whisper-small",
            "tiny": "models--Systran--faster-whisper-tiny",
        }}
    }), encoding="utf-8")
    monkeypatch.setenv("VOICESTT_FASTER_WHISPER_MODEL_ROOT", str(faster_root))

    settings = ServerSettings(
        model="small", realtime_model="small",
        realtime_transcription_engine="faster_whisper",
        model_warmup=False, admin_api_key="secret",
    )
    app = create_app(settings, scheduler_factory=ImmediateScheduler)
    headers = {"X-VoiceSTT-Admin-Key": "secret"}
    with TestClient(app) as client:
        response = client.put("/api/models/active", headers=headers, json={
            "model": "tiny",
            "transcription_engine": "faster_whisper",
            "realtime_model": "small",
            "realtime_transcription_engine": "faster_whisper",
        })
        missing = client.put("/api/models/active", headers=headers, json={
            "model": "does-not-exist",
        })

    assert response.status_code == 200, response.text
    assert response.json()["reloaded"] is True
    assert response.json()["active"]["final"]["model"] == "tiny"
    assert missing.status_code == 400
    assert "eingebundenen lokalen Modellregistrierung" in missing.json()["error"]
