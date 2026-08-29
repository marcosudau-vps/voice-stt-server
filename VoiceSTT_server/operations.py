"""Operational helpers for model discovery, audit logging, and runtime config."""

import json
import os
import sys
import threading
import uuid
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path

from VoiceSTT_server.event_logging import ChannelLogManager

FASTER_MODEL_ROOT_ENV = "VOICESTT_FASTER_WHISPER_MODEL_ROOT"
KROKO_MODEL_ROOT_ENV = "VOICESTT_KROKO_MODEL_ROOT"

AUDIT_EVENT_MESSAGES_DE = {
    "authentication.failed": "Authentifizierung fehlgeschlagen",
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
    "session.accepted": "Sitzung angenommen",
    "session.closed": "Sitzung beendet",
    "session.rejected": "Sitzung abgelehnt",
}

PERFORMANCE_EVENT_MESSAGES_DE = {
    "http.completed": "HTTP-Transkription abgeschlossen",
    "http.first_text": "Erster HTTP-Text ausgegeben",
    "inference.completed": "Inferenz abgeschlossen",
    "models.load_failed": "Modellladen fehlgeschlagen",
    "models.loaded": "Modelle geladen",
    "models.switched": "Modelle gewechselt",
    "models.unloaded": "Modelle aus dem RAM entladen",
    "queue.limit_reached": "Scheduler-Limit erreicht",
    "stream.final_text": "Finaler Streamtext ausgegeben",
    "stream.first_text": "Erster Streamtext ausgegeben",
    "transcription.performance_summary": "Transkriptionsleistung zusammengefasst",
    "transcription.realtime_emitted": "Realtime-Transkript ausgegeben",
}

#: Shared module-wide write lock for every RuntimeConfigStore instance, so
#: independent instances writing the same runtime config path serialize their
#: read-modify-write and never lose a top-level section (AP-SRV-050 prompt 25).
_RUNTIME_CONFIG_WRITE_LOCK = threading.RLock()


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
    """Legacy-shaped adapter over the one AP-SRV-060 wake-word catalog.

    A thin, id-based lookup for the v1/legacy paths that still need a
    ``(id, label, path, ...)`` shape instead of an admitted
    :class:`~VoiceSTT.core.wakeword_catalog.WakeWordSelection`. It never scans
    a directory and never picks an implicit default - both were properties of
    the retired ``openwakeword_catalog`` scanner, not of the canonical
    manifest. Resolution is always per requested id, so a caller can tell
    exactly which of several requested ids failed.
    """

    def __init__(self, catalog_authority=None):
        self._catalog = catalog_authority

    def _snapshot(self):
        return self._catalog.snapshot() if self._catalog is not None else None

    def openwakeword_models(self, framework="onnx"):
        snapshot = self._snapshot()
        if snapshot is None:
            return []
        preferred = str(framework or "onnx").strip().lower()
        result = []
        for entry in snapshot.entries:
            if not entry.available:
                continue
            artifact = entry.artifact_for(preferred)
            if artifact is None:
                continue
            result.append(self._entry_dict(entry, artifact, preferred))
        return sorted(result, key=lambda item: item["label"].lower())

    def resolve_openwakeword(self, model_ids, framework="onnx"):
        if isinstance(model_ids, str):
            requested = [
                value.strip() for value in model_ids.split(",") if value.strip()
            ]
        else:
            requested = [
                str(value).strip() for value in (model_ids or ()) if str(value).strip()
            ]
        if not requested:
            return [], []

        snapshot = self._snapshot()
        preferred = str(framework or "onnx").strip().lower()
        resolved = []
        missing = []
        for token in requested:
            canonical_id = snapshot.resolve(token) if snapshot else None
            entry = snapshot.get(canonical_id) if canonical_id else None
            artifact = (
                entry.artifact_for(preferred)
                if entry is not None and preferred in entry.healthy_backends
                else None
            )
            if entry is None or not entry.available or artifact is None:
                missing.append(token)
            else:
                resolved.append(self._entry_dict(entry, artifact, preferred))
        return resolved, missing

    def catalog(self, framework="onnx"):
        return {"openwakeword": self.openwakeword_models(framework)}

    @staticmethod
    def _entry_dict(entry, artifact, preferred):
        return {
            "id": entry.id,
            "label": entry.display_name,
            "backend": "openwakeword",
            "availableFormats": sorted(entry.declared_backends),
            "default": False,
            "source": "models.json",
            "path": str(artifact.path),
            "paths": {
                backend: str(entry.artifacts[backend].path)
                for backend in entry.declared_backends
            },
        }


class AuditLogManager:
    """Compatibility facade for structured audit events and audio archives."""

    def __init__(self, settings, event_hub=None):
        self._manager = ChannelLogManager(
            settings,
            "audit",
            AUDIT_EVENT_MESSAGES_DE,
            event_hub,
        )
        self.configure(settings)

    @property
    def hub(self):
        return self._manager.hub

    def configure(self, settings, configure_hub=True):
        if configure_hub:
            self._manager.configure(settings)
        self.save_audio = bool(settings.save_audio_files)
        self.audio_dir = Path(settings.audio_log_dir or "logs/audio").expanduser()
        if self.save_audio:
            self.audio_dir.mkdir(parents=True, exist_ok=True)

    def event(self, event, **fields):
        return self._manager.event(event, **fields)

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
        self._manager.close()


class PerformanceLogManager:
    """Compatibility facade for operational performance events."""

    def __init__(self, settings, event_hub=None):
        self._enabled = True
        self._manager = ChannelLogManager(
            settings,
            "performance",
            PERFORMANCE_EVENT_MESSAGES_DE,
            event_hub,
        )
        self.configure(settings, configure_hub=False)

    @property
    def hub(self):
        return self._manager.hub

    def configure(self, settings, configure_hub=True):
        if configure_hub:
            self._manager.configure(settings)
        self._enabled = bool(
            getattr(settings, "performance_logging_enabled", True)
        )

    def event(self, event, **fields):
        if not self._enabled:
            return None
        return self._manager.event(event, **fields)

    def close(self):
        self._manager.close()


class RuntimeConfigStore:
    """Persist non-secret runtime settings as JSON with atomic replacement.

    The runtime config document is a coexistence format (AP-SRV-050 prompt
    22-25): the legacy ``settings`` section, the additive
    ``settingsControlOverlay``/``settingsRevision`` sections and every unknown
    compatible top-level field live in the *same* file and must never clobber
    one another. Both write families therefore read-modify-write the whole
    document under one shared lock and replace it atomically via
    ``temp file -> os.replace``. The lock is module-wide, so even separate
    instances writing the same path serialize correctly and no section is lost.
    """

    #: Binding top-level overlay name of the AP-SRV-050 server defaults.
    OVERLAY_FIELD = "settingsControlOverlay"
    #: Binding top-level revision name of the server settings revision.
    REVISION_FIELD = "settingsRevision"

    def __init__(self, path=None):
        self.path = Path(path).expanduser() if path else None
        self._lock = _RUNTIME_CONFIG_WRITE_LOCK

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
        legacy = {
            "version": 1,
            "updatedAt": _utc_now(),
            "settings": {
                name: values[name]
                for name in sorted(allowed_names)
                if name in values
            },
        }
        return self._write_merged(legacy)

    def save_settings_control(self, overlay, revision):
        """Atomically adds/updates the control overlay and its revision.

        The legacy ``settings`` section and every other compatible top-level
        field are preserved untouched.
        """
        if self.path is None:
            return None
        overlay = dict(overlay or {})
        revision = int(revision) if not isinstance(revision, bool) else 0
        if revision < 0:
            revision = 0
        fields = {
            "version": 1,
            "updatedAt": _utc_now(),
            self.OVERLAY_FIELD: overlay,
            self.REVISION_FIELD: revision,
        }
        return self._write_merged(fields)

    def load_control(self):
        """``(overlay, revision)`` of the persisted settings control plane.

        AP-SRV-050 C2 F4: a *present but invalid* section fails fast instead of
        being silently normalized. Missing sections are the only case that
        defaults to ``({}, 0)``.
        """
        if self.path is None or not self.path.is_file():
            return {}, 0
        try:
            payload = json.loads(
                self.path.read_text(encoding="utf-8", errors="replace")
            )
        except (OSError, ValueError):
            raise ValueError(
                "Invalid settingsControlOverlay: Die Laufzeitkonfiguration "
                "ist kein lesbares JSON."
            )
        if not isinstance(payload, dict):
            raise ValueError(
                "Invalid settingsControlOverlay: Die Laufzeitkonfiguration "
                "ist kein Objekt."
            )
        if self.OVERLAY_FIELD in payload:
            overlay = payload[self.OVERLAY_FIELD]
            if not isinstance(overlay, dict):
                raise ValueError(
                    "Invalid settingsControlOverlay: muss ein Objekt sein."
                )
        else:
            overlay = {}
        if self.REVISION_FIELD in payload:
            revision = payload[self.REVISION_FIELD]
            if isinstance(revision, bool) or not isinstance(revision, int):
                raise ValueError(
                    "Invalid settingsControlOverlay: settingsRevision muss "
                    "eine nicht negative Ganzzahl sein."
                )
            if revision < 0:
                raise ValueError(
                    "Invalid settingsControlOverlay: settingsRevision darf "
                    "nicht negativ sein."
                )
        else:
            revision = 0
        return overlay, revision

    def _write_merged(self, new_fields):
        """Read-modify-write the whole document under the shared lock."""
        if self.path is None:
            return None
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(
            f".{self.path.name}.{uuid.uuid4().hex}.tmp"
        )
        try:
            with self._lock:
                # The read happens *inside* the shared lock, so two read-modify-
                # write transactions cannot both start from the same stale payload.
                payload = self._read_payload()
                payload.update(dict(new_fields))
                temporary.write_text(
                    json.dumps(payload, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
                os.replace(temporary, self.path)
            return str(self.path.resolve())
        except Exception:
            # A failed write/replace leaves the original file untouched and
            # removes the temporary file (AP-SRV-050 C2 F5).
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            raise

    def _read_payload(self):
        if self.path is None or not self.path.is_file():
            return {}
        try:
            payload = json.loads(
                self.path.read_text(encoding="utf-8", errors="replace")
            )
        except (OSError, ValueError):
            return {}
        return payload if isinstance(payload, dict) else {}
