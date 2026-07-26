"""Operational helpers for model discovery, audit logging, and runtime config."""

import json
import logging
import os
import sys
import threading
import uuid
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

from VoiceSTT.core.openwakeword_catalog import OpenWakeWordCatalog

FASTER_MODEL_ROOT_ENV = "VOICESTT_FASTER_WHISPER_MODEL_ROOT"
KROKO_MODEL_ROOT_ENV = "VOICESTT_KROKO_MODEL_ROOT"
OPENWAKEWORD_MODEL_ROOT_ENV = "VOICESTT_OPENWAKEWORD_MODEL_ROOT"

AUDIT_EVENT_MESSAGES_DE = {
    "config.updated": "Konfiguration aktualisiert",
    "language.updated": "Sprache aktualisiert",
    "models.loaded": "Modelle geladen",
    "models.switched": "Modelle gewechselt",
    "models.unloaded": "Modelle aus dem RAM entladen",
    "transcription.completed": "Transkription abgeschlossen",
    "transcription.failed": "Transkription fehlgeschlagen",
    "transcription.rejected": "Transkription abgelehnt",
    "transcription.started": "Transkription gestartet",
    "websocket.connected": "WebSocket verbunden",
    "websocket.disconnected": "WebSocket getrennt",
    "websocket.session_config_rejected": "WebSocket-Sitzungskonfiguration abgelehnt",
}

PERFORMANCE_EVENT_MESSAGES_DE = {
    "http.completed": "HTTP-Transkription abgeschlossen",
    "http.first_text": "Erster HTTP-Text ausgegeben",
    "inference.completed": "Inferenz abgeschlossen",
    "models.load_failed": "Modellladen fehlgeschlagen",
    "models.loaded": "Modelle geladen",
    "models.switched": "Modelle gewechselt",
    "models.unloaded": "Modelle aus dem RAM entladen",
    "stream.final_text": "Finaler Streamtext ausgegeben",
    "stream.first_text": "Erster Streamtext ausgegeben",
}


if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    class _ProcessMemoryCountersEx(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
            ("PrivateUsage", ctypes.c_size_t),
        ]


def _utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def process_memory_snapshot():
    """Return best-effort process memory counters without an optional dependency."""

    try:
        if sys.platform == "win32":
            counters = _ProcessMemoryCountersEx()
            counters.cb = ctypes.sizeof(counters)
            get_current_process = ctypes.windll.kernel32.GetCurrentProcess
            get_current_process.argtypes = []
            get_current_process.restype = wintypes.HANDLE
            get_memory_info = ctypes.windll.psapi.GetProcessMemoryInfo
            get_memory_info.argtypes = [
                wintypes.HANDLE,
                ctypes.POINTER(_ProcessMemoryCountersEx),
                wintypes.DWORD,
            ]
            get_memory_info.restype = wintypes.BOOL
            process = get_current_process()
            ok = get_memory_info(
                process, ctypes.byref(counters), counters.cb
            )
            if ok:
                return {
                    "rssBytes": int(counters.WorkingSetSize),
                    "peakRssBytes": int(counters.PeakWorkingSetSize),
                    "privateBytes": int(counters.PrivateUsage),
                }

        proc_status = Path("/proc/self/status")
        if proc_status.is_file():
            values = {}
            for line in proc_status.read_text(encoding="ascii", errors="replace").splitlines():
                key, separator, value = line.partition(":")
                if separator and key in {"VmRSS", "VmHWM"}:
                    values[key] = int(value.strip().split()[0]) * 1024
            if values:
                return {
                    "rssBytes": values.get("VmRSS"),
                    "peakRssBytes": values.get("VmHWM"),
                }
    except (OSError, TypeError, ValueError, AttributeError):
        pass
    return {}


def _ctranslate_model_path(path):
    path = Path(path)
    if (path / "config.json").is_file() and (path / "model.bin").is_file():
        return path
    snapshots = path / "snapshots"
    if snapshots.is_dir():
        for candidate in sorted(snapshots.iterdir(), reverse=True):
            if (candidate / "config.json").is_file() and (candidate / "model.bin").is_file():
                return candidate
    return None


class LocalModelRegistry:
    """Discover local Faster-Whisper and Kroko models without network access."""

    def __init__(self, faster_root=None, kroko_root=None):
        self.faster_root = Path(
            faster_root or os.getenv(FASTER_MODEL_ROOT_ENV, "")
        ).expanduser() if (faster_root or os.getenv(FASTER_MODEL_ROOT_ENV)) else None
        self.kroko_root = Path(
            kroko_root or os.getenv(KROKO_MODEL_ROOT_ENV, "")
        ).expanduser() if (kroko_root or os.getenv(KROKO_MODEL_ROOT_ENV)) else None

    def _configured_aliases(self):
        if self.faster_root is None:
            return {}
        config_path = self.faster_root / "stt_models.json"
        if not config_path.is_file():
            return {}
        try:
            payload = json.loads(config_path.read_text(encoding="utf-8"))
            return dict(payload.get("stt", {}).get("models", {}))
        except (OSError, ValueError, TypeError):
            return {}

    def list_models(self):
        entries = []
        seen = set()
        aliases = self._configured_aliases()
        aliases_by_folder = {str(folder).lower(): str(alias) for alias, folder in aliases.items()}

        if self.faster_root is not None and self.faster_root.is_dir():
            for folder in sorted(self.faster_root.iterdir()):
                if not folder.is_dir() or folder.name.startswith("."):
                    continue
                model_path = _ctranslate_model_path(folder)
                if model_path is None:
                    continue
                alias = aliases_by_folder.get(folder.name.lower())
                model_name = folder.name
                if model_name.lower().startswith("models--"):
                    parts = model_name.split("--", 2)
                    if len(parts) == 3:
                        model_name = parts[2]
                model_id = alias or model_name
                entries.append({
                    "id": model_id,
                    "object": "model",
                    "engine": "faster_whisper",
                    "alias": alias,
                    "name": model_name,
                    "folder": folder.name,
                    "path": str(model_path.resolve()),
                    "available": True,
                })
                seen.add(("faster_whisper", model_id.lower()))

        if self.kroko_root is not None and self.kroko_root.is_dir():
            for path in sorted(self.kroko_root.glob("*.data")):
                key = ("kroko_onnx", path.name.lower())
                if key in seen:
                    continue
                entries.append({
                    "id": path.name,
                    "object": "model",
                    "engine": "kroko_onnx",
                    "alias": None,
                    "name": path.name,
                    "folder": path.name,
                    "path": str(path.resolve()),
                    "available": True,
                })
                seen.add(key)
        return entries

    def aliases_for(self, engine, configured_model):
        normalized_engine = str(engine or "").lower().replace("-", "_")
        value = str(configured_model or "").lower()
        matches = {str(configured_model)}
        for entry in self.list_models():
            if entry["engine"] != normalized_engine:
                continue
            candidates = {
                str(entry.get("id") or ""), str(entry.get("alias") or ""),
                str(entry.get("name") or ""), str(entry.get("folder") or ""),
                str(entry.get("path") or ""),
            }
            if value in {candidate.lower() for candidate in candidates if candidate}:
                matches.update(candidate for candidate in candidates if candidate)
        return matches

    def resolve(self, requested, preferred_engine=None):
        value = str(requested or "").strip().lower()
        for entry in self.list_models():
            if preferred_engine and entry["engine"] != str(preferred_engine).lower().replace("-", "_"):
                continue
            candidates = {
                str(entry.get("id") or ""), str(entry.get("alias") or ""),
                str(entry.get("name") or ""), str(entry.get("folder") or ""),
                str(entry.get("path") or ""),
            }
            if value in {candidate.lower() for candidate in candidates if candidate}:
                return entry
        return None


class WakeWordRegistry:
    """Discover usable OpenWakeWord models without network access."""

    def __init__(self, openwakeword_root=None):
        configured = openwakeword_root or os.getenv(OPENWAKEWORD_MODEL_ROOT_ENV, "")
        self.openwakeword_root = Path(configured).expanduser() if configured else None

    def openwakeword_models(self, configured_paths=None, framework="onnx"):
        return OpenWakeWordCatalog(
            self.openwakeword_root,
            configured_paths,
        ).entries(framework, include_paths=True)

    def resolve_openwakeword(self, model_ids, configured_paths=None, framework="onnx"):
        return OpenWakeWordCatalog(
            self.openwakeword_root,
            configured_paths,
        ).resolve(model_ids, framework)

    def default_openwakeword(self, configured_paths=None, framework="onnx"):
        catalog = OpenWakeWordCatalog(
            self.openwakeword_root,
            configured_paths,
        )
        resolved, missing = catalog.resolve(None, framework)
        return (resolved[0] if resolved else None), missing

    def catalog(self, configured_paths=None, framework="onnx"):
        return {
            "openwakeword": self.openwakeword_models(configured_paths, framework),
        }


class AuditLogManager:
    """Write the same structured request events to stdout and a rotating file."""

    def __init__(self, settings):
        self._lock = threading.RLock()
        self.logger = logging.getLogger("voicestt.audit")
        self.logger.propagate = False
        self.configure(settings)

    def configure(self, settings):
        with self._lock:
            for handler in list(self.logger.handlers):
                self.logger.removeHandler(handler)
                try:
                    handler.close()
                except Exception:
                    pass
            self.enabled = bool(settings.request_logging_enabled)
            self.include_transcripts = bool(settings.request_log_transcripts)
            self.save_audio = bool(settings.save_audio_files)
            self.audio_dir = Path(settings.audio_log_dir or "logs/audio").expanduser()
            self.logger.setLevel(logging.INFO)
            formatter = logging.Formatter("%(message)s")
            if self.enabled and settings.request_log_stdout:
                stream = logging.StreamHandler()
                stream.setFormatter(formatter)
                self.logger.addHandler(stream)
            if self.enabled and settings.request_log_path:
                path = Path(settings.request_log_path).expanduser()
                path.parent.mkdir(parents=True, exist_ok=True)
                file_handler = RotatingFileHandler(
                    path,
                    maxBytes=int(settings.request_log_max_bytes),
                    backupCount=int(settings.request_log_backup_count),
                    encoding="utf-8",
                )
                file_handler.setFormatter(formatter)
                self.logger.addHandler(file_handler)
            if self.save_audio:
                self.audio_dir.mkdir(parents=True, exist_ok=True)

    def event(self, event, **fields):
        if not self.enabled:
            return
        payload = {
            "timestamp": _utc_now(),
            "event": event,
            "meldung": AUDIT_EVENT_MESSAGES_DE.get(event, event),
        }
        payload.update({key: value for key, value in fields.items() if value is not None})
        if not self.include_transcripts:
            payload.pop("text", None)
        self.logger.info(json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str))

    def archive_audio(self, data, original_filename, request_id):
        if not self.save_audio:
            return None
        suffix = Path(original_filename or "audio.bin").suffix.lower() or ".audio"
        day_dir = self.audio_dir / datetime.now().strftime("%Y-%m-%d")
        day_dir.mkdir(parents=True, exist_ok=True)
        path = day_dir / f"{datetime.now().strftime('%H%M%S_%f')}_{request_id}{suffix}"
        path.write_bytes(data)
        return str(path.resolve())

    def close(self):
        with self._lock:
            for handler in list(self.logger.handlers):
                self.logger.removeHandler(handler)
                try:
                    handler.close()
                except Exception:
                    pass


class PerformanceLogManager:
    """Write operational performance measurements to a separate JSONL channel."""

    def __init__(self, settings):
        self._lock = threading.RLock()
        self.logger = logging.getLogger("voicestt.performance")
        self.logger.propagate = False
        self.configure(settings)

    def configure(self, settings):
        with self._lock:
            for handler in list(self.logger.handlers):
                self.logger.removeHandler(handler)
                try:
                    handler.close()
                except Exception:
                    pass
            self.enabled = bool(settings.performance_logging_enabled)
            self.logger.setLevel(logging.INFO)
            formatter = logging.Formatter("%(message)s")
            if self.enabled and settings.performance_log_stdout:
                stream = logging.StreamHandler()
                stream.setFormatter(formatter)
                self.logger.addHandler(stream)
            if self.enabled and settings.performance_log_path:
                path = Path(settings.performance_log_path).expanduser()
                path.parent.mkdir(parents=True, exist_ok=True)
                file_handler = RotatingFileHandler(
                    path,
                    maxBytes=int(settings.performance_log_max_bytes),
                    backupCount=int(settings.performance_log_backup_count),
                    encoding="utf-8",
                )
                file_handler.setFormatter(formatter)
                self.logger.addHandler(file_handler)

    def event(self, event, **fields):
        if not self.enabled:
            return
        payload = {
            "timestamp": _utc_now(),
            "channel": "performance",
            "event": event,
            "meldung": PERFORMANCE_EVENT_MESSAGES_DE.get(event, event),
        }
        payload.update({key: value for key, value in fields.items() if value is not None})
        self.logger.info(json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str))

    def close(self):
        with self._lock:
            for handler in list(self.logger.handlers):
                self.logger.removeHandler(handler)
                try:
                    handler.close()
                except Exception:
                    pass


class RuntimeConfigStore:
    """Persist non-secret runtime settings as JSON with atomic replacement."""

    def __init__(self, path=None):
        self.path = Path(path).expanduser() if path else None
        self._lock = threading.RLock()

    def load(self):
        if self.path is None or not self.path.is_file():
            return {}
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        settings = payload.get("settings", payload)
        if not isinstance(settings, dict):
            raise ValueError("Die Laufzeitkonfiguration muss ein settings-Objekt enthalten.")
        return settings

    def save(self, settings, allowed_names):
        if self.path is None:
            return None
        if is_dataclass(settings):
            values = asdict(settings)
        else:
            values = dict(settings)
        payload = {
            "version": 1,
            "updatedAt": _utc_now(),
            "settings": {name: values[name] for name in sorted(allowed_names) if name in values},
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(f".{self.path.name}.{uuid.uuid4().hex}.tmp")
        with self._lock:
            temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
            os.replace(temporary, self.path)
        return str(self.path.resolve())
