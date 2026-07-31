"""Structured server event channels, persistence, and live subscriptions."""

from __future__ import annotations

import asyncio
import json
import logging
import queue
import sqlite3
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


CONTEXT_FIELDS = {
    "clientId",
    "requestId",
    "segmentId",
    "sessionId",
    "transcriptionId",
    "transport",
}


def utc_timestamp() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def resolve_calendar_timezone(name: str):
    """Resolve an IANA zone, with a Windows-local fallback for Europe/Berlin."""

    try:
        return ZoneInfo(str(name))
    except ZoneInfoNotFoundError as exc:
        if str(name) == "Europe/Berlin":
            local_timezone = datetime.now().astimezone().tzinfo
            if local_timezone is not None:
                return local_timezone
        raise ValueError(f"Unbekannte Logging-Zeitzone: {name}") from exc


def resolve_log_level(value: Any) -> int:
    name = str(value or "").strip().upper()
    level = logging.getLevelNamesMapping().get(name)
    if not isinstance(level, int):
        raise ValueError(f"Unbekanntes Log-Level: {value}")
    return level


def apply_process_log_level(value: Any) -> str:
    """Apply one validated level to the active application loggers."""

    level = resolve_log_level(value)
    name = logging.getLevelName(level)
    logging.getLogger().setLevel(level)
    for logger_name in (
        "voicestt.fastapi",
        "uvicorn",
        "uvicorn.access",
        "uvicorn.error",
    ):
        logging.getLogger(logger_name).setLevel(level)

    recorder_logger = logging.getLogger("voicestt")
    for handler in recorder_logger.handlers:
        if getattr(handler, "_voicestt_console_handler", False):
            handler.setLevel(level)
    return str(name)


def _calendar_root(configured: Optional[str], fallback: str) -> Optional[Path]:
    if configured in (None, ""):
        return None
    path = Path(configured or fallback).expanduser()
    if path.suffix.lower() in {".json", ".jsonl", ".log"}:
        path = path.parent / path.stem
    return path


class CalendarJsonlSink:
    """Write one JSONL file per local calendar day and channel."""

    def __init__(
        self,
        root: Path,
        timezone_name: str,
        max_bytes: int = 0,
        backup_count: int = 0,
    ):
        self.root = Path(root)
        self.timezone = resolve_calendar_timezone(timezone_name)
        self.max_bytes = max(0, int(max_bytes or 0))
        self.backup_count = max(0, int(backup_count or 0))
        self._lock = threading.RLock()
        self._day = None
        self._path = None
        self._stream = None

    def _day_for(self, timestamp: str):
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        return parsed.astimezone(self.timezone).date()

    def _base_path(self, day) -> Path:
        month_dir = self.root / day.strftime("%Y-%m")
        month_dir.mkdir(parents=True, exist_ok=True)
        return month_dir / f"{day.isoformat()}.jsonl"

    def _segment_path(self, base_path: Path) -> Path:
        if not base_path.exists() or not self.max_bytes:
            return base_path
        if base_path.stat().st_size < self.max_bytes:
            return base_path
        index = 1
        while True:
            candidate = base_path.with_name(
                f"{base_path.stem}.{index}{base_path.suffix}"
            )
            if not candidate.exists() or candidate.stat().st_size < self.max_bytes:
                return candidate
            index += 1

    def _ensure_stream(self, timestamp: str, line_bytes: int):
        day = self._day_for(timestamp)
        base_path = self._base_path(day)
        current_size = (
            self._path.stat().st_size
            if self._path is not None and self._path.exists()
            else 0
        )
        requires_size_rollover = (
            self.max_bytes
            and self._stream is not None
            and current_size > 0
            and current_size + line_bytes > self.max_bytes
        )
        if day == self._day and self._stream is not None and not requires_size_rollover:
            return
        self.close()
        self._day = day
        self._path = self._segment_path(base_path)
        self._stream = self._path.open("a", encoding="utf-8", newline="\n")

    def write(self, event: Dict[str, Any]):
        line = json.dumps(
            event,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        )
        encoded_size = len(line.encode("utf-8")) + 1
        with self._lock:
            self._ensure_stream(event["timestamp"], encoded_size)
            self._stream.write(line + "\n")
            self._stream.flush()

    @property
    def current_path(self) -> Optional[Path]:
        return self._path

    def close(self):
        with self._lock:
            if self._stream is not None:
                self._stream.close()
                self._stream = None


class SQLiteEventStore:
    """Small indexed append-only event store for history queries."""

    def __init__(self, path: Path):
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(
            self.path,
            check_same_thread=False,
            timeout=30.0,
        )
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA synchronous=NORMAL")
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                cursor INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL UNIQUE,
                timestamp TEXT NOT NULL,
                channel TEXT NOT NULL,
                event_name TEXT NOT NULL,
                severity TEXT NOT NULL,
                server_instance_id TEXT NOT NULL,
                transport TEXT,
                client_id TEXT,
                session_id TEXT,
                request_id TEXT,
                transcription_id TEXT,
                segment_id TEXT,
                payload_json TEXT NOT NULL
            )
            """
        )
        for name, column in (
            ("idx_events_timestamp", "timestamp"),
            ("idx_events_channel", "channel"),
            ("idx_events_event_name", "event_name"),
            ("idx_events_session_id", "session_id"),
            ("idx_events_client_id", "client_id"),
            ("idx_events_transcription_id", "transcription_id"),
        ):
            self._connection.execute(
                f"CREATE INDEX IF NOT EXISTS {name} ON events ({column})"
            )
        self._connection.commit()

    def append(self, event: Dict[str, Any]) -> int:
        with self._lock:
            cursor = self._connection.execute(
                """
                INSERT INTO events (
                    event_id, timestamp, channel, event_name, severity,
                    server_instance_id, transport, client_id, session_id,
                    request_id, transcription_id, segment_id, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event["eventId"],
                    event["timestamp"],
                    event["channel"],
                    event["event"],
                    event["severity"],
                    event["serverInstanceId"],
                    event.get("transport"),
                    event.get("clientId"),
                    event.get("sessionId"),
                    event.get("requestId"),
                    event.get("transcriptionId"),
                    (
                        str(event["segmentId"])
                        if event.get("segmentId") is not None
                        else None
                    ),
                    json.dumps(
                        event,
                        ensure_ascii=False,
                        separators=(",", ":"),
                        default=str,
                    ),
                ),
            ).lastrowid
            self._connection.commit()
            return int(cursor)

    def latest_cursor(self) -> int:
        with self._lock:
            row = self._connection.execute(
                "SELECT COALESCE(MAX(cursor), 0) FROM events"
            ).fetchone()
        return int(row[0])

    def query(
        self,
        *,
        channels: Optional[Iterable[str]] = None,
        events: Optional[Iterable[str]] = None,
        session_id: Optional[str] = None,
        transcription_id: Optional[str] = None,
        from_timestamp: Optional[str] = None,
        to_timestamp: Optional[str] = None,
        after_cursor: int = 0,
        until_cursor: Optional[int] = None,
        limit: int = 200,
    ):
        clauses = ["cursor > ?"]
        parameters = [max(0, int(after_cursor or 0))]
        if until_cursor is not None:
            clauses.append("cursor <= ?")
            parameters.append(max(0, int(until_cursor)))
        for values, column in ((channels, "channel"), (events, "event_name")):
            values = [str(value) for value in (values or []) if str(value)]
            if values:
                clauses.append(
                    f"{column} IN ({','.join('?' for _ in values)})"
                )
                parameters.extend(values)
        for value, column, operator in (
            (session_id, "session_id", "="),
            (transcription_id, "transcription_id", "="),
            (from_timestamp, "timestamp", ">="),
            (to_timestamp, "timestamp", "<="),
        ):
            if value not in (None, ""):
                clauses.append(f"{column} {operator} ?")
                parameters.append(str(value))
        limit = min(1000, max(1, int(limit or 200)))
        parameters.append(limit)
        sql = (
            "SELECT cursor, payload_json FROM events WHERE "
            + " AND ".join(clauses)
            + " ORDER BY cursor ASC LIMIT ?"
        )
        with self._lock:
            rows = self._connection.execute(sql, parameters).fetchall()
        result = []
        for cursor, payload_json in rows:
            payload = json.loads(payload_json)
            payload["cursor"] = int(cursor)
            result.append(payload)
        return result

    def close(self):
        with self._lock:
            self._connection.close()


class StructuredEventHub:
    """Normalize events once, then fan them out to configured sinks."""

    def __init__(self, settings):
        self.server_instance_id = uuid.uuid4().hex
        self._queue = queue.Queue(maxsize=max(
            100,
            int(getattr(settings, "event_log_queue_size", 10000)),
        ))
        self._settings_lock = threading.RLock()
        self._subscribers_lock = threading.RLock()
        self._subscribers: Dict[str, Dict[str, Any]] = {}
        self._fallback_cursor = 0
        self._dropped_events = 0
        self._closed = False
        self._store = None
        if bool(getattr(settings, "event_store_enabled", False)):
            store_path = getattr(
                settings,
                "event_store_path",
                "logs/voicestt-events.sqlite3",
            )
            if store_path:
                self._store = SQLiteEventStore(Path(store_path))
        self._channel_config = {}
        self._sinks: Dict[str, CalendarJsonlSink] = {}
        self.configure(settings)
        self._worker = threading.Thread(
            target=self._run,
            name="VoiceSTTStructuredEventWriter",
            daemon=True,
        )
        self._worker.start()

    def configure(self, settings):
        timezone_name = str(
            getattr(settings, "log_calendar_timezone", "Europe/Berlin")
        )
        definitions = {
            "audit": {
                "enabled": bool(getattr(settings, "request_logging_enabled", True)),
                "stdout": bool(getattr(settings, "request_log_stdout", True)),
                "path": getattr(settings, "request_log_path", "logs/audit"),
                "max_bytes": getattr(settings, "request_log_max_bytes", 0),
                "backup_count": getattr(settings, "request_log_backup_count", 0),
            },
            "performance": {
                "enabled": bool(
                    getattr(settings, "performance_logging_enabled", True)
                ),
                "stdout": bool(
                    getattr(settings, "performance_log_stdout", True)
                ),
                "path": getattr(
                    settings,
                    "performance_log_path",
                    "logs/performance",
                ),
                "max_bytes": getattr(settings, "performance_log_max_bytes", 0),
                "backup_count": getattr(
                    settings,
                    "performance_log_backup_count",
                    0,
                ),
            },
            "transcription": {
                "enabled": bool(
                    getattr(settings, "transcription_logging_enabled", True)
                ),
                "stdout": bool(
                    getattr(settings, "transcription_log_stdout", False)
                ),
                "path": getattr(
                    settings,
                    "transcription_log_path",
                    "logs/transcription",
                ),
                "max_bytes": getattr(settings, "transcription_log_max_bytes", 0),
                "backup_count": getattr(
                    settings,
                    "transcription_log_backup_count",
                    0,
                ),
            },
            "system": {
                "enabled": bool(
                    getattr(settings, "system_event_logging_enabled", True)
                ),
                "stdout": bool(
                    getattr(settings, "system_event_log_stdout", False)
                ),
                "path": getattr(
                    settings,
                    "system_event_log_path",
                    "logs/system",
                ),
                "max_bytes": getattr(settings, "system_event_log_max_bytes", 0),
                "backup_count": getattr(
                    settings,
                    "system_event_log_backup_count",
                    0,
                ),
            },
        }
        new_sinks = {}
        for channel, config in definitions.items():
            root = _calendar_root(config["path"], f"logs/{channel}")
            if config["enabled"] and root is not None:
                new_sinks[channel] = CalendarJsonlSink(
                    root,
                    timezone_name,
                    config["max_bytes"],
                    config["backup_count"],
                )
        with self._settings_lock:
            old_sinks = self._sinks
            self._sinks = new_sinks
            self._channel_config = definitions
            self.include_transcripts = bool(
                getattr(settings, "request_log_transcripts", True)
            )
            self.realtime_detail = str(
                getattr(settings, "realtime_log_detail", "events")
            ).strip().lower()
        for sink in old_sinks.values():
            sink.close()

    def emit(
        self,
        channel: str,
        event: str,
        *,
        message: Optional[str] = None,
        severity: str = "info",
        **fields,
    ) -> Optional[str]:
        with self._settings_lock:
            config = self._channel_config.get(channel)
            include_transcripts = self.include_transcripts
        if not config or not config["enabled"] or self._closed:
            return None
        context = {}
        for name in CONTEXT_FIELDS:
            if name in fields and fields[name] is not None:
                context[name] = fields.pop(name)
        if not include_transcripts:
            fields.pop("text", None)
        payload = {
            "schemaVersion": 1,
            "eventId": uuid.uuid4().hex,
            "cursor": None,
            "timestamp": utc_timestamp(),
            "channel": channel,
            "event": str(event),
            "severity": str(severity),
            "serverInstanceId": self.server_instance_id,
            **context,
            "data": {
                key: value
                for key, value in fields.items()
                if value is not None
            },
        }
        if message is not None:
            payload["meldung"] = message
        try:
            self._queue.put_nowait(payload)
        except queue.Full:
            if channel in {"audit", "transcription"}:
                try:
                    self._queue.put(payload, timeout=0.5)
                except queue.Full:
                    self._dropped_events += 1
                    return None
            else:
                self._dropped_events += 1
                return None
        return payload["eventId"]

    def _run(self):
        while True:
            payload = self._queue.get()
            try:
                if payload is None:
                    return
                try:
                    self._write(payload)
                except Exception:
                    logging.getLogger("voicestt.fastapi").exception(
                        "Strukturiertes Ereignis konnte nicht geschrieben werden"
                    )
            finally:
                self._queue.task_done()

    def _write(self, payload):
        if self._store is not None:
            try:
                cursor = self._store.append(payload)
            except Exception:
                logging.getLogger("voicestt.fastapi").exception(
                    "Event-Store konnte ein Ereignis nicht speichern"
                )
                self._fallback_cursor += 1
                cursor = self._fallback_cursor
        else:
            self._fallback_cursor += 1
            cursor = self._fallback_cursor
        payload["cursor"] = cursor
        channel = payload["channel"]
        with self._settings_lock:
            sink = self._sinks.get(channel)
            config = self._channel_config.get(channel, {})
            if sink is not None:
                try:
                    sink.write(payload)
                except Exception:
                    logging.getLogger("voicestt.fastapi").exception(
                        "Kalender-Logdatei konnte nicht geschrieben werden"
                    )
        if config.get("stdout"):
            print(
                json.dumps(
                    payload,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    default=str,
                ),
                file=sys.stdout,
                flush=True,
            )
        self._publish(payload)

    def _publish(self, payload):
        with self._subscribers_lock:
            subscribers = list(self._subscribers.values())
        for subscription in subscribers:
            channels = subscription["channels"]
            session_id = subscription["sessionId"]
            if channels and payload["channel"] not in channels:
                continue
            if session_id and payload.get("sessionId") != session_id:
                continue
            try:
                subscription["callback"](dict(payload))
            except Exception:
                logging.getLogger("voicestt.fastapi").debug(
                    "Log-Abonnent konnte nicht benachrichtigt werden",
                    exc_info=True,
                )

    def subscribe(
        self,
        callback: Callable[[Dict[str, Any]], None],
        *,
        channels: Optional[Iterable[str]] = None,
        session_id: Optional[str] = None,
    ) -> str:
        subscription_id = uuid.uuid4().hex
        with self._subscribers_lock:
            self._subscribers[subscription_id] = {
                "callback": callback,
                "channels": set(channels or []),
                "sessionId": session_id,
            }
        return subscription_id

    def subscribe_async(
        self,
        loop: asyncio.AbstractEventLoop,
        target: asyncio.Queue,
        *,
        channels: Optional[Iterable[str]] = None,
        session_id: Optional[str] = None,
    ) -> str:
        dropped = [0]

        def deliver(payload):
            def put():
                try:
                    if dropped[0]:
                        target.put_nowait({
                            "_logControl": "gap",
                            "dropped": dropped[0],
                            "cursor": payload.get("cursor"),
                        })
                        dropped[0] = 0
                    target.put_nowait(payload)
                except asyncio.QueueFull:
                    dropped[0] += 1

            loop.call_soon_threadsafe(put)

        return self.subscribe(
            deliver,
            channels=channels,
            session_id=session_id,
        )

    def unsubscribe(self, subscription_id: str):
        with self._subscribers_lock:
            self._subscribers.pop(subscription_id, None)

    def query(self, **filters):
        if self._store is None:
            return []
        self.flush()
        return self._store.query(**filters)

    def latest_cursor(self) -> int:
        self.flush()
        if self._store is not None:
            return self._store.latest_cursor()
        return self._fallback_cursor

    def flush(self):
        if not self._closed:
            self._queue.join()

    def close(self):
        if self._closed:
            return
        self.flush()
        self._closed = True
        self._queue.put(None)
        self._worker.join(timeout=5)
        with self._settings_lock:
            for sink in self._sinks.values():
                sink.close()
            self._sinks = {}
        if self._store is not None:
            self._store.close()


class ChannelLogManager:
    """Compatibility facade for the existing audit/performance call sites."""

    def __init__(
        self,
        settings,
        channel: str,
        messages: Dict[str, str],
        event_hub: Optional[StructuredEventHub] = None,
    ):
        self.channel = channel
        self.messages = messages
        self._owns_hub = event_hub is None
        self.hub = event_hub or StructuredEventHub(settings)

    def configure(self, settings):
        self.hub.configure(settings)

    def event(self, event, **fields):
        severity = "info"
        if event.endswith(".failed"):
            severity = "error"
        elif event.endswith((".rejected", ".warning", ".timeout", ".dropped")):
            severity = "warning"
        event_id = self.hub.emit(
            self.channel,
            event,
            message=self.messages.get(event, event),
            severity=severity,
            **fields,
        )
        if self._owns_hub:
            self.hub.flush()
        return event_id

    def flush(self):
        self.hub.flush()

    def close(self):
        if self._owns_hub:
            self.hub.close()
