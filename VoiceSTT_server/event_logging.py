"""Structured server event channels, persistence, and live subscriptions."""

from __future__ import annotations

import asyncio
import json
import logging
import queue
import re
import sqlite3
import sys
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Optional
from urllib.parse import urlsplit, urlunsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


CONTEXT_FIELDS = {
    "clientId",
    "requestId",
    "segmentId",
    "sessionId",
    "transcriptionId",
    "transport",
}

_DROP_FIELD = object()
_SECRET_KEYS = {
    "accesstoken",
    "adminkey",
    "adminapikey",
    "apikey",
    "authorization",
    "cookie",
    "credential",
    "credentials",
    "logtoken",
    "openaiapikey",
    "password",
    "privatekey",
    "refreshtoken",
    "secret",
    "sessiontoken",
    "setcookie",
    "token",
    "xapikey",
    "xvoicesttadminkey",
    "xvoicesttlogtoken",
}
_AUDIO_KEYS = {
    "audio",
    "audiodata",
    "audiobytes",
    "audioraw",
    "pcm",
    "rawaudio",
    "samples",
    "waveform",
}
_TRANSCRIPT_KEYS = {
    "committedstabletext",
    "consensustext",
    "delta",
    "displaytext",
    "rawtext",
    "stabletext",
    "text",
    "transcript",
    "transcriptiontext",
    "unstabletext",
    "visualstabletext",
    "visualunstabletext",
}
_QUERY_KEYS = {"query", "queryparams", "querystring", "rawquery"}
_SECRET_TEXT_PATTERN = re.compile(
    r"(?i)\b(authorization|access[_-]?token|api[_-]?key|password|secret)"
    r"\s*[:=]\s*(?:bearer\s+)?[^\s,;]+"
)
_BEARER_PATTERN = re.compile(r"(?i)\bbearer\s+[^\s,;]+")


def _normalized_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def _sanitize_string(value: str, key: str) -> str:
    sanitized = _BEARER_PATTERN.sub("Bearer [REDACTED]", value)
    sanitized = _SECRET_TEXT_PATTERN.sub(
        lambda match: f"{match.group(1)}=[REDACTED]",
        sanitized,
    )
    try:
        parsed = urlsplit(sanitized)
        if parsed.query and (
            parsed.scheme
            or parsed.netloc
            or key.endswith("url")
            or key in {"uri", "requesturl"}
        ):
            sanitized = urlunsplit((
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                "",
                parsed.fragment,
            ))
    except ValueError:
        pass
    return sanitized


def sanitize_event_value(
    key: Any,
    value: Any,
    *,
    channel: str,
    event: str,
    transcript_mode: str,
):
    """Recursively remove secrets, raw audio and disallowed transcript data."""

    normalized = _normalized_key(key)
    if (
        normalized in _SECRET_KEYS
        or normalized.endswith((
            "apikey",
            "authorization",
            "cookie",
            "credential",
            "password",
            "privatekey",
            "secret",
            "token",
        ))
        or normalized in _AUDIO_KEYS
    ):
        return _DROP_FIELD
    if normalized in _QUERY_KEYS:
        return _DROP_FIELD
    if normalized in _TRANSCRIPT_KEYS:
        if channel == "performance":
            return _DROP_FIELD
        if transcript_mode == "none":
            return _DROP_FIELD
        if transcript_mode == "final" and not (
            channel == "transcription"
            and event == "transcription.completed"
        ):
            return _DROP_FIELD
        if channel != "transcription":
            return _DROP_FIELD
    if isinstance(value, (bytes, bytearray, memoryview)):
        return _DROP_FIELD
    if isinstance(value, dict):
        cleaned = {}
        for child_key, child_value in value.items():
            sanitized = sanitize_event_value(
                child_key,
                child_value,
                channel=channel,
                event=event,
                transcript_mode=transcript_mode,
            )
            if sanitized is not _DROP_FIELD:
                cleaned[str(child_key)] = sanitized
        return cleaned
    if isinstance(value, (list, tuple, set)):
        cleaned = []
        for child_value in value:
            sanitized = sanitize_event_value(
                "",
                child_value,
                channel=channel,
                event=event,
                transcript_mode=transcript_mode,
            )
            if sanitized is not _DROP_FIELD:
                cleaned.append(sanitized)
        return cleaned
    if isinstance(value, str):
        return _sanitize_string(value, normalized)
    return value


class BoundedPriorityEventQueue:
    """Non-blocking FIFO queue that may evict older low-priority work."""

    def __init__(self, maxsize: int):
        self.maxsize = max(1, int(maxsize))
        self._items = []
        self._sequence = 0
        self._unfinished = 0
        self._closed = False
        self._condition = threading.Condition()

    def put_nowait(self, item, priority: int):
        with self._condition:
            if self._closed:
                return False, item
            self._sequence += 1
            entry = (int(priority), self._sequence, item)
            if len(self._items) >= self.maxsize:
                worst_index = max(
                    range(len(self._items)),
                    key=lambda index: (
                        self._items[index][0],
                        self._items[index][1],
                    ),
                )
                worst = self._items[worst_index]
                if worst[0] <= entry[0]:
                    return False, item
                self._items[worst_index] = entry
                self._condition.notify()
                return True, worst[2]
            self._items.append(entry)
            self._unfinished += 1
            self._condition.notify()
            return True, None

    def get(self):
        with self._condition:
            while not self._items and not self._closed:
                self._condition.wait()
            if not self._items:
                return None
            oldest_index = min(
                range(len(self._items)),
                key=lambda index: self._items[index][1],
            )
            return self._items.pop(oldest_index)[2]

    def task_done(self):
        with self._condition:
            self._unfinished -= 1
            if self._unfinished <= 0:
                self._unfinished = 0
                self._condition.notify_all()

    def join(self):
        with self._condition:
            while self._unfinished:
                self._condition.wait()

    def close(self):
        with self._condition:
            self._closed = True
            self._condition.notify_all()


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
        retention_days: int = 0,
    ):
        self.root = Path(root)
        self.timezone = resolve_calendar_timezone(timezone_name)
        self.max_bytes = max(0, int(max_bytes or 0))
        self.backup_count = max(0, int(backup_count or 0))
        self.retention_days = max(0, int(retention_days or 0))
        self._lock = threading.RLock()
        self._day = None
        self._path = None
        self._stream = None
        self._last_cleanup_day = None

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
        self._cleanup(day)
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

    def _cleanup(self, current_day):
        if (
            not self.retention_days
            or self._last_cleanup_day == current_day
            or not self.root.is_dir()
        ):
            return
        cutoff = current_day - timedelta(days=self.retention_days)
        for month_dir in self.root.iterdir():
            if not month_dir.is_dir() or not re.fullmatch(
                r"\d{4}-\d{2}",
                month_dir.name,
            ):
                continue
            for path in month_dir.glob("*.jsonl"):
                match = re.match(r"(\d{4}-\d{2}-\d{2})", path.name)
                if not match:
                    continue
                try:
                    file_day = datetime.strptime(
                        match.group(1),
                        "%Y-%m-%d",
                    ).date()
                except ValueError:
                    continue
                if file_day < cutoff and path != self._path:
                    path.unlink(missing_ok=True)
            try:
                next(month_dir.iterdir())
            except StopIteration:
                month_dir.rmdir()
        self._last_cleanup_day = current_day

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
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS retention_watermarks (
                channel TEXT NOT NULL,
                session_id TEXT NOT NULL,
                cursor INTEGER NOT NULL,
                PRIMARY KEY (channel, session_id)
            )
            """
        )
        self._connection.commit()
        self._retention_days = {}
        self._last_prune_day = None

    def set_retention(self, retention_days: Dict[str, int]):
        with self._lock:
            self._retention_days = {
                str(channel): max(0, int(days or 0))
                for channel, days in dict(retention_days or {}).items()
            }
            self._last_prune_day = None

    def _prune_if_due(self, now=None):
        now = now or datetime.now(timezone.utc)
        current_day = now.date()
        if self._last_prune_day == current_day:
            return
        for channel, days in self._retention_days.items():
            if days <= 0:
                continue
            cutoff = (now - timedelta(days=days)).isoformat(
                timespec="milliseconds"
            ).replace("+00:00", "Z")
            removed_scopes = self._connection.execute(
                """
                SELECT channel, COALESCE(session_id, ''), MAX(cursor)
                FROM events
                WHERE channel = ? AND timestamp < ?
                GROUP BY channel, COALESCE(session_id, '')
                """,
                (channel, cutoff),
            ).fetchall()
            for removed_channel, session_id, cursor in removed_scopes:
                self._connection.execute(
                    """
                    INSERT INTO retention_watermarks (
                        channel, session_id, cursor
                    ) VALUES (?, ?, ?)
                    ON CONFLICT(channel, session_id) DO UPDATE SET
                        cursor = MAX(cursor, excluded.cursor)
                    """,
                    (removed_channel, session_id, int(cursor)),
                )
            self._connection.execute(
                "DELETE FROM events WHERE channel = ? AND timestamp < ?",
                (channel, cutoff),
            )
        self._connection.commit()
        self._last_prune_day = current_day

    def append(self, event: Dict[str, Any]) -> int:
        with self._lock:
            self._prune_if_due()
            cursor = self._cursor_high_watermark_locked() + 1
            committed_event = dict(event)
            committed_event["cursor"] = cursor
            try:
                self._connection.execute(
                    """
                    INSERT INTO events (
                        cursor, event_id, timestamp, channel, event_name,
                        severity, server_instance_id, transport, client_id,
                        session_id, request_id, transcription_id, segment_id,
                        payload_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        cursor,
                        committed_event["eventId"],
                        committed_event["timestamp"],
                        committed_event["channel"],
                        committed_event["event"],
                        committed_event["severity"],
                        committed_event["serverInstanceId"],
                        committed_event.get("transport"),
                        committed_event.get("clientId"),
                        committed_event.get("sessionId"),
                        committed_event.get("requestId"),
                        committed_event.get("transcriptionId"),
                        (
                            str(committed_event["segmentId"])
                            if committed_event.get("segmentId") is not None
                            else None
                        ),
                        json.dumps(
                            committed_event,
                            ensure_ascii=False,
                            separators=(",", ":"),
                            default=str,
                        ),
                    ),
                )
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                raise
            return cursor

    def _cursor_high_watermark_locked(self) -> int:
        row = self._connection.execute(
            """
            SELECT MAX(
                COALESCE((SELECT MAX(cursor) FROM events), 0),
                COALESCE(
                    (SELECT seq FROM sqlite_sequence WHERE name = 'events'),
                    0
                )
            )
            """
        ).fetchone()
        return int(row[0] or 0)

    def latest_cursor(self) -> int:
        with self._lock:
            return self._cursor_high_watermark_locked()

    def oldest_cursor(self) -> int:
        with self._lock:
            row = self._connection.execute(
                "SELECT MIN(cursor) FROM events"
            ).fetchone()
            return int(row[0] or 0)

    def retention_cursor(
        self,
        *,
        channels: Optional[Iterable[str]] = None,
        session_id: Optional[str] = None,
    ) -> int:
        clauses = []
        parameters = []
        channel_values = [
            str(value) for value in (channels or []) if str(value)
        ]
        if channel_values:
            clauses.append(
                f"channel IN ({','.join('?' for _ in channel_values)})"
            )
            parameters.extend(channel_values)
        if session_id not in (None, ""):
            clauses.append("session_id = ?")
            parameters.append(str(session_id))
        sql = "SELECT MAX(cursor) FROM retention_watermarks"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        with self._lock:
            row = self._connection.execute(sql, parameters).fetchone()
        return int(row[0] or 0)

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
        self._settings_lock = threading.RLock()
        self._cursor_lock = threading.Lock()
        self._drop_lock = threading.Lock()
        self._store_state_lock = threading.RLock()
        self._subscribers_lock = threading.RLock()
        self._subscribers: Dict[str, Dict[str, Any]] = {}
        self._dropped_events = 0
        self._drop_counts: Dict[str, int] = {}
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
        self._cursor = self._store.latest_cursor() if self._store is not None else 0
        self._store_state = "ready" if self._store is not None else "disabled"
        self._store_last_error_type = None
        self._store_last_transition_at = utc_timestamp()
        self._channel_config = {}
        self._sinks: Dict[str, CalendarJsonlSink] = {}
        self.configure(settings)
        queue_size = max(
            1,
            int(getattr(settings, "event_log_queue_size", 10000)),
        )
        self._queues = {
            name: BoundedPriorityEventQueue(queue_size)
            for name in ("file", "stdout")
        }
        # Commit/store notifications are deliberately payload-free. A missed
        # commit wakeup is harmless because subscribers always rescan SQLite
        # from their own committed cursor and keepalive performs a periodic
        # high-watermark check.
        self._control_queue = queue.Queue(maxsize=queue_size)
        self._workers = {
            "file": threading.Thread(
                target=self._run_file,
                name="VoiceSTTEventFileWriter",
                daemon=True,
            ),
            "stdout": threading.Thread(
                target=self._run_stdout,
                name="VoiceSTTEventStdoutWriter",
                daemon=True,
            ),
            "control": threading.Thread(
                target=self._run_control,
                name="VoiceSTTEventControlPublisher",
                daemon=True,
            ),
        }
        for worker in self._workers.values():
            worker.start()

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
                "retention_days": getattr(
                    settings,
                    "request_log_retention_days",
                    0,
                ),
            },
            "performance": {
                "enabled": bool(
                    getattr(settings, "performance_log_mirror_enabled", True)
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
                "retention_days": getattr(
                    settings,
                    "performance_log_retention_days",
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
                "retention_days": getattr(
                    settings,
                    "transcription_log_retention_days",
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
                "retention_days": getattr(
                    settings,
                    "system_event_log_retention_days",
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
                    config["retention_days"],
                )
        with self._settings_lock:
            old_sinks = self._sinks
            self._sinks = new_sinks
            self._channel_config = definitions
            configured_mode = str(
                getattr(settings, "transcript_log_mode", "") or ""
            ).strip().lower()
            self.transcript_mode = (
                configured_mode
                if configured_mode in {"none", "final", "full"}
                else (
                    "final"
                    if bool(
                        getattr(settings, "request_log_transcripts", True)
                    )
                    else "none"
                )
            )
            self.realtime_detail = str(
                getattr(settings, "realtime_log_detail", "events")
            ).strip().lower()
        if self._store is not None:
            self._store.set_retention({
                channel: config["retention_days"]
                for channel, config in definitions.items()
            })
        for sink in old_sinks.values():
            sink.close()

    def _next_cursor(self) -> int:
        with self._cursor_lock:
            self._cursor += 1
            return self._cursor

    @staticmethod
    def _priority(channel: str, event: str, severity: str) -> int:
        if channel == "audit" or severity in {"error", "critical"}:
            return 0
        if channel == "transcription" and event.endswith((
            ".completed",
            ".failed",
            ".rejected",
            ".cancelled",
            ".discarded",
        )):
            return 0
        if channel == "performance":
            return 2
        return 1

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
            transcript_mode = self.transcript_mode
        # Per-channel enabled switches control only the optional JSONL/stdout
        # mirrors. Once the canonical store is enabled, every generated event
        # must follow the same SQLite-first contract.
        if not config or self._closed:
            return None
        event = str(event)
        severity = str(severity)
        sanitized_fields = {}
        for key, value in fields.items():
            sanitized = sanitize_event_value(
                key,
                value,
                channel=channel,
                event=event,
                transcript_mode=transcript_mode,
            )
            if sanitized is not _DROP_FIELD and sanitized is not None:
                sanitized_fields[key] = sanitized
        context = {}
        for name in CONTEXT_FIELDS:
            if name in sanitized_fields:
                context[name] = sanitized_fields.pop(name)
        sanitized_message = sanitize_event_value(
            "message",
            message,
            channel=channel,
            event=event,
            transcript_mode=transcript_mode,
        )
        payload = {
            "schemaVersion": 1,
            "eventId": uuid.uuid4().hex,
            "timestamp": utc_timestamp(),
            "channel": channel,
            "event": event,
            "severity": severity,
            "serverInstanceId": self.server_instance_id,
            **context,
            "data": sanitized_fields,
        }
        if sanitized_message not in (None, _DROP_FIELD):
            payload["meldung"] = sanitized_message

        if self._store is not None:
            try:
                cursor = self._store.append(payload)
            except Exception as exc:
                logging.getLogger("voicestt.fastapi").exception(
                    "Kanonischer SQLite-Eventstore ist fehlgeschlagen"
                )
                self._set_store_state("degraded", error=exc)
                return None
            payload["cursor"] = cursor
            with self._cursor_lock:
                self._cursor = cursor
            self._set_store_state("ready")
            self._enqueue_control({
                "_logControl": "commit",
                "cursor": cursor,
            })
        else:
            payload["cursor"] = self._next_cursor()

        priority = self._priority(channel, event, severity)
        targets = []
        with self._settings_lock:
            if channel in self._sinks:
                targets.append("file")
            if (
                self._channel_config.get(channel, {}).get("enabled")
                and self._channel_config.get(channel, {}).get("stdout")
            ):
                targets.append("stdout")
        for target in targets:
            self._enqueue(target, payload, priority)
        return payload["eventId"]

    def _enqueue(self, target, payload, priority):
        accepted, dropped = self._queues[target].put_nowait(
            payload,
            priority,
        )
        if dropped is not None:
            self._record_sink_drop(target, dropped)
        return accepted

    def _run_worker(self, target, callback):
        event_queue = self._queues[target]
        while True:
            payload = event_queue.get()
            if payload is None:
                return
            try:
                try:
                    callback(payload)
                except Exception:
                    logging.getLogger("voicestt.fastapi").exception(
                        "Strukturierter Event-Sink '%s' ist fehlgeschlagen",
                        target,
                    )
                    self._record_sink_drop(target, payload, failed=True)
            finally:
                event_queue.task_done()

    def _run_file(self):
        self._run_worker("file", self._write_file)

    def _run_stdout(self):
        self._run_worker("stdout", self._write_stdout)

    def _run_control(self):
        while True:
            payload = self._control_queue.get()
            try:
                if payload is None:
                    return
                self._publish_control(payload)
            finally:
                self._control_queue.task_done()

    def _write_file(self, payload):
        channel = payload["channel"]
        with self._settings_lock:
            sink = self._sinks.get(channel)
        if sink is not None:
            sink.write(payload)

    @staticmethod
    def _write_stdout(payload):
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

    def _record_sink_drop(self, sink, payload, failed=False):
        with self._drop_lock:
            self._dropped_events += 1
            self._drop_counts[sink] = self._drop_counts.get(sink, 0) + 1
        logging.getLogger("voicestt.fastapi").warning(
            "Optionaler strukturierter Eventspiegel '%s' hat ein Event %s",
            sink,
            "nicht schreiben können" if failed else "verworfen",
        )

    def _enqueue_control(self, payload, *, critical=False):
        try:
            self._control_queue.put_nowait(dict(payload))
            return True
        except queue.Full:
            if not critical:
                return False
        try:
            self._control_queue.get_nowait()
            self._control_queue.task_done()
        except queue.Empty:
            pass
        try:
            self._control_queue.put_nowait(dict(payload))
            return True
        except queue.Full:
            return False

    def _set_store_state(self, state, *, error=None):
        error_type = type(error).__name__ if error is not None else None
        with self._store_state_lock:
            changed = (
                state != self._store_state
                or (
                    state == "degraded"
                    and error_type != self._store_last_error_type
                )
            )
            self._store_state = str(state)
            self._store_last_error_type = error_type
            if changed:
                self._store_last_transition_at = utc_timestamp()
        if not changed:
            return
        if state == "degraded":
            self._enqueue_control({
                "_logControl": "store_error",
                "code": "event_store_unavailable",
            }, critical=True)
        elif state == "ready":
            self._enqueue_control({
                "_logControl": "store_recovered",
                "cursor": self.latest_cursor(),
            })

    def _publish_control(self, payload):
        with self._subscribers_lock:
            subscribers = list(self._subscribers.values())
        for subscription in subscribers:
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
        def deliver(payload):
            def put():
                try:
                    target.put_nowait(payload)
                except asyncio.QueueFull:
                    if payload.get("_logControl") != "store_error":
                        return
                    try:
                        target.get_nowait()
                        target.task_done()
                        target.put_nowait(payload)
                    except (asyncio.QueueEmpty, asyncio.QueueFull):
                        return

            loop.call_soon_threadsafe(put)

        subscription_id = self.subscribe(
            deliver,
            channels=channels,
            session_id=session_id,
        )
        return subscription_id

    def unsubscribe(self, subscription_id: str):
        with self._subscribers_lock:
            self._subscribers.pop(subscription_id, None)

    def query(self, **filters):
        if self._store is None:
            return []
        try:
            result = self._store.query(**filters)
        except Exception as exc:
            self._set_store_state("degraded", error=exc)
            raise
        self._set_store_state("ready")
        return result

    def latest_cursor(self) -> int:
        if self._store is not None:
            try:
                cursor = self._store.latest_cursor()
            except Exception as exc:
                self._set_store_state("degraded", error=exc)
                raise
            return cursor
        with self._cursor_lock:
            return self._cursor

    def oldest_cursor(self) -> int:
        if self._store is None:
            return 0
        try:
            cursor = self._store.oldest_cursor()
        except Exception as exc:
            self._set_store_state("degraded", error=exc)
            raise
        return cursor

    def retention_cursor(self, **filters) -> int:
        if self._store is None:
            return 0
        try:
            cursor = self._store.retention_cursor(**filters)
        except Exception as exc:
            self._set_store_state("degraded", error=exc)
            raise
        return cursor

    def store_status(self):
        oldest_cursor = 0
        latest_cursor = 0
        if self._store is not None:
            try:
                oldest_cursor = self._store.oldest_cursor()
                latest_cursor = self._store.latest_cursor()
            except Exception as exc:
                self._set_store_state("degraded", error=exc)
        with self._store_state_lock:
            return {
                "state": self._store_state,
                "available": self._store_state == "ready",
                "lastErrorType": self._store_last_error_type,
                "lastTransitionAt": self._store_last_transition_at,
                "oldestCursor": oldest_cursor,
                "latestCursor": latest_cursor,
            }

    def store_available(self) -> bool:
        with self._store_state_lock:
            return self._store_state == "ready"

    def drop_counts(self):
        with self._drop_lock:
            return dict(self._drop_counts)

    def flush(self):
        if not self._closed:
            for event_queue in self._queues.values():
                event_queue.join()
            self._control_queue.join()

    def close(self):
        if self._closed:
            return
        self.flush()
        self._closed = True
        for event_queue in self._queues.values():
            event_queue.close()
        self._control_queue.put_nowait(None)
        for worker in self._workers.values():
            worker.join(timeout=5)
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
