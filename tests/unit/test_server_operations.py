import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from VoiceSTT_server.operations import (
    AuditLogManager,
    LocalModelRegistry,
    PerformanceLogManager,
    RuntimeConfigStore,
    WakeWordRegistry,
    process_memory_snapshot,
)


def make_ctranslate_model(root, folder):
    model = root / folder
    model.mkdir(parents=True)
    (model / "config.json").write_text("{}", encoding="utf-8")
    (model / "model.bin").write_bytes(b"model")
    return model


def test_local_model_registry_discovers_aliases_and_kroko(tmp_path):
    faster = tmp_path / "ctranslate2"
    kroko = tmp_path / "kroko"
    faster.mkdir()
    kroko.mkdir()
    model = make_ctranslate_model(faster, "models--Systran--faster-whisper-small")
    (faster / "stt_models.json").write_text(json.dumps({
        "stt": {"models": {"small": model.name}}
    }), encoding="utf-8")
    kroko_model = kroko / "Kroko-DE-Community-64-L-Streaming-001.data"
    kroko_model.write_bytes(b"kroko")

    registry = LocalModelRegistry(faster, kroko)
    entries = registry.list_models()

    assert {(entry["engine"], entry["id"]) for entry in entries} == {
        ("faster_whisper", "small"),
        ("kroko_onnx", kroko_model.name),
    }
    assert registry.resolve("small")["path"] == str(model.resolve())
    assert registry.resolve(model.name)["id"] == "small"
    assert "small" in registry.aliases_for("faster-whisper", model.name)


def test_wakeword_registry_discovers_models_and_ignores_support_files(tmp_path):
    (tmp_path / "hey_jarvis_v0.1.onnx").write_bytes(b"wake")
    (tmp_path / "hey_jarvis_v0.1.tflite").write_bytes(b"wake")
    (tmp_path / "embedding_model.onnx").write_bytes(b"support")
    (tmp_path / "melspectrogram.onnx").write_bytes(b"support")
    registry = WakeWordRegistry(tmp_path)

    models = registry.openwakeword_models(framework="onnx")

    assert len(models) == 1
    assert models[0]["id"] == "hey_jarvis"
    assert models[0]["label"] == "Hey Jarvis"
    assert models[0]["path"].endswith("hey_jarvis_v0.1.onnx")
    assert models[0]["availableFormats"] == ["onnx", "tflite"]


@dataclass
class LogSettings:
    request_logging_enabled: bool = True
    request_log_stdout: bool = False
    request_log_path: str = ""
    request_log_transcripts: bool = True
    request_log_max_bytes: int = 1024 * 1024
    request_log_backup_count: int = 2
    save_audio_files: bool = True
    audio_log_dir: str = ""
    performance_logging_enabled: bool = True
    performance_log_stdout: bool = False
    performance_log_path: str = ""
    performance_log_max_bytes: int = 1024 * 1024
    performance_log_backup_count: int = 2


def test_audit_logger_writes_json_and_archives_audio(tmp_path):
    settings = LogSettings(
        request_log_path=str(tmp_path / "requests.jsonl"),
        audio_log_dir=str(tmp_path / "audio"),
    )
    audit = AuditLogManager(settings)
    audit.event("transcription.completed", requestId="abc", text="Hallo Welt")
    archive = audit.archive_audio(b"RIFF", "sample.wav", "abc")

    payload = json.loads((tmp_path / "requests.jsonl").read_text(encoding="utf-8").strip())
    assert payload["event"] == "transcription.completed"
    assert payload["meldung"] == "Transkription abgeschlossen"
    assert payload["text"] == "Hallo Welt"
    assert payload["timestamp"].endswith("Z")
    assert archive.endswith(".wav")
    assert list((tmp_path / "audio").glob("*/*"))

    settings.request_log_transcripts = False
    settings.save_audio_files = False
    audit.configure(settings)
    audit.event("transcription.completed", text="secret")
    last = json.loads((tmp_path / "requests.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert "text" not in last
    audit.close()


def test_performance_logger_uses_separate_jsonl_channel(tmp_path):
    settings = LogSettings(
        save_audio_files=False,
        performance_log_path=str(tmp_path / "performance.jsonl"),
    )
    performance = PerformanceLogManager(settings)
    performance.event(
        "inference.completed",
        model="small",
        queueDelayMs=12.5,
        realTimeFactor=0.4,
    )
    performance.close()

    payload = json.loads((tmp_path / "performance.jsonl").read_text(encoding="utf-8"))
    assert payload["channel"] == "performance"
    assert payload["event"] == "inference.completed"
    assert payload["meldung"] == "Inferenz abgeschlossen"
    assert payload["queueDelayMs"] == 12.5
    assert payload["realTimeFactor"] == 0.4
    assert payload["timestamp"].endswith("Z")


def test_process_memory_snapshot_reports_nonnegative_byte_counters():
    snapshot = process_memory_snapshot()

    assert snapshot
    assert snapshot["rssBytes"] > 0
    assert all(value is None or value >= 0 for value in snapshot.values())

    with ThreadPoolExecutor(max_workers=8) as pool:
        concurrent = list(pool.map(lambda _: process_memory_snapshot(), range(32)))
    assert all(item.get("rssBytes", 0) > 0 for item in concurrent)


@dataclass
class RuntimeSettings:
    language: str = "de"
    model: str = "small"
    secret: str = "do-not-write"


def test_runtime_config_store_persists_only_allowlisted_values(tmp_path):
    path = tmp_path / "runtime.json"
    store = RuntimeConfigStore(path)
    resolved = store.save(RuntimeSettings(), {"language", "model"})

    assert resolved == str(path.resolve())
    assert store.load() == {"language": "de", "model": "small"}
    assert "secret" not in path.read_text(encoding="utf-8")
