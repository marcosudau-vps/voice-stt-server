import json
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone

from VoiceSTT_server.operations import (
    AuditLogManager,
    LocalModelRegistry,
    PerformanceLogManager,
    RuntimeConfigStore,
    WakeWordRegistry,
    process_memory_snapshot,
)
from VoiceSTT_server.event_logging import (
    CalendarJsonlSink,
    SQLiteEventStore,
    StructuredEventHub,
    apply_process_log_level,
)
from VoiceSTT.core.initialization import _configure_logger


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


def test_wakeword_registry_prefers_models_json_and_resolves_default(tmp_path):
    model_root = tmp_path / "all_models"
    model_root.mkdir()
    for filename in (
        "alexa.onnx",
        "jarvis_v2.onnx",
        "embedding.custom.onnx",
        "melspectrogram.custom.onnx",
        "silero_vad.onnx",
    ):
        (model_root / filename).write_bytes(b"model")
    (tmp_path / "models.json").write_text(json.dumps({
        "openwakeword_models": {
            "path": str(model_root),
            "default_model": "alexa",
            "pipeline_models": {
                "embedding_model_onnx": "embedding.custom.onnx",
                "melspectrogram_onnx": "melspectrogram.custom.onnx",
            },
            "onnx_models": {
                "alexa": "alexa.onnx",
                "hey_jarvis": "jarvis_v2.onnx",
                "missing": "missing.onnx",
                "silero_vad": "silero_vad.onnx",
            },
            "tflite_models": {},
        }
    }), encoding="utf-8")

    registry = WakeWordRegistry(tmp_path)
    models = registry.openwakeword_models(framework="onnx")
    default, missing = registry.default_openwakeword(framework="onnx")
    selected, unavailable = registry.resolve_openwakeword(
        ["HEY_JARVIS"],
        framework="onnx",
    )

    assert [model["id"] for model in models] == ["alexa", "hey_jarvis"]
    assert models[0]["default"] is True
    assert all(model["source"] == "models.json" for model in models)
    assert default["id"] == "alexa"
    assert missing == []
    assert selected[0]["id"] == "hey_jarvis"
    assert selected[0]["path"] == str((model_root / "jarvis_v2.onnx").resolve())
    assert unavailable == []


@dataclass
class LogSettings:
    request_logging_enabled: bool = True
    request_log_stdout: bool = False
    request_log_path: str = ""
    request_log_transcripts: bool = True
    request_log_max_bytes: int = 1024 * 1024
    request_log_backup_count: int = 2
    request_log_retention_days: int = 0
    save_audio_files: bool = True
    audio_log_dir: str = ""
    performance_logging_enabled: bool = True
    performance_log_stdout: bool = False
    performance_log_path: str = ""
    performance_log_max_bytes: int = 1024 * 1024
    performance_log_backup_count: int = 2
    performance_log_retention_days: int = 0
    log_calendar_timezone: str = "Europe/Berlin"
    transcription_logging_enabled: bool = False
    transcription_log_stdout: bool = False
    transcription_log_path: str = ""
    transcription_log_max_bytes: int = 1024 * 1024
    transcription_log_backup_count: int = 2
    transcription_log_retention_days: int = 0
    system_event_logging_enabled: bool = False
    system_event_log_stdout: bool = False
    system_event_log_path: str = ""
    system_event_log_max_bytes: int = 1024 * 1024
    system_event_log_backup_count: int = 2
    system_event_log_retention_days: int = 0
    event_store_enabled: bool = False
    event_store_path: str = ""
    event_log_queue_size: int = 1000
    realtime_log_detail: str = "events"
    transcript_log_mode: str = "final"


def read_channel_events(root):
    paths = sorted(root.glob("*/*.jsonl"))
    assert paths
    return [
        json.loads(line)
        for path in paths
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def test_audit_logger_writes_json_and_archives_audio(tmp_path):
    settings = LogSettings(
        request_log_path=str(tmp_path / "requests.jsonl"),
        audio_log_dir=str(tmp_path / "audio"),
    )
    audit = AuditLogManager(settings)
    audit.event("transcription.completed", requestId="abc", text="Hallo Welt")
    archive = audit.archive_audio(b"RIFF", "sample.wav", "abc")

    payload = read_channel_events(tmp_path / "requests")[0]
    assert payload["schemaVersion"] == 1
    assert payload["channel"] == "audit"
    assert payload["event"] == "transcription.completed"
    assert payload["meldung"] == "Transkription abgeschlossen"
    # Transcript content belongs exclusively to the transcription channel.
    assert "text" not in payload["data"]
    assert payload["requestId"] == "abc"
    assert payload["timestamp"].endswith("Z")
    assert archive.endswith(".wav")
    assert list((tmp_path / "audio").glob("*/*"))

    settings.request_log_transcripts = False
    settings.save_audio_files = False
    audit.configure(settings)
    audit.event("transcription.completed", text="secret")
    last = read_channel_events(tmp_path / "requests")[-1]
    assert "text" not in last["data"]
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

    payload = read_channel_events(tmp_path / "performance")[0]
    assert payload["channel"] == "performance"
    assert payload["event"] == "inference.completed"
    assert payload["meldung"] == "Inferenz abgeschlossen"
    assert payload["data"]["queueDelayMs"] == 12.5
    assert payload["data"]["realTimeFactor"] == 0.4
    assert payload["timestamp"].endswith("Z")


def test_calendar_sink_creates_month_directories_and_daily_files(tmp_path):
    sink = CalendarJsonlSink(tmp_path / "audit", "Europe/Berlin")
    first = {
        "timestamp": "2026-07-30T12:00:00.000Z",
        "event": "first",
    }
    second = {
        "timestamp": "2026-08-01T12:00:00.000Z",
        "event": "second",
    }

    sink.write(first)
    sink.write(second)
    sink.close()

    assert (tmp_path / "audit" / "2026-07" / "2026-07-30.jsonl").is_file()
    assert (tmp_path / "audit" / "2026-08" / "2026-08-01.jsonl").is_file()


def test_calendar_sink_appends_after_restart_and_rolls_within_same_day(tmp_path):
    root = tmp_path / "audit"
    event = {
        "timestamp": "2026-07-30T12:00:00.000Z",
        "event": "entry",
        "data": {"value": "x" * 80},
    }
    first = CalendarJsonlSink(root, "Europe/Berlin", max_bytes=100)
    first.write(event)
    first.close()

    restarted = CalendarJsonlSink(root, "Europe/Berlin", max_bytes=100)
    restarted.write(event)
    restarted.close()

    day = root / "2026-07"
    assert (day / "2026-07-30.jsonl").is_file()
    assert (day / "2026-07-30.1.jsonl").is_file()
    assert sum(
        len(path.read_text(encoding="utf-8").splitlines())
        for path in day.glob("2026-07-30*.jsonl")
    ) == 2


def test_sqlite_event_store_filters_by_session_and_cursor(tmp_path):
    store = SQLiteEventStore(tmp_path / "events.sqlite3")
    common = {
        "schemaVersion": 1,
        "cursor": None,
        "timestamp": "2026-07-30T12:00:00.000Z",
        "channel": "transcription",
        "severity": "info",
        "serverInstanceId": "server",
        "transport": "websocket",
        "requestId": None,
        "transcriptionId": "tr-1",
        "segmentId": 1,
        "data": {},
    }
    first = dict(common, eventId="one", event="transcription.started", sessionId="a")
    second = dict(common, eventId="two", event="transcription.completed", sessionId="b")
    first_cursor = store.append(first)
    store.append(second)

    result = store.query(session_id="a", after_cursor=0)

    assert len(result) == 1
    assert result[0]["eventId"] == "one"
    assert result[0]["cursor"] == first_cursor
    store.close()


def test_sqlite_event_store_assigns_unique_monotonic_cursors_concurrently(tmp_path):
    store = SQLiteEventStore(tmp_path / "events.sqlite3")

    def append(sequence):
        return store.append({
            "schemaVersion": 1,
            "eventId": f"event-{sequence}",
            "timestamp": "2026-08-02T12:00:00.000Z",
            "channel": "system",
            "event": "concurrency.test",
            "severity": "info",
            "serverInstanceId": "server",
            "data": {"sequence": sequence},
        })

    with ThreadPoolExecutor(max_workers=8) as executor:
        cursors = list(executor.map(append, range(100)))

    assert sorted(cursors) == list(range(1, 101))
    assert store.oldest_cursor() == 1
    assert store.latest_cursor() == 100
    assert [event["cursor"] for event in store.query(limit=1000)] == list(
        range(1, 101)
    )
    store.close()


def test_event_hub_commits_before_notifying_and_queries_session_scope(tmp_path):
    settings = LogSettings(
        request_logging_enabled=False,
        performance_logging_enabled=False,
        transcription_logging_enabled=True,
        transcription_log_path=str(tmp_path / "transcription"),
        event_store_enabled=True,
        event_store_path=str(tmp_path / "events.sqlite3"),
    )
    hub = StructuredEventHub(settings)
    received = []
    subscription = hub.subscribe(
        received.append,
        channels={"transcription"},
        session_id="session-a",
    )

    hub.emit(
        "transcription",
        "transcription.completed",
        sessionId="session-a",
        transcriptionId="tr-a",
        text="Hallo",
    )
    hub.emit(
        "transcription",
        "transcription.completed",
        sessionId="session-b",
        transcriptionId="tr-b",
        text="Andere Sitzung",
    )
    hub.flush()

    history = hub.query(session_id="session-a")
    assert received == [
        {"_logControl": "commit", "cursor": 1},
        {"_logControl": "commit", "cursor": 2},
    ]
    assert len(history) == 1
    assert history[0]["data"]["text"] == "Hallo"
    hub.unsubscribe(subscription)
    hub.close()


def test_event_hub_redacts_secrets_audio_queries_and_transcripts_centrally(tmp_path):
    settings = LogSettings(
        request_log_path=str(tmp_path / "audit"),
        performance_log_path=str(tmp_path / "performance"),
        transcription_logging_enabled=True,
        transcription_log_path=str(tmp_path / "transcription"),
        event_store_enabled=True,
        event_store_path=str(tmp_path / "events.sqlite3"),
        transcript_log_mode="final",
    )
    hub = StructuredEventHub(settings)
    received = []
    subscription = hub.subscribe(received.append)

    hub.emit(
        "performance",
        "inference.completed",
        text="must not leak",
        audio=b"raw-audio",
        nested={
            "authorization": "Bearer secret-token",
            "access_token": "secret-token",
            "safe": "visible",
        },
        requestUrl="https://example.test/path?token=secret",
    )
    hub.emit(
        "transcription",
        "transcription.completed",
        text="final text",
        authorization="Bearer secret-token",
    )
    hub.flush()

    history = hub.query()
    performance = next(
        event for event in history if event["channel"] == "performance"
    )
    transcription = next(
        event for event in history if event["channel"] == "transcription"
    )
    assert "text" not in performance["data"]
    assert "audio" not in performance["data"]
    assert performance["data"]["nested"] == {"safe": "visible"}
    assert performance["data"]["requestUrl"] == "https://example.test/path"
    assert transcription["data"]["text"] == "final text"
    assert "authorization" not in transcription["data"]
    assert all("secret-token" not in json.dumps(event) for event in history)

    settings.transcript_log_mode = "none"
    hub.configure(settings)
    hub.emit(
        "transcription",
        "transcription.completed",
        text="disabled text",
    )
    hub.flush()
    assert "text" not in hub.query()[-1]["data"]

    settings.transcript_log_mode = "full"
    hub.configure(settings)
    hub.emit(
        "transcription",
        "transcription.realtime_emitted",
        text="realtime text",
    )
    hub.flush()
    assert hub.query()[-1]["data"]["text"] == "realtime text"
    hub.unsubscribe(subscription)
    hub.close()


def test_event_hub_cursor_remains_unique_after_store_write_failure(tmp_path):
    settings = LogSettings(
        request_log_stdout=False,
        request_log_path=str(tmp_path / "audit"),
        performance_logging_enabled=False,
        system_event_logging_enabled=True,
        system_event_log_path=str(tmp_path / "system"),
        event_store_enabled=True,
        event_store_path=str(tmp_path / "events.sqlite3"),
    )
    hub = StructuredEventHub(settings)
    received = []
    subscription = hub.subscribe(received.append)
    original_append = hub._store.append
    failed_once = False

    def fail_first_append(event):
        nonlocal failed_once
        if not failed_once:
            failed_once = True
            raise OSError("simulated store outage")
        return original_append(event)

    hub._store.append = fail_first_append
    failed_event_id = hub.emit("audit", "session.accepted", sessionId="a")
    hub.flush()
    assert failed_event_id is None
    assert hub.store_status()["state"] == "degraded"
    recovered_event_id = hub.emit("audit", "session.closed", sessionId="a")
    hub.flush()

    stored_cursors = [item["cursor"] for item in hub.query()]
    assert recovered_event_id is not None
    assert stored_cursors == [1]
    assert hub.latest_cursor() == 1
    assert hub.store_status()["state"] == "ready"
    assert any(
        item.get("_logControl") == "store_error"
        and item.get("code") == "event_store_unavailable"
        for item in received
    )
    assert any(item.get("_logControl") == "store_recovered" for item in received)
    assert {item.get("event") for item in hub.query()} == {"session.closed"}
    hub.unsubscribe(subscription)
    hub.close()


def test_event_hub_optional_mirror_overload_never_loses_committed_events(tmp_path):
    settings = LogSettings(
        request_logging_enabled=False,
        performance_log_path=str(tmp_path / "performance"),
        event_store_enabled=True,
        event_store_path=str(tmp_path / "events.sqlite3"),
        event_log_queue_size=1,
    )
    hub = StructuredEventHub(settings)
    received = []
    subscription = hub.subscribe(received.append)
    sink = hub._sinks["performance"]
    original_write = sink.write
    writer_entered = threading.Event()
    release_writer = threading.Event()
    first_write = True

    def slow_first_write(event):
        nonlocal first_write
        if first_write:
            first_write = False
            writer_entered.set()
            release_writer.wait(timeout=2)
        original_write(event)

    sink.write = slow_first_write
    hub.emit("performance", "inference.completed", sequence=0)
    assert writer_entered.wait(timeout=1)

    started = time.monotonic()
    for sequence in range(1, 100):
        hub.emit(
            "performance",
            "transcription.realtime_emitted",
            sequence=sequence,
        )
    elapsed = time.monotonic() - started
    release_writer.set()
    hub.flush()

    assert elapsed < 0.25
    assert hub.drop_counts().get("file", 0) > 0
    assert len(hub.query(limit=1000)) == 100
    assert not any(item.get("_logControl") == "gap" for item in received)
    hub.unsubscribe(subscription)
    hub.close()


def test_calendar_and_sqlite_retention_are_opt_in_and_channel_scoped(tmp_path):
    root = tmp_path / "audit"
    old_path = root / "2026-05" / "2026-05-01.jsonl"
    old_path.parent.mkdir(parents=True)
    old_path.write_text("{}\n", encoding="utf-8")
    disabled = CalendarJsonlSink(root, "Europe/Berlin", retention_days=0)
    disabled.write({"timestamp": "2026-07-31T12:00:00.000Z", "event": "keep"})
    disabled.close()
    assert old_path.is_file()

    enabled = CalendarJsonlSink(root, "Europe/Berlin", retention_days=30)
    enabled.write({"timestamp": "2026-08-01T12:00:00.000Z", "event": "prune"})
    enabled.close()
    assert not old_path.exists()

    store_path = tmp_path / "events.sqlite3"
    store = SQLiteEventStore(store_path)
    common = {
        "schemaVersion": 1,
        "cursor": None,
        "channel": "audit",
        "severity": "info",
        "serverInstanceId": "server",
        "transport": "http",
        "clientId": None,
        "sessionId": None,
        "requestId": None,
        "transcriptionId": None,
        "segmentId": None,
        "data": {},
    }
    store.append(dict(
        common,
        eventId="old",
        event="session.closed",
        timestamp="2020-01-01T00:00:00.000Z",
    ))
    store.close()

    reopened = SQLiteEventStore(store_path)
    reopened.set_retention({"audit": 30})
    new_cursor = reopened.append(dict(
        common,
        eventId="new",
        event="session.accepted",
        timestamp=datetime.now(timezone.utc).isoformat(
            timespec="milliseconds"
        ).replace("+00:00", "Z"),
    ))
    assert [event["eventId"] for event in reopened.query()] == ["new"]
    assert new_cursor > 1
    reopened.close()


def test_recorder_logger_configuration_is_idempotent_and_keeps_external_handlers():
    recorder_logger = logging.getLogger("voicestt")
    original_handlers = list(recorder_logger.handlers)
    external = logging.NullHandler()
    recorder_logger.addHandler(external)
    recorder = type("Recorder", (), {"level": logging.WARNING})()
    try:
        _configure_logger(recorder, True, {})
        _configure_logger(recorder, True, {})
        managed = [
            handler
            for handler in recorder_logger.handlers
            if getattr(handler, "_voicestt_console_handler", False)
        ]

        assert len(managed) == 1
        assert external in recorder_logger.handlers
        apply_process_log_level("DEBUG")
        assert managed[0].level == logging.DEBUG
    finally:
        for handler in list(recorder_logger.handlers):
            if handler not in original_handlers:
                recorder_logger.removeHandler(handler)


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
