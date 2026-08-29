import argparse
import asyncio
import collections
import datetime
import gc
import io
import json
import logging
import math
import os
import secrets
import threading
import time
import uuid
import wave
from dataclasses import asdict, dataclass, field, fields, replace
from pathlib import Path
from typing import Any, Callable, Deque, Dict, List, Optional, Tuple

from VoiceSTT_server.openai_compat import (
    OpenAIRequestError,
    format_caption_response,
    format_json_response,
    openai_error,
    parse_transcription_form,
    sse_data,
    validate_audio_filename,
)
from VoiceSTT_server.event_logging import (
    StructuredEventHub,
    apply_process_log_level,
    resolve_calendar_timezone,
    resolve_log_level,
)
from api_fastapi_server.activation import (
    ActivationController,
    ActivationTimingPolicy,
    DEFAULT_CLOSING_RECOVERY_TIMEOUT,
    DEFAULT_FOLLOWUP_TIMEOUT,
    DEFAULT_INITIAL_SPEECH_TIMEOUT,
    DEFAULT_SEGMENT_WATCHDOG_INITIAL,
    DEFAULT_SEGMENT_WATCHDOG_REFRESH,
    DEFAULT_SEGMENT_WATCHDOG_WARNING,
)
from api_fastapi_server.activation_commands import (
    ACTIVATE,
    ACTIVATION_ACTIONS,
    CANCEL,
    CONFLICT,
    CommandReplayCache,
    FINISH,
    REFRESH,
    REPLAY,
    prepare_activation_command,
)
from api_fastapi_server.segment_ledger import (
    LedgerUpdate,
    SegmentContext,
    SegmentLedger,
)
from api_fastapi_server.protocol_v2 import schema as protocol_v2_schema
from api_fastapi_server.protocol_v2.connection import ProtocolV2Connection
from api_fastapi_server import settings_control as settings_control_module
from api_fastapi_server.wake_admission import (
    WakeActivationOutcome,
    WakeAdmissionCoordinator,
)
from VoiceSTT.core import wakeword_catalog as wakeword_catalog_module
from VoiceSTT.core.wake_detection import (
    WakeAttemptPolicy,
    WakeDetectionEvaluator,
)
from VoiceSTT_server.operations import (
    AuditLogManager,
    LocalModelRegistry,
    PerformanceLogManager,
    RuntimeConfigStore,
    WakeWordRegistry,
    process_memory_snapshot,
)

try:
    import numpy as np
except ModuleNotFoundError as exc:  # pragma: no cover - numpy is a core dependency
        raise RuntimeError(
            "Der FastAPI-Server benötigt NumPy. Installiere zuerst die Projektabhängigkeiten."
        ) from exc

try:
    from .protocol import (
        AudioPacketError,
        decode_audio_packet,
        normalize_engine_name,
        parse_json_object,
        require_positive_int,
    )
except ImportError:
    from protocol import (
        AudioPacketError,
        decode_audio_packet,
        normalize_engine_name,
        parse_json_object,
        require_positive_int,
    )


LOGGER = logging.getLogger("voicestt.fastapi")
STATIC_DIR = Path(__file__).resolve().parent / "static"
INDEX_PATH = STATIC_DIR / "index.html"
WARMUP_AUDIO_PATH = (
    Path(__file__).resolve().parents[1]
    / "VoiceSTT"
    / "assets"
    / "warmup_audio.wav"
)
SERVER_SAMPLE_RATE = 16000
INT16_MAX_ABS_VALUE = 32768.0
LOG_STREAM_KEEPALIVE_SECONDS = 30.0

BASE_TUNING_DEFAULTS = {
    "beam_size": 5,
    "beam_size_realtime": 3,
    "batch_size": 16,
    "realtime_batch_size": 16,
    "realtime_processing_pause": 0.02,
    "min_length_of_recording": 0.2,
    "post_speech_silence_duration": 0.55,
    "early_transcription_on_silence": 0.2,
}

TUNING_PROFILES = {
    "custom": {
        "description": "Explizite CLI-/Standardwerte verwenden.",
        "settings": {},
    },
    "parakeet-low-latency": {
        "description": "Parakeet-Profil für häufige Zwischenergebnisse.",
        "settings": {
            "batch_size": 1,
            "realtime_batch_size": 1,
            "realtime_processing_pause": 0.04,
            "min_length_of_recording": 0.18,
            "post_speech_silence_duration": 0.45,
            "early_transcription_on_silence": 0.15,
        },
    },
    "parakeet-balanced": {
        "description": "Parakeet-Profil mit ausgewogenem Verhältnis aus Latenz und finaler Stabilität.",
        "settings": {
            "batch_size": 8,
            "realtime_batch_size": 4,
            "realtime_processing_pause": 0.06,
            "min_length_of_recording": 0.2,
            "post_speech_silence_duration": 0.55,
            "early_transcription_on_silence": 0.2,
        },
    },
    "parakeet-accurate-final": {
        "description": "Parakeet-Profil für ruhigere Segmentierung und höhere finale Qualität.",
        "settings": {
            "batch_size": 16,
            "realtime_batch_size": 8,
            "realtime_processing_pause": 0.1,
            "min_length_of_recording": 0.3,
            "post_speech_silence_duration": 0.7,
            "early_transcription_on_silence": 0.35,
        },
    },
}

ACTIVE_RUNTIME_SETTINGS = {
    "log_calendar_timezone",
    "log_level",
    "log_live_enabled",
    "max_active_speakers",
    "max_audio_packet_bytes",
    "max_final_queue_depth_per_session",
    "max_global_inference_queue_depth",
    "max_realtime_queue_age_ms",
    "max_sessions",
    "allow_two_medium_models",
    "model_idle_timeout_seconds",
    "model_idle_unload_enabled",
    "model_memory_policy_enabled",
    "request_log_backup_count",
    "request_log_max_bytes",
    "request_log_retention_days",
    "request_log_stdout",
    "request_log_transcripts",
    "request_logging_enabled",
    "performance_log_backup_count",
    "performance_log_max_bytes",
    "performance_log_mirror_enabled",
    "performance_log_retention_days",
    "performance_log_stdout",
    "performance_logging_enabled",
    "realtime_log_detail",
    "save_audio_files",
    "system_event_log_backup_count",
    "system_event_log_max_bytes",
    "system_event_log_retention_days",
    "system_event_log_stdout",
    "system_event_logging_enabled",
    "transcription_log_backup_count",
    "transcription_log_max_bytes",
    "transcription_log_retention_days",
    "transcription_log_stdout",
    "transcription_logging_enabled",
    "transcript_log_mode",
    "realtime_degradation_threshold_ms",
}

NEW_SESSION_RUNTIME_SETTINGS = {
    "audio_queue_size",
    "early_transcription_on_silence",
    "initial_prompt",
    "initial_prompt_realtime",
    "max_audio_queue_seconds_per_session",
    "min_gap_between_recordings",
    "min_length_of_recording",
    "openwakeword_inference_framework",
    "openwakeword_model_paths",
    "post_speech_silence_duration",
    "pre_recording_buffer_duration",
    "realtime_batch_size",
    "realtime_boundary_detector_sensitivity",
    "realtime_boundary_followup_delays",
    "realtime_callback",
    "realtime_max_audio_seconds",
    "realtime_min_audio_seconds",
    "realtime_processing_pause",
    "realtime_transcription_use_syllable_boundaries",
    "silero_sensitivity",
    "vad_energy_threshold",
    "vad_filter",
    "wake_word_activation_delay",
    "wake_word_buffer_duration",
    "wake_word_followup_window",
    "wake_word_timeout",
    "wake_words",
    "wake_words_sensitivity",
    "wakeword_backend",
    "webrtc_sensitivity",
}

STARTUP_ONLY_SETTINGS = {
    "admin_api_key",
    "batch_size",
    "beam_size",
    "beam_size_realtime",
    "compute_type",
    "data_root_path",
    "device",
    "download_root",
    "host",
    "language",
    "model",
    "model_warmup",
    "normalize_audio",
    "port",
    "realtime_model",
    "realtime_transcription_engine",
    "realtime_transcription_engine_options",
    "transcription_engine",
    "transcription_engine_options",
    "tuning_description",
    "tuning_profile",
    "use_main_model_for_realtime",
    "openai_api_enabled",
    "openai_api_key",
    "openai_max_file_bytes",
    "openai_model_aliases",
    "event_log_queue_size",
    "event_store_enabled",
}

DERIVED_DATA_PATH_SETTINGS = {
    "audio_log_dir",
    "event_store_path",
    "performance_log_path",
    "request_log_path",
    "runtime_config_path",
    "system_event_log_path",
    "transcription_log_path",
}

INT_SETTINGS = {
    "audio_queue_size",
    "batch_size",
    "beam_size",
    "beam_size_realtime",
    "max_active_speakers",
    "max_audio_packet_bytes",
    "max_final_queue_depth_per_session",
    "max_global_inference_queue_depth",
    "max_realtime_queue_age_ms",
    "max_sessions",
    "port",
    "realtime_batch_size",
    "realtime_degradation_threshold_ms",
    "webrtc_sensitivity",
    "openai_max_file_bytes",
    "request_log_backup_count",
    "request_log_max_bytes",
    "request_log_retention_days",
    "performance_log_backup_count",
    "performance_log_max_bytes",
    "performance_log_retention_days",
    "system_event_log_backup_count",
    "system_event_log_max_bytes",
    "system_event_log_retention_days",
    "transcription_log_backup_count",
    "transcription_log_max_bytes",
    "transcription_log_retention_days",
    "event_log_queue_size",
}

FLOAT_SETTINGS = {
    "early_transcription_on_silence",
    "max_audio_queue_seconds_per_session",
    "min_gap_between_recordings",
    "min_length_of_recording",
    "post_speech_silence_duration",
    "pre_recording_buffer_duration",
    "realtime_boundary_detector_sensitivity",
    "realtime_max_audio_seconds",
    "realtime_min_audio_seconds",
    "realtime_processing_pause",
    "silero_sensitivity",
    "vad_energy_threshold",
    "wake_word_activation_delay",
    "wake_word_buffer_duration",
    "wake_word_followup_window",
    "wake_word_timeout",
    "wake_words_sensitivity",
    "model_idle_timeout_seconds",
}

BOOL_SETTINGS = {
    "allow_two_medium_models",
    "model_warmup",
    "normalize_audio",
    "realtime_transcription_use_syllable_boundaries",
    "use_main_model_for_realtime",
    "vad_filter",
    "openai_api_enabled",
    "request_log_stdout",
    "request_log_transcripts",
    "request_logging_enabled",
    "performance_log_mirror_enabled",
    "performance_log_stdout",
    "performance_logging_enabled",
    "system_event_log_stdout",
    "system_event_logging_enabled",
    "transcription_log_stdout",
    "transcription_logging_enabled",
    "event_store_enabled",
    "log_live_enabled",
    "save_audio_files",
    "model_idle_unload_enabled",
    "model_memory_policy_enabled",
}

OPTIONAL_STRING_SETTINGS = {
    "admin_api_key",
    "data_root_path",
    "download_root",
    "initial_prompt",
    "initial_prompt_realtime",
    "openwakeword_model_paths",
    "realtime_transcription_engine",
    "openai_api_key",
}

DICT_SETTINGS = {
    "realtime_transcription_engine_options",
    "transcription_engine_options",
    "openai_model_aliases",
}

TUPLE_FLOAT_SETTINGS = {"realtime_boundary_followup_delays"}


@dataclass
class ServerSettings:
    host: str = "0.0.0.0"
    port: int = 8010
    tuning_profile: str = "custom"
    tuning_description: str = TUNING_PROFILES["custom"]["description"]
    model: str = "small"
    realtime_model: str = "Kroko-DE-Community-64-L-Streaming-001.data"
    language: str = "de"
    transcription_engine: str = "faster_whisper"
    realtime_transcription_engine: Optional[str] = "kroko_onnx"
    transcription_engine_options: Optional[Dict[str, Any]] = None
    realtime_transcription_engine_options: Optional[Dict[str, Any]] = None
    download_root: Optional[str] = None
    compute_type: str = "int8"
    device: str = "cpu"
    beam_size: int = 5
    beam_size_realtime: int = 3
    batch_size: int = 16
    realtime_batch_size: int = 16
    vad_filter: bool = True
    normalize_audio: bool = False
    realtime_callback: str = "update"
    min_length_of_recording: float = 0.2
    min_gap_between_recordings: float = 0.0
    post_speech_silence_duration: float = 0.55
    silero_sensitivity: float = 0.05
    webrtc_sensitivity: int = 3
    realtime_processing_pause: float = 0.02
    realtime_transcription_use_syllable_boundaries: bool = False
    realtime_boundary_detector_sensitivity: float = 0.6
    realtime_boundary_followup_delays: Tuple[float, ...] = (0.05, 0.2)
    early_transcription_on_silence: float = 0.2
    initial_prompt: Optional[str] = None
    initial_prompt_realtime: Optional[str] = None
    wakeword_backend: str = ""
    openwakeword_model_paths: Optional[str] = None
    openwakeword_inference_framework: str = "onnx"
    wake_words: str = ""
    wake_words_sensitivity: float = 0.5
    wake_word_activation_delay: float = 0.0
    wake_word_timeout: float = 5.0
    wake_word_buffer_duration: float = 0.1
    wake_word_followup_window: float = 0.0
    use_main_model_for_realtime: bool = False
    audio_queue_size: int = 128
    max_audio_packet_bytes: int = 512 * 1024
    log_level: str = "INFO"
    data_root_path: Optional[str] = None
    request_logging_enabled: bool = True
    request_log_stdout: bool = True
    request_log_path: str = field(init=False)
    request_log_transcripts: bool = True
    transcript_log_mode: Optional[str] = None
    request_log_max_bytes: int = 10 * 1024 * 1024
    request_log_backup_count: int = 12
    request_log_retention_days: int = 0
    performance_logging_enabled: bool = True
    performance_log_mirror_enabled: bool = True
    performance_log_stdout: bool = True
    performance_log_path: str = field(init=False)
    performance_log_max_bytes: int = 10 * 1024 * 1024
    performance_log_backup_count: int = 12
    performance_log_retention_days: int = 0
    transcription_logging_enabled: bool = True
    transcription_log_stdout: bool = False
    transcription_log_path: str = field(init=False)
    transcription_log_max_bytes: int = 10 * 1024 * 1024
    transcription_log_backup_count: int = 12
    transcription_log_retention_days: int = 0
    system_event_logging_enabled: bool = True
    system_event_log_stdout: bool = False
    system_event_log_path: str = field(init=False)
    system_event_log_max_bytes: int = 10 * 1024 * 1024
    system_event_log_backup_count: int = 12
    system_event_log_retention_days: int = 0
    log_calendar_timezone: str = "Europe/Berlin"
    realtime_log_detail: str = "events"
    event_store_enabled: bool = True
    event_store_path: str = field(init=False)
    event_log_queue_size: int = 10000
    log_live_enabled: bool = True
    save_audio_files: bool = False
    audio_log_dir: str = field(init=False)
    max_sessions: int = 4
    max_active_speakers: int = 4
    max_audio_queue_seconds_per_session: float = 30.0
    pre_recording_buffer_duration: float = 0.75
    max_realtime_queue_age_ms: int = 1500
    max_final_queue_depth_per_session: int = 8
    max_global_inference_queue_depth: int = 64
    realtime_degradation_threshold_ms: int = 1500
    realtime_min_audio_seconds: float = 0.25
    realtime_max_audio_seconds: float = 20.0
    vad_energy_threshold: float = 250.0
    model_warmup: bool = True
    model_idle_unload_enabled: bool = True
    model_idle_timeout_seconds: float = 3600.0
    model_memory_policy_enabled: bool = True
    allow_two_medium_models: bool = True
    openai_api_enabled: bool = True
    openai_api_key: Optional[str] = None
    admin_api_key: Optional[str] = None
    openai_model_aliases: Optional[Dict[str, str]] = field(default_factory=lambda: {
        "whisper-1": "final",
        "fast": "realtime",
    })
    openai_max_file_bytes: int = 25 * 1024 * 1024
    runtime_config_path: Optional[str] = field(init=False)

    def __post_init__(self):
        root = Path(self.data_root_path).expanduser() if self.data_root_path else None
        logs_root = root / "logs" if root is not None else Path("logs")
        self.request_log_path = str(logs_root / "audit")
        self.performance_log_path = str(logs_root / "performance")
        self.transcription_log_path = str(logs_root / "transcription")
        self.system_event_log_path = str(logs_root / "system")
        self.event_store_path = str(logs_root / "voicestt-events.sqlite3")
        self.audio_log_dir = str(logs_root / "audio")
        self.runtime_config_path = (
            str(root / "config" / "runtime.json")
            if root is not None
            else None
        )
        self.realtime_log_detail = str(
            self.realtime_log_detail or ""
        ).strip().lower()
        if self.realtime_log_detail not in {"off", "summary", "events"}:
            raise ValueError(
                "realtime_log_detail muss off, summary oder events sein"
            )
        if self.log_live_enabled and not self.event_store_enabled:
            raise ValueError(
                "log_live_enabled erfordert event_store_enabled"
            )

    def public_dict(self):
        data = asdict(self)
        data.pop("transcription_engine_options", None)
        data.pop("realtime_transcription_engine_options", None)
        data.pop("openai_api_key", None)
        data.pop("admin_api_key", None)
        data["wake_word_enabled"] = self.wake_word_enabled()
        return data

    def wake_word_enabled(self):
        return bool(str(self.wakeword_backend or "").strip() and str(self.wake_words or "").strip())


SESSION_WAKE_WORD_QUERY_FIELDS = (
    "wakeWordBackend",
    "wakeWords",
    "wakeWordInferenceFramework",
    "wakeWordSensitivity",
    "wakeWordActivationDelay",
    "wakeWordTimeout",
    "wakeWordBufferDuration",
    "wakeWordFollowupWindow",
)

SESSION_WAKE_WORD_TUNING_FIELDS = {
    "wakeWordSensitivity": ("wake_words_sensitivity", 0.0, 1.0),
    "wakeWordActivationDelay": ("wake_word_activation_delay", 0.0, 3600.0),
    "wakeWordTimeout": ("wake_word_timeout", 0.0, 3600.0),
    "wakeWordBufferDuration": ("wake_word_buffer_duration", 0.0, 60.0),
    "wakeWordFollowupWindow": ("wake_word_followup_window", 0.0, 3600.0),
}

OPENWAKEWORD_SESSION_BACKENDS = {
    "openwakeword",
    "open_wakeword",
    "oww",
}


class SessionConfigurationError(ValueError):
    def __init__(self, code, message, **details):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details

    def payload(self):
        payload = {
            "type": "error",
            "where": "session_config",
            "code": self.code,
            "message": self.message,
        }
        payload.update(self.details)
        return payload


@dataclass(frozen=True)
class SessionWakeWordRequest:
    enabled: Optional[bool] = None
    values: Tuple[Tuple[str, str], ...] = ()
    ignored_fields: Tuple[str, ...] = ()
    fallbacks: Tuple[Dict[str, Any], ...] = ()
    warnings: Tuple[Dict[str, Any], ...] = ()
    #: AP-SRV-060: an already admitted
    #: :class:`~VoiceSTT.core.wakeword_catalog.WakeWordSelection`. When it is
    #: present the v1 name resolution and *all* of its fallbacks are bypassed:
    #: the v2 admission is atomic, so a session either gets exactly the models
    #: it asked for or no session at all.
    selection: Any = None

    def get(self, name, default=None):
        return dict(self.values).get(name, default)

    @property
    def provided_fields(self):
        return tuple(name for name, _value in self.values)


@dataclass(frozen=True)
class ResolvedSessionWakeWordConfig:
    requested_enabled: Optional[bool]
    effective_enabled: bool
    effective_backend: str
    effective_wake_words: Tuple[str, ...]
    source: str
    fallbacks: Tuple[Dict[str, Any], ...] = ()
    ignored_fields: Tuple[str, ...] = ()
    warnings: Tuple[Dict[str, Any], ...] = ()
    requested_fields: Tuple[str, ...] = ()
    #: AP-SRV-060 internal artifact projection of the admitted selection. It
    #: carries filesystem paths and therefore never appears in ``public_dict``.
    wake_word_selection: Any = None

    def public_dict(self):
        return {
            "version": 1,
            "requestedWakeWordEnabled": self.requested_enabled,
            "effectiveWakeWordEnabled": self.effective_enabled,
            "effectiveWakeWordBackend": self.effective_backend,
            "effectiveWakeWords": list(self.effective_wake_words),
            "source": self.source,
            "fallbacks": [dict(item) for item in self.fallbacks],
            "ignoredFields": list(self.ignored_fields),
            "warnings": [dict(item) for item in self.warnings],
            "requestedFields": list(self.requested_fields),
        }


def parse_session_wake_word_query(query_params):
    enabled_values = list(query_params.getlist("wakeWordEnabled"))
    if len(enabled_values) > 1:
        raise SessionConfigurationError(
            "duplicate_wake_word_enabled",
            "wakeWordEnabled darf nur einmal angegeben werden.",
        )

    enabled = None
    fallbacks = []
    warnings = []
    if enabled_values:
        normalized = str(enabled_values[0]).strip().lower()
        if normalized in {"null", "inherit"}:
            enabled = None
        elif normalized == "true":
            enabled = True
        elif normalized == "false":
            enabled = False
        else:
            fallbacks.append({
                "field": "wakeWordEnabled",
                "source": "server",
                "value": None,
                "reason": "invalid_value",
            })
            warnings.append({
                "code": "session_config_value_fallback",
                "field": "wakeWordEnabled",
                "message": (
                    "wakeWordEnabled war ungültig; die Serverkonfiguration "
                    "wurde übernommen."
                ),
            })

    provided = []
    for name in SESSION_WAKE_WORD_QUERY_FIELDS:
        values = list(query_params.getlist(name))
        if not values:
            continue
        if enabled is True and len(values) > 1:
            raise SessionConfigurationError(
                "duplicate_session_config_field",
                f"{name} darf nur einmal angegeben werden.",
                field=name,
            )
        provided.append((name, str(values[-1])))

    if enabled is not True:
        return SessionWakeWordRequest(
            enabled=enabled,
            values=tuple(provided),
            ignored_fields=tuple(name for name, _value in provided),
            fallbacks=tuple(fallbacks),
            warnings=tuple(warnings),
        )

    backend = dict(provided).get("wakeWordBackend")
    if backend is not None:
        normalized_backend = backend.strip().lower().replace("-", "_")
        if normalized_backend not in OPENWAKEWORD_SESSION_BACKENDS:
            fallbacks.append({
                "field": "wakeWordBackend",
                "source": "server",
                "value": "openwakeword",
                "reason": "unsupported_value",
            })
            warnings.append({
                "code": "session_config_value_fallback",
                "field": "wakeWordBackend",
                "message": (
                    "wakeWordBackend wird sessionlokal nicht unterstützt; "
                    "OpenWakeWord wurde verwendet."
                ),
            })
    framework = dict(provided).get("wakeWordInferenceFramework")
    if framework is not None:
        normalized_framework = framework.strip().lower()
        if normalized_framework not in {"onnx", "tflite"}:
            fallbacks.append({
                "field": "wakeWordInferenceFramework",
                "source": "server",
                "value": None,
                "reason": "unsupported_value",
            })
            warnings.append({
                "code": "session_config_value_fallback",
                "field": "wakeWordInferenceFramework",
                "message": (
                    "wakeWordInferenceFramework war ungültig; die "
                    "Serverkonfiguration wurde übernommen."
                ),
            })
    return SessionWakeWordRequest(
        enabled=True,
        values=tuple(provided),
        fallbacks=tuple(fallbacks),
        warnings=tuple(warnings),
    )


def _split_wake_word_ids(value):
    return tuple(
        item.strip()
        for item in str(value or "").split(",")
        if item.strip()
    )


def resolve_session_wake_word_config(base_settings, request, registry):
    settings = replace(base_settings)
    inherited_words = _split_wake_word_ids(settings.wake_words)
    fallbacks = [dict(item) for item in request.fallbacks]
    warnings = [dict(item) for item in request.warnings]

    selection = getattr(request, "selection", None)
    if selection is not None:
        # AP-SRV-060 v2 admission. The catalog authority already validated the
        # whole selection atomically, so there is deliberately no name
        # resolution, no default model and no fallback profile here: exactly
        # the admitted classifiers are configured, in canonical id order.
        settings.wakeword_backend = "openwakeword"
        settings.wake_words = ",".join(selection.wake_word_ids)
        settings.openwakeword_model_paths = ",".join(selection.model_paths)
        # AP-SRV-060 C3: the admission already chose the one common
        # inference backend for the whole selection.
        settings.openwakeword_inference_framework = selection.backend
        return settings, ResolvedSessionWakeWordConfig(
            requested_enabled=True,
            effective_enabled=True,
            effective_backend="openwakeword",
            effective_wake_words=tuple(selection.wake_word_ids),
            source="session",
            ignored_fields=request.ignored_fields,
            fallbacks=(),
            warnings=tuple(warnings),
            requested_fields=request.provided_fields,
            wake_word_selection=selection,
        )
    for fallback in fallbacks:
        if fallback.get("field") == "wakeWordInferenceFramework":
            fallback["value"] = (
                settings.openwakeword_inference_framework
            )

    if request.enabled is None:
        return settings, ResolvedSessionWakeWordConfig(
            requested_enabled=None,
            effective_enabled=settings.wake_word_enabled(),
            effective_backend=str(settings.wakeword_backend or ""),
            effective_wake_words=inherited_words,
            source="server",
            ignored_fields=request.ignored_fields,
            fallbacks=tuple(fallbacks),
            warnings=tuple(warnings),
            requested_fields=request.provided_fields,
        )

    if request.enabled is False:
        settings.wakeword_backend = ""
        settings.wake_words = ""
        settings.openwakeword_model_paths = None
        return settings, ResolvedSessionWakeWordConfig(
            requested_enabled=False,
            effective_enabled=False,
            effective_backend="",
            effective_wake_words=(),
            source="session",
            ignored_fields=request.ignored_fields,
            fallbacks=tuple(fallbacks),
            warnings=tuple(warnings),
            requested_fields=request.provided_fields,
        )

    requested_backend = request.get("wakeWordBackend")
    requested_words = _split_wake_word_ids(request.get("wakeWords"))
    requested_framework = str(
        request.get("wakeWordInferenceFramework") or ""
    ).strip().lower()
    if requested_framework in {"onnx", "tflite"}:
        settings.openwakeword_inference_framework = requested_framework
    normalized_requested_backend = (
        str(requested_backend or "")
        .strip()
        .lower()
        .replace("-", "_")
    )
    valid_backend_override = (
        normalized_requested_backend in OPENWAKEWORD_SESSION_BACKENDS
    )
    inherited_backend = (
        str(settings.wakeword_backend or "")
        .strip()
        .lower()
        .replace("-", "_")
    )
    can_inherit_complete_openwakeword = (
        not valid_backend_override
        and not requested_words
        and requested_framework not in {"onnx", "tflite"}
        and inherited_backend in OPENWAKEWORD_SESSION_BACKENDS
        and settings.wake_word_enabled()
    )

    source = "server"
    if not can_inherit_complete_openwakeword:
        requested_model_ids = (
            requested_words
            or (
                inherited_words
                if requested_framework in {"onnx", "tflite"}
                else None
            )
        )
        resolved, missing = registry.resolve_openwakeword(
            requested_model_ids,
            settings.openwakeword_model_paths,
            settings.openwakeword_inference_framework,
        )
        if requested_words and missing:
            fallback_source = None
            if (
                inherited_backend in OPENWAKEWORD_SESSION_BACKENDS
                and base_settings.wake_word_enabled()
            ):
                settings.wakeword_backend = "openwakeword"
                settings.wake_words = base_settings.wake_words
                settings.openwakeword_model_paths = (
                    base_settings.openwakeword_model_paths
                )
                inherited_words = _split_wake_word_ids(
                    base_settings.wake_words
                )
                fallback_source = "server"
            else:
                default_resolved, default_missing = (
                    registry.resolve_openwakeword(
                        None,
                        settings.openwakeword_model_paths,
                        settings.openwakeword_inference_framework,
                    )
                )
                if default_resolved and not default_missing:
                    settings.wakeword_backend = "openwakeword"
                    settings.wake_words = ",".join(
                        entry["id"] for entry in default_resolved
                    )
                    settings.openwakeword_model_paths = ",".join(
                        entry["path"] for entry in default_resolved
                    )
                    inherited_words = tuple(
                        entry["id"] for entry in default_resolved
                    )
                    fallback_source = "model_catalog"
            if fallback_source is None:
                raise SessionConfigurationError(
                    "wake_word_fallback_unavailable",
                    "Das angeforderte Wake Word ist ungültig und es ist kein Fallback-Profil verfügbar.",
                    unavailableWakeWords=missing,
                )
            fallbacks.append({
                "field": "wakeWords",
                "source": fallback_source,
                "value": list(inherited_words),
                "reason": "unknown_value",
            })
            warnings.append({
                "code": "session_config_value_fallback",
                "field": "wakeWords",
                "message": (
                    "Mindestens ein angefordertes Wake Word war nicht "
                    "verfügbar; das Fallback-Profil wurde verwendet."
                ),
            })
            source = fallback_source
        elif missing or not resolved:
            raise SessionConfigurationError(
                "wake_word_default_unavailable",
                "Wake Word kann nicht aktiviert werden, weil kein verfügbares OpenWakeWord-Standardmodell gefunden wurde.",
            )
        else:
            settings.wakeword_backend = "openwakeword"
            settings.wake_words = ",".join(
                entry["id"] for entry in resolved
            )
            settings.openwakeword_model_paths = ",".join(
                entry["path"] for entry in resolved
            )
            inherited_words = tuple(entry["id"] for entry in resolved)
            source = "session" if requested_words else "model_catalog"
    else:
        settings.wakeword_backend = "openwakeword"
        inherited_words = _split_wake_word_ids(settings.wake_words)

    if requested_framework in {"onnx", "tflite"}:
        source = "session"

    for query_name, (setting_name, minimum, maximum) in (
        SESSION_WAKE_WORD_TUNING_FIELDS.items()
    ):
        raw_value = request.get(query_name)
        if raw_value is None:
            continue
        try:
            value = float(raw_value)
            if not math.isfinite(value) or not minimum <= value <= maximum:
                raise ValueError
        except (TypeError, ValueError):
            fallback_value = getattr(base_settings, setting_name)
            fallbacks.append({
                "field": query_name,
                "source": "server",
                "value": fallback_value,
                "reason": "invalid_value",
            })
            warnings.append({
                "code": "session_config_value_fallback",
                "field": query_name,
                "message": (
                    f"{query_name} war ungültig und wurde aus der "
                    "Serverkonfiguration übernommen."
                ),
            })
            continue
        setattr(settings, setting_name, value)
        source = "session"

    if not settings.wake_word_enabled():
        raise SessionConfigurationError(
            "incomplete_wake_word_profile",
            "Das aufgelöste Wake-Word-Profil ist unvollständig.",
        )

    return settings, ResolvedSessionWakeWordConfig(
        requested_enabled=True,
        effective_enabled=True,
        effective_backend="openwakeword",
        effective_wake_words=inherited_words,
        source=source,
        fallbacks=tuple(fallbacks),
        warnings=tuple(warnings),
        requested_fields=request.provided_fields,
    )


def public_session_settings(settings):
    data = settings.public_dict()
    data.pop("openwakeword_model_paths", None)
    return data


SESSION_ACTIVATION_QUERY_FIELDS = (
    "manualTriggerEnabled",
    "wakeWordTriggerEnabled",
    "initialSpeechTimeout",
    "followupTimeout",
    "segmentWatchdogInitialSeconds",
    "segmentWatchdogRefreshSeconds",
    "segmentWatchdogWarningSeconds",
    "closingRecoveryTimeoutSeconds",
)

ACTIVATION_SOURCES_PUBLIC = ("manual", "wake_word")
ACTIVATION_ACTIONS_PUBLIC = tuple(ACTIVATION_ACTIONS)


@dataclass(frozen=True)
class SessionActivationRequest:
    manual_enabled: Optional[bool] = None
    wake_word_enabled: Optional[bool] = None
    initial_speech_timeout: float = DEFAULT_INITIAL_SPEECH_TIMEOUT
    followup_timeout: float = DEFAULT_FOLLOWUP_TIMEOUT
    segment_watchdog_initial: float = DEFAULT_SEGMENT_WATCHDOG_INITIAL
    segment_watchdog_refresh: float = DEFAULT_SEGMENT_WATCHDOG_REFRESH
    segment_watchdog_warning: float = DEFAULT_SEGMENT_WATCHDOG_WARNING
    closing_recovery_timeout: float = DEFAULT_CLOSING_RECOVERY_TIMEOUT


@dataclass(frozen=True)
class ResolvedSessionActivationConfig:
    mode: str
    manual_enabled: bool
    wake_word_enabled: bool
    initial_speech_timeout: float
    followup_timeout: float
    segment_watchdog_initial: float = DEFAULT_SEGMENT_WATCHDOG_INITIAL
    segment_watchdog_refresh: float = DEFAULT_SEGMENT_WATCHDOG_REFRESH
    segment_watchdog_warning: float = DEFAULT_SEGMENT_WATCHDOG_WARNING
    closing_recovery_timeout: float = DEFAULT_CLOSING_RECOVERY_TIMEOUT
    wake_word_profile_enabled: bool = False

    def public_dict(self):
        return {
            "version": 2,
            "mode": self.mode,
            "manualTriggerEnabled": self.manual_enabled,
            "wakeWordTriggerEnabled": self.wake_word_enabled,
            # Whether wake-word *detection* is actually running for this
            # session. A client that enables the wake-word trigger without an
            # active profile can see here that no detections will arrive.
            "wakeWordProfileEnabled": self.wake_word_profile_enabled,
            "initialSpeechTimeout": self.initial_speech_timeout,
            "followupTimeout": self.followup_timeout,
            "segmentWatchdogInitialSeconds": self.segment_watchdog_initial,
            "segmentWatchdogRefreshSeconds": self.segment_watchdog_refresh,
            "segmentWatchdogWarningSeconds": self.segment_watchdog_warning,
            "closingRecoveryTimeoutSeconds": self.closing_recovery_timeout,
        }


#: ``queryName -> (fieldName, default, minimum, maximum)``. The bounds stay
#: deliberately wide so that deterministic tests can drive short deadlines
#: through the production entry point; the contract ranges are enforced by the
#: settings control plane in AP-SRV-050.
SESSION_ACTIVATION_TIMING_FIELDS = {
    "initialSpeechTimeout": (
        "initial_speech_timeout", DEFAULT_INITIAL_SPEECH_TIMEOUT, 0.01, 3600.0
    ),
    "followupTimeout": (
        "followup_timeout", DEFAULT_FOLLOWUP_TIMEOUT, 0.01, 3600.0
    ),
    "segmentWatchdogInitialSeconds": (
        "segment_watchdog_initial",
        DEFAULT_SEGMENT_WATCHDOG_INITIAL,
        0.01,
        3600.0,
    ),
    "segmentWatchdogRefreshSeconds": (
        "segment_watchdog_refresh",
        DEFAULT_SEGMENT_WATCHDOG_REFRESH,
        0.01,
        3600.0,
    ),
    "segmentWatchdogWarningSeconds": (
        "segment_watchdog_warning",
        DEFAULT_SEGMENT_WATCHDOG_WARNING,
        0.01,
        3600.0,
    ),
    "closingRecoveryTimeoutSeconds": (
        "closing_recovery_timeout",
        DEFAULT_CLOSING_RECOVERY_TIMEOUT,
        0.01,
        3600.0,
    ),
}

_ACTIVATION_TRUE_VALUES = {"true", "1", "yes", "on"}
_ACTIVATION_FALSE_VALUES = {"false", "0", "no", "off"}


def _parse_activation_flag(query_params, name):
    """Reads one trigger flag. An unparsable value is an error, not a ``False``.

    Silently treating ``manualTriggerEnabled=maybe`` as "disabled" could turn a
    valid request into the forbidden ``false/false`` combination without the
    client ever learning why, so the session is rejected instead.
    """
    raw = query_params.get(name)
    if raw is None:
        return None
    normalized = str(raw).strip().lower()
    if normalized == "":
        return None
    if normalized in _ACTIVATION_TRUE_VALUES:
        return True
    if normalized in _ACTIVATION_FALSE_VALUES:
        return False
    raise SessionConfigurationError(
        "invalid_activation_flag",
        f"{name} muss ein Wahrheitswert sein.",
        field=name,
        value=str(raw),
    )


def parse_session_activation_query(query_params):
    manual_enabled = _parse_activation_flag(query_params, "manualTriggerEnabled")
    wake_word_enabled = _parse_activation_flag(
        query_params, "wakeWordTriggerEnabled"
    )

    timings = {}
    for query_name, (
        field_name,
        default,
        minimum,
        maximum,
    ) in SESSION_ACTIVATION_TIMING_FIELDS.items():
        raw = query_params.get(query_name)
        if raw is None or str(raw).strip() == "":
            timings[field_name] = default
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError):
            raise SessionConfigurationError(
                "invalid_activation_timing",
                f"{query_name} muss eine Zahl sein.",
                field=query_name,
                value=str(raw),
            )
        if not math.isfinite(value) or not minimum <= value <= maximum:
            raise SessionConfigurationError(
                "invalid_activation_timing",
                f"{query_name} liegt außerhalb des zulässigen Bereichs "
                f"({minimum}–{maximum}).",
                field=query_name,
                value=str(raw),
            )
        timings[field_name] = value

    return SessionActivationRequest(
        manual_enabled=manual_enabled,
        wake_word_enabled=wake_word_enabled,
        **timings,
    )


def resolve_session_activation_config(request, effective_wake_word_enabled):
    """Turns the requested trigger flags into the configuration of one session.

    A session that sends neither flag keeps the legacy behaviour, so existing
    clients are unaffected. As soon as one flag is present the session is
    controlled and the omitted flag counts as ``false`` - an explicit opt-in,
    never an implicit one.
    """
    if request.manual_enabled is None and request.wake_word_enabled is None:
        return ResolvedSessionActivationConfig(
            mode="legacy",
            manual_enabled=False,
            wake_word_enabled=effective_wake_word_enabled,
            wake_word_profile_enabled=effective_wake_word_enabled,
            initial_speech_timeout=request.initial_speech_timeout,
            followup_timeout=request.followup_timeout,
            segment_watchdog_initial=request.segment_watchdog_initial,
            segment_watchdog_refresh=request.segment_watchdog_refresh,
            segment_watchdog_warning=request.segment_watchdog_warning,
            closing_recovery_timeout=request.closing_recovery_timeout,
        )

    man_enabled = bool(request.manual_enabled)
    ww_enabled = bool(request.wake_word_enabled)

    if not man_enabled and not ww_enabled:
        raise SessionConfigurationError(
            "activation_trigger_required",
            "Im kontrollierten Modus muss mindestens manualTriggerEnabled oder "
            "wakeWordTriggerEnabled aktiviert sein.",
        )

    # `wakeWordTriggerEnabled` says a detected wake word may open an
    # activation; whether detections happen at all is the separate wake-word
    # profile contract. If the wake word is the *only* trigger and the profile
    # is not active, the session could never activate anything, so it is
    # rejected here rather than silently going deaf.
    if not man_enabled and ww_enabled and not effective_wake_word_enabled:
        raise SessionConfigurationError(
            "activation_wake_word_unavailable",
            "wakeWordTriggerEnabled ist die einzige Triggerquelle, aber für "
            "diese Sitzung ist kein Wake-Word-Profil aktiv.",
        )

    return ResolvedSessionActivationConfig(
        mode="controlled",
        manual_enabled=man_enabled,
        wake_word_enabled=ww_enabled,
        wake_word_profile_enabled=bool(effective_wake_word_enabled),
        initial_speech_timeout=request.initial_speech_timeout,
        followup_timeout=request.followup_timeout,
        segment_watchdog_initial=request.segment_watchdog_initial,
        segment_watchdog_refresh=request.segment_watchdog_refresh,
        segment_watchdog_warning=request.segment_watchdog_warning,
        closing_recovery_timeout=request.closing_recovery_timeout,
    )


def runtime_settings_contract():
    return {
        "activeSessionSafe": sorted(ACTIVE_RUNTIME_SETTINGS),
        "newSessionOnly": sorted(NEW_SESSION_RUNTIME_SETTINGS),
        "startupOnly": sorted(STARTUP_ONLY_SETTINGS),
    }


def coerce_setting_value(name, value):
    if name == "log_level":
        return str(logging.getLevelName(resolve_log_level(value)))
    if name == "realtime_log_detail":
        normalized = str(value or "").strip().lower()
        if normalized not in {"off", "summary", "events"}:
            raise ValueError(
                "realtime_log_detail muss off, summary oder events sein"
            )
        return normalized
    if name == "transcript_log_mode":
        normalized = str(value or "").strip().lower()
        if normalized not in {"none", "final", "full"}:
            raise ValueError(
                "transcript_log_mode muss none, final oder full sein"
            )
        return normalized
    if name == "log_calendar_timezone":
        resolve_calendar_timezone(str(value))
        return str(value)
    if name in BOOL_SETTINGS:
        if not isinstance(value, bool):
            raise ValueError(f"{name} muss ein boolescher Wert sein")
        return value
    if name in INT_SETTINGS:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{name} muss eine Ganzzahl sein")
        if name.endswith("_max_bytes") and value <= 0:
            raise ValueError(f"{name} muss größer als null sein")
        if name.endswith("_backup_count") and value < 0:
            raise ValueError(f"{name} muss null oder größer sein")
        if name.endswith("_retention_days") and value < 0:
            raise ValueError(f"{name} muss null oder größer sein")
        if name == "event_log_queue_size" and value < 100:
            raise ValueError("event_log_queue_size muss mindestens 100 sein")
        return value
    if name in FLOAT_SETTINGS:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{name} muss eine Zahl sein")
        return float(value)
    if name in TUPLE_FLOAT_SETTINGS:
        if not isinstance(value, (list, tuple)):
            raise ValueError(f"{name} muss eine Liste von Zahlen sein")
        return tuple(float(item) for item in value)
    if name in DICT_SETTINGS:
        if value is not None and not isinstance(value, dict):
            raise ValueError(f"{name} muss ein JSON-Objekt oder null sein")
        return value
    if name in OPTIONAL_STRING_SETTINGS:
        if value is not None and not isinstance(value, str):
            raise ValueError(f"{name} muss eine Zeichenfolge oder null sein")
        return value
    if not isinstance(value, str):
        raise ValueError(f"{name} muss eine Zeichenfolge sein")
    return value


class SegmentState:
    """Owns the identity of the segment currently being recorded.

    ``id_factory`` is the authoritative creation point of a segment id. The v1
    transport keeps the historical integer counter; a protocol v2 session
    injects a canonical UUID factory here, so the very same string travels
    through ledger, events and results without any boundary reformatting
    (AP-SRV-040 K1).
    """

    def __init__(self, id_factory=None):
        self._lock = threading.Lock()
        self._id_factory = id_factory
        self._counter = 1
        self._segment_id = 1 if id_factory is None else id_factory()
        self._has_realtime = False

    def _advance_locked(self):
        self._counter += 1
        self._segment_id = (
            self._counter if self._id_factory is None else self._id_factory()
        )
        return self._segment_id

    def realtime(self):
        with self._lock:
            self._has_realtime = True
            return self._segment_id

    def final(self):
        with self._lock:
            segment_id = self._segment_id
            self._advance_locked()
            self._has_realtime = False
            return segment_id

    def current(self):
        with self._lock:
            return self._segment_id

    def reset(self):
        with self._lock:
            self._has_realtime = False
            return self._advance_locked()


def timestamp_iso(timestamp):
    return (
        datetime.datetime.fromtimestamp(timestamp, datetime.timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def normalized_client_id(value=None):
    candidate = str(value or "").strip()
    if (
        1 <= len(candidate) <= 128
        and all(
            character.isalnum() or character in "._:-"
            for character in candidate
        )
    ):
        return candidate
    return f"client-{uuid.uuid4().hex}"


def segment_text_fields(segment):
    fields = {}
    for key in (
        "durationSeconds",
        "endReason",
        "preRecordingBuffer",
        "recordingEndedAt",
        "recordingEndedAtIso",
        "recordingStartedAt",
        "recordingStartedAtIso",
        "wakeWord",
    ):
        if key in segment:
            fields[key] = segment[key]
    return fields


class SegmentTimelineTracker:
    def __init__(self, settings: ServerSettings):
        self.settings = settings
        self._lock = threading.Lock()
        self._segments = {}
        self._current_segment_id = None
        self._wakeword_wait_started_at = None
        self._pending_wakeword_detected_at = None
        self._last_wakeword_timeout_at = None

    def reset(self):
        with self._lock:
            self._segments.clear()
            self._current_segment_id = None
            self._wakeword_wait_started_at = None
            self._pending_wakeword_detected_at = None
            self._last_wakeword_timeout_at = None

    def mark_wakeword_wait_started(self, timestamp=None):
        timestamp = time.time() if timestamp is None else float(timestamp)
        with self._lock:
            self._wakeword_wait_started_at = timestamp
            self._pending_wakeword_detected_at = None
            return {
                "wakeWord": self._wakeword_payload(
                    wait_started_at=timestamp,
                    state="waiting_for_wake_word",
                )
            }

    def mark_wakeword_wait_ended(self, timestamp=None):
        timestamp = time.time() if timestamp is None else float(timestamp)
        with self._lock:
            wait_started_at = self._wakeword_wait_started_at
            self._wakeword_wait_started_at = None
            return {
                "wakeWord": self._wakeword_payload(
                    wait_started_at=wait_started_at,
                    wait_ended_at=timestamp,
                    state="wake_word_wait_ended",
                )
            }

    def mark_wakeword_detected(self, timestamp=None):
        timestamp = time.time() if timestamp is None else float(timestamp)
        with self._lock:
            self._pending_wakeword_detected_at = timestamp
            return {
                "wakeWord": self._wakeword_payload(
                    wait_started_at=self._wakeword_wait_started_at,
                    detected_at=timestamp,
                    state="wake_word_detected_waiting_for_voice",
                )
            }

    def mark_wakeword_timeout(self, timestamp=None):
        timestamp = time.time() if timestamp is None else float(timestamp)
        with self._lock:
            self._last_wakeword_timeout_at = timestamp
            self._pending_wakeword_detected_at = None
            return {
                "wakeWord": self._wakeword_payload(
                    wait_started_at=self._wakeword_wait_started_at,
                    timeout_at=timestamp,
                    state="wake_word_timeout",
                )
            }

    def mark_recording_started(self, segment_id, actual_preroll_seconds=None, timestamp=None):
        timestamp = time.time() if timestamp is None else float(timestamp)
        configured_preroll = max(0.0, float(self.settings.pre_recording_buffer_duration))
        included_preroll = (
            max(0.0, float(actual_preroll_seconds))
            if actual_preroll_seconds is not None
            else configured_preroll
        )
        prebuffer = {
            "configuredSeconds": configured_preroll,
            "includedSeconds": included_preroll,
            "startTimestamp": timestamp - included_preroll,
            "startTimestampIso": timestamp_iso(timestamp - included_preroll),
            "endTimestamp": timestamp,
            "endTimestampIso": timestamp_iso(timestamp),
            "exact": actual_preroll_seconds is not None,
        }
        with self._lock:
            segment = self._segment_locked(segment_id)
            segment.update({
                "segmentId": segment_id,
                "recordingStartedAt": timestamp,
                "recordingStartedAtIso": timestamp_iso(timestamp),
                "recordingEndedAt": None,
                "recordingEndedAtIso": None,
                "durationSeconds": None,
                "endReason": None,
                "preRecordingBuffer": prebuffer,
            })
            if self._pending_wakeword_detected_at is not None:
                segment["wakeWord"] = self._wakeword_payload(
                    wait_started_at=self._wakeword_wait_started_at,
                    detected_at=self._pending_wakeword_detected_at,
                    state="recording",
                )
            self._current_segment_id = segment_id
            return self._copy_segment_locked(segment_id)

    def mark_recording_ended(
        self,
        reason,
        segment_id=None,
        actual_duration_seconds=None,
        timestamp=None,
    ):
        timestamp = time.time() if timestamp is None else float(timestamp)
        with self._lock:
            if segment_id is None:
                segment_id = self._current_segment_id
            if segment_id is None:
                return None
            segment = self._segment_locked(segment_id)
            started_at = segment.get("recordingStartedAt")
            duration = actual_duration_seconds
            if duration is None and started_at is not None:
                duration = max(0.0, timestamp - float(started_at))
            segment.update({
                "recordingEndedAt": timestamp,
                "recordingEndedAtIso": timestamp_iso(timestamp),
                "durationSeconds": duration,
                "endReason": reason,
            })
            self._current_segment_id = None
            self._pending_wakeword_detected_at = None
            return self._copy_segment_locked(segment_id)

    def snapshot(self, segment_id=None):
        with self._lock:
            if segment_id is None:
                segment_id = self._current_segment_id
            if segment_id is None:
                return None
            return self._copy_segment_locked(segment_id)

    def _segment_locked(self, segment_id):
        return self._segments.setdefault(segment_id, {"segmentId": segment_id})

    def _copy_segment_locked(self, segment_id):
        segment = self._segments.get(segment_id)
        if segment is None:
            return None
        payload = {}
        for key, value in segment.items():
            if value is None:
                continue
            if isinstance(value, dict):
                payload[key] = dict(value)
            else:
                payload[key] = value
        return payload

    def _wakeword_payload(
        self,
        *,
        wait_started_at=None,
        wait_ended_at=None,
        detected_at=None,
        timeout_at=None,
        state=None,
    ):
        payload = {
            "enabled": self.settings.wake_word_enabled(),
            "backend": self.settings.wakeword_backend,
            "wakeWords": self.settings.wake_words,
            "state": state,
        }
        timestamps = {
            "waitStartedAt": wait_started_at,
            "waitEndedAt": wait_ended_at,
            "detectedAt": detected_at,
            "timeoutAt": timeout_at,
        }
        for key, value in timestamps.items():
            if value is None:
                continue
            payload[key] = value
            payload[f"{key}Iso"] = timestamp_iso(value)
        return payload


class RunningStats:
    def __init__(self):
        self._lock = threading.Lock()
        self._count = 0
        self._total = 0.0
        self._max = 0.0
        self._recent = collections.deque(maxlen=256)

    def record(self, value):
        value = float(value)
        with self._lock:
            self._count += 1
            self._total += value
            self._max = max(self._max, value)
            self._recent.append(value)

    def snapshot_ms(self):
        with self._lock:
            recent = sorted(self._recent)
            count = self._count
            total = self._total
            max_value = self._max

        def percentile(fraction):
            if not recent:
                return 0.0
            index = min(len(recent) - 1, int(round((len(recent) - 1) * fraction)))
            return recent[index] * 1000.0

        return {
            "count": count,
            "avgMs": (total / count * 1000.0) if count else 0.0,
            "maxMs": max_value * 1000.0,
            "p50Ms": percentile(0.50),
            "p95Ms": percentile(0.95),
        }


@dataclass(frozen=True)
class InferenceJob:
    request_id: str
    session_id: str
    kind: str
    audio: Any
    language: Optional[str]
    use_prompt: bool
    segment_id: int
    sequence: int
    generation: int
    created_at: float
    deadline_at: Optional[float] = None
    sample_rate: int = SERVER_SAMPLE_RATE
    request_options: Optional[Dict[str, Any]] = None
    client_id: Optional[str] = None
    segment_context: Optional[SegmentContext] = None


@dataclass(frozen=True)
class InferenceResult:
    request_id: str
    session_id: str
    kind: str
    segment_id: int
    sequence: int
    generation: int
    text: str
    error: Optional[str]
    created_at: float
    started_at: float
    completed_at: float
    queue_delay: float
    inference_duration: float
    total_latency: float
    details: Optional[Dict[str, Any]] = None
    audio_duration_seconds: float = 0.0
    client_id: Optional[str] = None
    segment_context: Optional[SegmentContext] = None


@dataclass(frozen=True)
class QueueSubmitResult:
    accepted: bool
    reason: str = ""
    coalesced: bool = False


@dataclass(frozen=True)
class InputClosePlan:
    """One immutable description of an input-close operation to execute.

    ``_run_input_close(plan)`` is the single orchestrator for both normal
    closes and recovery. It runs **outside** ``self.lock`` and outside
    ``_ledger_dispatch_lock``: closing the gate, flushing the recorder and
    dispatching the ledger close happen there, and only afterwards the
    identity-bound controller finalisation turns the phase to ``idle``.
    """

    activation_id: str
    activation_sequence: int
    gate_generation: int
    reason: str
    cause: str
    requested_by_command_id: Optional[str] = None
    requested_by_action: Optional[str] = None
    cancel_pending: bool = False
    recovery: bool = False
    #: Accepted segments of this activation, sampled before the ledger close.
    #: Closing an activation whose segments are already terminal drops its
    #: ledger record immediately, so the count has to travel with the plan.
    accepted_segment_count: int = 0


class ConnectionManager:
    def __init__(self):
        self._connections = {}
        self._lock = asyncio.Lock()
        self._loop = None

    def bind_loop(self, loop):
        self._loop = loop

    async def connect(self, session_id, websocket):
        await websocket.accept()
        async with self._lock:
            self._connections[session_id] = websocket

    async def disconnect(self, session_id):
        async with self._lock:
            self._connections.pop(session_id, None)

    async def send(self, session_id, message):
        payload = json.dumps(message, separators=(",", ":"))
        async with self._lock:
            websocket = self._connections.get(session_id)

        if websocket is None:
            return False

        try:
            await websocket.send_text(payload)
            return True
        except Exception:
            async with self._lock:
                if self._connections.get(session_id) is websocket:
                    self._connections.pop(session_id, None)
            return False

    async def send_all(self, message):
        payload = json.dumps(message, separators=(",", ":"))
        async with self._lock:
            connections = list(self._connections.items())

        stale = []
        for session_id, websocket in connections:
            try:
                await websocket.send_text(payload)
            except Exception:
                stale.append((session_id, websocket))

        if stale:
            async with self._lock:
                for session_id, websocket in stale:
                    if self._connections.get(session_id) is websocket:
                        self._connections.pop(session_id, None)

    def publish_session(self, session_id, message):
        if self._loop is None:
            return
        asyncio.run_coroutine_threadsafe(self.send(session_id, message), self._loop)

    def publish_all(self, message):
        if self._loop is None:
            return
        asyncio.run_coroutine_threadsafe(self.send_all(message), self._loop)


class FairInferenceQueue:
    def __init__(self, name, settings: ServerSettings, drop_callback=None):
        self.name = name
        self.settings = settings
        self.drop_callback = drop_callback
        self._condition = threading.Condition()
        self._sessions = {}
        self._ordered_sessions = collections.deque()
        self._queued_session_ids = set()
        self._total_queued = 0
        self._closed = False
        self._coalesced_realtime = 0
        self._stale_realtime_dropped = 0
        self._rejected_jobs = 0

    def submit(self, job: InferenceJob):
        dropped_jobs = []
        with self._condition:
            if self._closed:
                return QueueSubmitResult(False, "Der Scheduler ist gestoppt")

            state = self._sessions.setdefault(
                job.session_id,
                {"final": collections.deque(), "realtime": None},
            )

            if job.kind == "final":
                if len(state["final"]) >= self.settings.max_final_queue_depth_per_session:
                    self._rejected_jobs += 1
                    return QueueSubmitResult(False, "Die finale Warteschlange der Sitzung ist voll")
                if self._total_queued >= self.settings.max_global_inference_queue_depth:
                    self._rejected_jobs += 1
                    return QueueSubmitResult(False, "Die globale Inferenzwarteschlange ist voll")
                state["final"].append(job)
                self._total_queued += 1
                self._ensure_session_locked(job.session_id)
                self._condition.notify()
                return QueueSubmitResult(True)

            if job.kind != "realtime":
                self._rejected_jobs += 1
                return QueueSubmitResult(False, f"Unbekannte Inferenzart: {job.kind}")

            old_job = state["realtime"]
            if old_job is not None:
                state["realtime"] = job
                dropped_jobs.append((old_job, "coalesced"))
                self._coalesced_realtime += 1
                self._ensure_session_locked(job.session_id)
                self._condition.notify()
                result = QueueSubmitResult(True, coalesced=True)
            elif self._total_queued >= self.settings.max_global_inference_queue_depth:
                self._rejected_jobs += 1
                result = QueueSubmitResult(False, "Die globale Inferenzwarteschlange ist voll")
            else:
                state["realtime"] = job
                self._total_queued += 1
                self._ensure_session_locked(job.session_id)
                self._condition.notify()
                result = QueueSubmitResult(True)

        self._notify_drops(dropped_jobs)
        return result

    def get(self):
        while True:
            stale_jobs = []
            job = None
            with self._condition:
                while not self._closed:
                    job = None
                    now = time.monotonic()
                    while self._ordered_sessions:
                        session_id = self._ordered_sessions.popleft()
                        self._queued_session_ids.discard(session_id)
                        state = self._sessions.get(session_id)
                        if state is None:
                            continue

                        job = None
                        if state["final"]:
                            job = state["final"].popleft()
                        elif state["realtime"] is not None:
                            realtime_job = state["realtime"]
                            state["realtime"] = None
                            if (
                                realtime_job.deadline_at is not None
                                and realtime_job.deadline_at < now
                            ):
                                self._total_queued -= 1
                                self._stale_realtime_dropped += 1
                                stale_jobs.append((realtime_job, "stale"))
                                self._cleanup_session_locked(session_id)
                                continue
                            job = realtime_job

                        if job is None:
                            self._cleanup_session_locked(session_id)
                            continue

                        self._total_queued -= 1
                        if self._session_has_work_locked(session_id):
                            self._ensure_session_locked(session_id)
                        else:
                            self._cleanup_session_locked(session_id)
                        break

                    if job is not None:
                        break
                    if stale_jobs:
                        break
                    self._condition.wait(timeout=0.2)

                if self._closed:
                    return None

            self._notify_drops(stale_jobs)
            if job is not None:
                return job

    def cancel_session(self, session_id):
        dropped = []
        with self._condition:
            state = self._sessions.pop(session_id, None)
            self._queued_session_ids.discard(session_id)
            if state is None:
                return
            while state["final"]:
                dropped.append((state["final"].popleft(), "cancelled"))
                self._total_queued -= 1
            if state["realtime"] is not None:
                dropped.append((state["realtime"], "cancelled"))
                self._total_queued -= 1
                state["realtime"] = None
            self._condition.notify_all()
        self._notify_drops(dropped)

    def close(self):
        with self._condition:
            self._closed = True
            self._condition.notify_all()

    def snapshot(self):
        with self._condition:
            per_session = {
                session_id: {
                    "final": len(state["final"]),
                    "realtime": 1 if state["realtime"] is not None else 0,
                }
                for session_id, state in self._sessions.items()
            }
            return {
                "name": self.name,
                "queued": self._total_queued,
                "sessions": len(self._sessions),
                "perSession": per_session,
                "coalescedRealtime": self._coalesced_realtime,
                "staleRealtimeDropped": self._stale_realtime_dropped,
                "rejectedJobs": self._rejected_jobs,
            }

    def _ensure_session_locked(self, session_id):
        if session_id not in self._queued_session_ids:
            self._queued_session_ids.add(session_id)
            self._ordered_sessions.append(session_id)

    def _session_has_work_locked(self, session_id):
        state = self._sessions.get(session_id)
        if state is None:
            return False
        return bool(state["final"]) or state["realtime"] is not None

    def _cleanup_session_locked(self, session_id):
        if not self._session_has_work_locked(session_id):
            self._sessions.pop(session_id, None)

    def _notify_drops(self, dropped_jobs):
        if not self.drop_callback:
            return
        for job, reason in dropped_jobs:
            try:
                self.drop_callback(job, reason, self.name)
            except Exception:
                LOGGER.exception("Drop-Callback fehlgeschlagen")


class SharedEngineWorker:
    def __init__(
        self,
        name,
        settings: ServerSettings,
        queue: FairInferenceQueue,
        engine_factory: Callable[[], Any],
        result_callback: Callable[[InferenceResult], None],
        error_callback: Optional[Callable[[str, Exception], None]] = None,
        initialization_lock: Optional[threading.Lock] = None,
    ):
        self.name = name
        self.settings = settings
        self.queue = queue
        self.engine_factory = engine_factory
        self.result_callback = result_callback
        self.error_callback = error_callback
        self.initialization_lock = initialization_lock
        self.ready = threading.Event()
        self.stop_event = threading.Event()
        self.thread = None
        self.engine = None
        self.load_error = None
        self.busy_seconds = 0.0
        self.started_at = time.monotonic()
        self.completed_jobs = 0
        self.failed_jobs = 0
        self.queue_delay = RunningStats()
        self.inference_duration = RunningStats()
        self.total_latency = RunningStats()

    def start(self):
        self.thread = threading.Thread(
            target=self._worker,
            name=f"VoiceSTT-{self.name}-Inference",
            daemon=True,
        )
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        self.queue.close()
        if self.thread is not None:
            self.thread.join(timeout=10)
        if self.thread is None or not self.thread.is_alive():
            self.engine = None

    def snapshot(self):
        elapsed = max(0.001, time.monotonic() - self.started_at)
        return {
            "name": self.name,
            "ready": self.ready.is_set(),
            "healthy": self.load_error is None,
            "completedJobs": self.completed_jobs,
            "failedJobs": self.failed_jobs,
            "busyRatio": min(1.0, self.busy_seconds / elapsed),
            "queueDelay": self.queue_delay.snapshot_ms(),
            "inferenceDuration": self.inference_duration.snapshot_ms(),
            "totalLatency": self.total_latency.snapshot_ms(),
        }

    def _worker(self):
        try:
            if self.initialization_lock is None:
                self.engine = self.engine_factory()
            else:
                # Some native CPU engines (notably Kroko-ONNX) corrupt their
                # allocator state when two model instances are constructed at
                # exactly the same time. Inference remains independent after
                # this short, process-wide initialization phase.
                with self.initialization_lock:
                    self.engine = self.engine_factory()
            self._warmup()
        except Exception as exc:
            self.load_error = exc
            LOGGER.exception("Inferenz-Engine %s konnte nicht initialisiert werden", self.name)
            if self.error_callback:
                self.error_callback(self.name, exc)
        finally:
            self.ready.set()

        while not self.stop_event.is_set():
            job = self.queue.get()
            if job is None:
                break

            started_at = time.monotonic()
            text = ""
            details = {}
            error = None

            try:
                if self.engine is None:
                    raise RuntimeError(f"Die Inferenz-Engine {self.name} ist nicht verfügbar")
                if job.request_options and hasattr(self.engine, "transcribe_with_options"):
                    result = self.engine.transcribe_with_options(
                        job.audio,
                        language=job.language if job.language else None,
                        use_prompt=job.use_prompt,
                        options=job.request_options,
                    )
                else:
                    result = self.engine.transcribe(
                        job.audio,
                        language=job.language if job.language else None,
                        use_prompt=job.use_prompt,
                    )
                text = (getattr(result, "text", "") or "").strip()
                details = getattr(result, "details", None) or {}
                self.completed_jobs += 1
            except Exception as exc:
                self.failed_jobs += 1
                error = str(exc)
                LOGGER.exception("Inferenzauftrag fehlgeschlagen: %s", job.request_id)

            completed_at = time.monotonic()
            queue_delay = max(0.0, started_at - job.created_at)
            inference_duration = max(0.0, completed_at - started_at)
            total_latency = max(0.0, completed_at - job.created_at)
            self.busy_seconds += inference_duration
            self.queue_delay.record(queue_delay)
            self.inference_duration.record(inference_duration)
            self.total_latency.record(total_latency)
            self.result_callback(
                InferenceResult(
                    request_id=job.request_id,
                    session_id=job.session_id,
                    kind=job.kind,
                    segment_id=job.segment_id,
                    sequence=job.sequence,
                    generation=job.generation,
                    text=text,
                    error=error,
                    created_at=job.created_at,
                    started_at=started_at,
                    completed_at=completed_at,
                    queue_delay=queue_delay,
                    inference_duration=inference_duration,
                    total_latency=total_latency,
                    details=details,
                    audio_duration_seconds=(
                        len(job.audio) / float(job.sample_rate)
                        if job.sample_rate and hasattr(job.audio, "__len__")
                        else 0.0
                    ),
                    client_id=job.client_id,
                    segment_context=job.segment_context,
                )
            )

    def _warmup(self):
        if not self.settings.model_warmup or self.engine is None:
            return
        try:
            audio = read_wav_float32(WARMUP_AUDIO_PATH).samples
            self.engine.warmup(audio)
        except Exception:
            LOGGER.debug("Aufwärmlauf für %s übersprungen", self.name, exc_info=True)


class InferenceScheduler:
    def __init__(
        self,
        settings: ServerSettings,
        result_callback: Callable[[InferenceResult], None],
        drop_callback: Optional[Callable[[InferenceJob, str, str], None]] = None,
        error_callback: Optional[Callable[[str, Exception], None]] = None,
    ):
        self.settings = settings
        self.result_callback = result_callback
        self.drop_callback = drop_callback
        self.error_callback = error_callback
        self.engine_initialization_lock = threading.Lock()
        self.main_queue = FairInferenceQueue("main", settings, drop_callback)
        self.realtime_queue = (
            self.main_queue
            if settings.use_main_model_for_realtime
            else FairInferenceQueue("realtime", settings, drop_callback)
        )
        self.main_worker = SharedEngineWorker(
            "main",
            settings,
            self.main_queue,
            self._create_main_engine,
            result_callback,
            error_callback,
            self.engine_initialization_lock,
        )
        self.realtime_worker = None
        if not settings.use_main_model_for_realtime:
            self.realtime_worker = SharedEngineWorker(
                "realtime",
                settings,
                self.realtime_queue,
                self._create_realtime_engine,
                result_callback,
                error_callback,
                self.engine_initialization_lock,
            )

    def start(self):
        self.main_worker.start()
        if self.realtime_worker is not None:
            self.realtime_worker.start()

    def stop(self):
        self.main_worker.stop()
        if self.realtime_worker is not None:
            self.realtime_worker.stop()

    def wait_ready(self, timeout=None):
        deadline = None if timeout is None else time.monotonic() + timeout
        workers = [self.main_worker]
        if self.realtime_worker is not None:
            workers.append(self.realtime_worker)

        for worker in workers:
            remaining = None if deadline is None else max(0.0, deadline - time.monotonic())
            if not worker.ready.wait(timeout=remaining):
                return False
        return True

    def healthy(self):
        if self.main_worker.load_error is not None:
            return False
        if self.realtime_worker is not None and self.realtime_worker.load_error is not None:
            return False
        return True

    def submit(self, job: InferenceJob):
        if job.kind == "realtime" and not self.settings.use_main_model_for_realtime:
            return self.realtime_queue.submit(job)
        return self.main_queue.submit(job)

    def cancel_session(self, session_id):
        self.main_queue.cancel_session(session_id)
        if self.realtime_queue is not self.main_queue:
            self.realtime_queue.cancel_session(session_id)

    def snapshot(self):
        data = {
            "mode": (
                "low-memory-one-model"
                if self.settings.use_main_model_for_realtime
                else "balanced-main-plus-realtime"
            ),
            "queues": {"main": self.main_queue.snapshot()},
            "workers": {"main": self.main_worker.snapshot()},
        }
        if self.realtime_queue is not self.main_queue:
            data["queues"]["realtime"] = self.realtime_queue.snapshot()
        if self.realtime_worker is not None:
            data["workers"]["realtime"] = self.realtime_worker.snapshot()
        return data

    def _create_main_engine(self):
        from VoiceSTT.transcription_engines import (
            TranscriptionEngineConfig,
            create_transcription_engine,
        )

        return create_transcription_engine(
            self.settings.transcription_engine,
            TranscriptionEngineConfig(
                model=self.settings.model,
                download_root=self.settings.download_root,
                compute_type=self.settings.compute_type,
                gpu_device_index=0,
                device=effective_device(self.settings.device),
                beam_size=self.settings.beam_size,
                initial_prompt=self.settings.initial_prompt,
                batch_size=self.settings.batch_size,
                vad_filter=self.settings.vad_filter,
                normalize_audio=self.settings.normalize_audio,
                engine_options=self.settings.transcription_engine_options,
            ),
        )

    def _create_realtime_engine(self):
        from VoiceSTT.transcription_engines import (
            TranscriptionEngineConfig,
            create_transcription_engine,
        )

        return create_transcription_engine(
            self.settings.realtime_transcription_engine
            or self.settings.transcription_engine,
            TranscriptionEngineConfig(
                model=self.settings.realtime_model or self.settings.model,
                download_root=self.settings.download_root,
                compute_type=self.settings.compute_type,
                gpu_device_index=0,
                device=effective_device(self.settings.device),
                beam_size=self.settings.beam_size_realtime,
                initial_prompt=self.settings.initial_prompt_realtime,
                batch_size=self.settings.realtime_batch_size,
                vad_filter=self.settings.vad_filter,
                normalize_audio=self.settings.normalize_audio,
                engine_options=(
                    self.settings.realtime_transcription_engine_options
                    if self.settings.realtime_transcription_engine_options is not None
                    else self.settings.transcription_engine_options
                ),
            ),
        )


class SchedulerTranscriptionExecutor:
    def __init__(self, service, session_id, kind):
        self.service = service
        self.session_id = session_id
        self.kind = kind

    def transcribe(self, audio, language=None, use_prompt=True):
        return self.transcribe_with_context(
            audio,
            language=language,
            use_prompt=use_prompt,
            segment_context=None,
        )

    def transcribe_with_context(
        self,
        audio,
        language=None,
        use_prompt=True,
        segment_context=None,
    ):
        if segment_context is None and self.kind == "final":
            session = self.service.sessions.get(self.session_id)
            if session is not None:
                segment_context = session.current_transcription_context()
        return self.service.transcribe_for_recorder(
            self.session_id,
            self.kind,
            audio,
            language,
            use_prompt,
            segment_context=segment_context,
        )


class RecorderBackedRealtimeSession:
    def __init__(
        self,
        service,
        session_id,
        client_id=None,
        settings=None,
        session_config=None,
        activation_config=None,
        canonical_ids=False,
    ):
        self.service = service
        self.settings = settings or replace(service.settings)
        self.session_config = session_config or ResolvedSessionWakeWordConfig(
            requested_enabled=None,
            effective_enabled=self.settings.wake_word_enabled(),
            effective_backend=str(self.settings.wakeword_backend or ""),
            effective_wake_words=_split_wake_word_ids(self.settings.wake_words),
            source="server",
        )
        self.activation_config = activation_config or ResolvedSessionActivationConfig(
            mode="legacy",
            manual_enabled=False,
            wake_word_enabled=self.settings.wake_word_enabled(),
            initial_speech_timeout=DEFAULT_INITIAL_SPEECH_TIMEOUT,
            followup_timeout=DEFAULT_FOLLOWUP_TIMEOUT,
        )
        self.session_id = session_id
        self.client_id = normalized_client_id(client_id)
        # A protocol v2 session generates canonical, hyphenated UUIDs at every
        # authoritative id source. The v1 transport keeps its compact ids until
        # the legacy cut in AP-SRV-070.
        self.canonical_ids = bool(canonical_ids)
        self._id_factory = (
            (lambda: str(uuid.uuid4())) if self.canonical_ids else None
        )
        #: Optional single subscriber on the lifecycle funnel. AP-SRV-040 binds
        #: its event projection here; it never becomes a second authority.
        self._protocol_observer = None
        self.segment_state = SegmentState(id_factory=self._id_factory)
        self.timeline = SegmentTimelineTracker(self.settings)
        self.lock = threading.RLock()
        self.streaming = False
        self.status = "idle"
        self.generation = 0
        self.reject_current_recording = False
        self.dropped_audio_chunks = 0
        self.rejected_audio_chunks = 0
        self.coalesced_realtime = 0
        self.stale_realtime_discarded = 0
        self.cancelled_jobs = 0
        self.realtime_submitted = 0
        self.final_submitted = 0
        self.realtime_completed = 0
        self.final_completed = 0
        self.realtime_rejected = 0
        self.final_rejected = 0
        self.forced_finalizations = 0
        self.dropped_recorded_segments = 0
        self.recording_sample_count = 0
        self._recorded_chunk_callback_seen = False
        self._force_finalize_in_progress = False
        self._wakeword_voice_window = False
        self._wakeword_followup_generation = 0
        self.segment_ledger = SegmentLedger(self.session_id)
        # AP-SRV-050: the one session-scoped settings domain authority. Its
        # ``settingsRevision`` is the revision this session publishes; it is
        # never the server revision and never a second persisted store.
        self.settings_state = self._build_settings_state()
        # Owns the complete mutation -> observable dispatch boundary. The
        # ledger lock orders state, while this session lock keeps a later
        # worker from publishing its already-created update first.
        self._ledger_dispatch_lock = threading.RLock()
        self._active_recording_context = None
        self._active_text_context = None
        self._last_final_context = None
        self._legacy_activation_sequence = 0
        self._performance_first_text_segments = set()
        self._realtime_event_stats = {}
        self._recorder_wake_word_timeout_before_followup = None
        self._recorder_start_recording_before_followup = None
        self._recorder_stop_recording_before_followup = None
        self._activation = None
        self._activation_timer_generation = 0
        #: The timer token the single scheduled worker was armed with.
        self._armed_timer_token = None
        # Monotone stream/lifecycle Epoch. Every stream start/stop/close
        # advances it, which invalidates lifecycle-bound recorder callbacks
        # from an earlier stream (F9/T11-T13).
        self._lifecycle_epoch = 0
        # The wake-detection epoch latched by a *valid synchronous*
        # ``_on_wakeword_detection_start``; a detect callback whose epoch no
        # longer matches the current lifecycle is inert (F9/T13).
        self._wake_detection_epoch = None
        # PHASE-04 / C3: the exactly-once input-close lifecycle event is
        # logically reserved before the foreground slot may become idle.
        # AP-SRV-040 will bind this seam to eventId/eventSeq/stateVersion.
        self._registered_input_close_events = {}
        # Session-scoped command idempotency. The contract requires the replay
        # cache to hold for at least the whole session, so it is cleared when
        # the session is torn down, not trimmed while it runs.
        self._command_replay = CommandReplayCache()
        # Generic device availability. The server never learns which device or
        # why - that stays client responsibility (DEVICE-01/DEVICE-02).
        self._audio_available = True
        self.queue_delay = {"realtime": RunningStats(), "final": RunningStats()}
        self.inference_duration = {"realtime": RunningStats(), "final": RunningStats()}
        self.total_latency = {"realtime": RunningStats(), "final": RunningStats()}
        self.recorder = self._create_recorder()
        # AP-SRV-060: the coordinator between detection and the source-neutral
        # activation authority. ``None`` for every session without an admitted
        # v2 wake selection, which keeps the legacy path untouched.
        self._wake_admission = None
        if self.activation_config.mode == "controlled":
            self.recorder.set_activation_policy("controlled")
            self._activation = ActivationController(
                manual_trigger_enabled=self.activation_config.manual_enabled,
                wake_word_trigger_enabled=self.activation_config.wake_word_enabled,
                initial_speech_timeout=self.activation_config.initial_speech_timeout,
                followup_timeout=self.activation_config.followup_timeout,
                segment_watchdog_initial=(
                    self.activation_config.segment_watchdog_initial
                ),
                segment_watchdog_refresh=(
                    self.activation_config.segment_watchdog_refresh
                ),
                segment_watchdog_warning=(
                    self.activation_config.segment_watchdog_warning
                ),
                closing_recovery_timeout=(
                    self.activation_config.closing_recovery_timeout
                ),
                id_factory=self._id_factory,
            )
        self._install_wake_word_runtime()
        self.text_thread = threading.Thread(
            target=self._text_worker,
            name=f"VoiceSTTSessionText-{session_id}",
            daemon=True,
        )
        self.text_thread.start()

    # -- AP-SRV-060 wake detection runtime -----------------------------------

    def _install_wake_word_runtime(self):
        """Binds the wake gate and the admission coordinator to the recorder.

        Only a session that actually holds an admitted catalog selection gets
        the v2 detection path. The evaluator drives the one
        :class:`~VoiceSTT.core.openwakeword_engine.OpenWakeWordEngine` the
        recorder built, and every wake value comes from the one AP-SRV-050
        settings authority through :meth:`_wake_attempt_policy`. That snapshot
        is frozen for the duration of one hit region, so a patch that lands
        mid-utterance applies to the next attempt (Root F11).
        """
        selection = getattr(self.session_config, "wake_word_selection", None)
        if selection is None or self._activation is None:
            return
        evaluator = WakeDetectionEvaluator(
            policy_supplier=self._wake_attempt_policy,
            engine=getattr(self.recorder, "wake_engine", None),
        )
        self.recorder.wake_detection_evaluator = evaluator
        self.recorder.wake_word_pre_roll_ms = evaluator.pre_roll_ms
        self._wake_admission = WakeAdmissionCoordinator(
            evaluator=evaluator,
            activate=self._activate_from_wake_candidate,
            deliver=self._deliver_wake_detected_event,
            committed_probe=self._open_wake_activation_id,
        )

    def _wake_effective_settings(self):
        """One atomic read of the session's effective wake settings."""
        state = getattr(self, "settings_state", None)
        if state is None:
            return None
        try:
            return state.activation_admission_settings()
        except Exception:  # noqa: BLE001 - defensive projection
            return None

    def _wake_engine_options(self):
        """The ``next_session`` wake engine values of this session.

        ``detectorGain`` is a ``next_activation`` value and is re-read per
        attempt; it is passed here only as the engine's starting value so a
        session that never patches still amplifies correctly.
        """
        options = {
            "detector_gain": 1.0,
            "noise_suppression_enabled": False,
            "vad_threshold": 0.0,
        }
        bundle = self._wake_effective_settings()
        if bundle is None:
            return options
        effective = bundle.effective_settings
        gain = effective.get(settings_control_module.WAKE_WORD_DETECTOR_GAIN)
        if isinstance(gain, (int, float)) and not isinstance(gain, bool):
            options["detector_gain"] = float(gain)
        suppression = effective.get(
            settings_control_module.WAKE_WORD_NOISE_SUPPRESSION
        )
        if isinstance(suppression, bool):
            options["noise_suppression_enabled"] = suppression
        threshold = effective.get(
            settings_control_module.WAKE_WORD_VAD_THRESHOLD
        )
        if isinstance(threshold, (int, float)) and not isinstance(threshold, bool):
            options["vad_threshold"] = float(threshold)
        return options

    def _wake_attempt_policy(self):
        """The current wake attempt snapshot from the one settings authority.

        Read live, never cached here: the tracker freezes it at the first
        prediction frame of a new hit region and picks the new values up for
        the next attempt, which is exactly what
        ``applyPolicy = next_activation`` means. There is no second settings
        registry and no second copy of these values.
        """
        defaults = WakeAttemptPolicy(
            sensitivity=float(self.settings.wake_words_sensitivity or 0.5),
            min_consecutive_prediction_frames=1,
            detector_gain=1.0,
            cooldown_ms=0,
            pre_roll_ms=0,
            settings_revision=0,
        )
        bundle = self._wake_effective_settings()
        if bundle is None:
            return defaults
        effective = bundle.effective_settings

        def number(key, fallback, cast):
            value = effective.get(key)
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return fallback
            return cast(value)

        return WakeAttemptPolicy(
            sensitivity=number(
                settings_control_module.WAKE_WORD_SENSITIVITY,
                defaults.sensitivity, float,
            ),
            min_consecutive_prediction_frames=number(
                settings_control_module.WAKE_WORD_MIN_PREDICTION_FRAMES, 1, int
            ),
            detector_gain=number(
                settings_control_module.WAKE_WORD_DETECTOR_GAIN, 1.0, float
            ),
            cooldown_ms=number(
                settings_control_module.WAKE_WORD_COOLDOWN_MS, 0, int
            ),
            pre_roll_ms=number(
                settings_control_module.WAKE_WORD_PRE_ROLL_MS, 0, int
            ),
            settings_revision=int(bundle.settings_revision),
        )

    #: Historical name of :meth:`_wake_attempt_policy`.
    _wake_runtime_policy = _wake_attempt_policy

    def _open_wake_activation_id(self):
        """The open wake activation the controller really shows, if any.

        Root F7: consulted only when the admission path raised, so a crash can
        never be mistaken for "no activation happened".
        """
        controller = self._activation
        if controller is None:
            return None
        try:
            snapshot = controller.snapshot() or {}
        except Exception:  # noqa: BLE001 - defensive read
            return None
        if snapshot.get("primarySource") != "wake_word":
            return None
        return snapshot.get("activationId")

    def _activate_from_wake_candidate(self, candidate, boundary):
        """The activation admission of one wake candidate.

        The wake word is a trigger like any other: it runs through the very
        same source-neutral ``ActivationController`` admission as a manual
        command, including the generic audio-availability gate and the runtime
        suppression mask. It never opens a recording on its own, and a refusal
        leaves no latch, no event and no second activation behind.

        Root F7: ``ActivationController.activate`` is the commit point. Every
        guard and every failure *before* it means "no activation" and is
        reported as a refusal. Everything *after* it - decision application,
        event collection, event publication - can no longer undo the
        activation, so a failure there is reported as a post-commit error and
        never turns into a refusal. This method therefore does not raise once
        the commit happened.
        """
        published = []
        with self.lock:
            if not self.streaming or self.status == "closed":
                return WakeActivationOutcome.refused()
            if self._wake_detection_epoch != self._lifecycle_epoch:
                # A stale callback from an earlier stream is inert.
                return WakeActivationOutcome.refused()
            if self._activation is None or not self._audio_available:
                return WakeActivationOutcome.refused()
            try:
                activation_settings, timing_policy = self._new_activation_inputs()
            except Exception as exc:  # noqa: BLE001 - still pre-commit
                LOGGER.exception(
                    "Activation-Settings konnten für %s nicht aufgelöst werden",
                    self.session_id,
                )
                return WakeActivationOutcome(committed=False, error=exc)

            # --- commit point -------------------------------------------------
            decision = self._activation.activate(
                "wake_word",
                activation_settings,
                timing_policy=timing_policy,
            )
            if not decision.accepted:
                return WakeActivationOutcome.refused()
            committed_id = (decision.snapshot or {}).get("activationId")
            post_commit_error = None
            try:
                activation_id = self._apply_activation_decision_locked(
                    "activate", decision, published
                )
                committed_id = activation_id or committed_id
            except Exception as exc:  # noqa: BLE001 - post-commit
                post_commit_error = exc
                LOGGER.exception(
                    "Activation %s wurde übernommen, aber die Projektion ist "
                    "fehlgeschlagen",
                    committed_id,
                )
            self._wakeword_voice_window = True
            self._wakeword_followup_generation += 1

        try:
            self._publish_collected_events(published)
        except Exception as exc:  # noqa: BLE001 - post-commit
            post_commit_error = post_commit_error or exc
            LOGGER.exception(
                "Activationevents von %s konnten nicht veröffentlicht werden",
                committed_id,
            )
        return WakeActivationOutcome(
            committed=True,
            activation_id=committed_id,
            error=post_commit_error,
        )

    def _deliver_wake_detected_event(self, logical_event, detection):
        """Transport of the one logical ``wakeword.detected`` (Root F13).

        The logical event was already minted exactly once by the admission
        ledger before this call, so a transport failure here can never leave an
        accepted hit without an event and a retry can never duplicate one. The
        payload is routed through the existing AP-SRV-040 lifecycle funnel;
        there is no second event authority.
        """
        event = self.timeline.mark_wakeword_detected()
        fields = detection.event_fields()
        self._publish_timeline_event(
            "wakeword_detected",
            wakeWord=fields["wakeWordId"],
            wakeWordId=fields["wakeWordId"],
            score=fields["score"],
            activationId=fields["activationId"],
            logicalEventId=logical_event.event_id,
        )
        self.publish_status("wakeword_detected")
        return event

    def _publish_accepted_wake_detection(self, detection):
        """Historical single-argument publish seam."""
        from api_fastapi_server.wake_admission import LogicalWakeEvent

        return self._deliver_wake_detected_event(
            LogicalWakeEvent(
                event_id="",
                wake_word_id=detection.canonical_wake_word_id,
                activation_id=detection.activation_id,
                score=detection.score,
                sequence=1,
            ),
            detection,
        )

    def _release_wake_latch(self, activation_id=None):
        """Releases the wake latch at the safe input close of that activation."""
        coordinator = getattr(self, "_wake_admission", None)
        if coordinator is None:
            return False
        released = coordinator.release(activation_id)
        if released:
            recorder = getattr(self, "recorder", None)
            if recorder is not None:
                try:
                    recorder.wakeword_detected = False
                    recorder.wake_word_detect_time = 0
                except Exception:  # pragma: no cover - fakes may differ
                    pass
        return released

    def publish_wake_word_availability(self, catalog_revision, available_ids):
        """``wakeword.availability_changed`` through the AP-SRV-040 funnel."""
        self._publish_timeline_event(
            "wakeword_availability_changed",
            catalogRevision=int(catalog_revision),
            availableWakeWordIds=list(available_ids),
        )
        return True

    def wake_detection_diagnostics(self):
        """Raw-score/latch diagnostics. Never a domain event."""
        coordinator = getattr(self, "_wake_admission", None)
        if coordinator is None:
            return None
        return coordinator.diagnostics()

    def _create_recorder(self):
        recorder_factory = self.service.recorder_factory
        use_structured_stabilization = recorder_factory is None
        if recorder_factory is None:
            from VoiceSTT import AudioToTextRecorder

            recorder_factory = AudioToTextRecorder

        callback_key = (
            "on_realtime_transcription_stabilized"
            if self.settings.realtime_callback == "stabilized"
            else "on_realtime_transcription_update"
        )
        realtime_engine = self.settings.realtime_transcription_engine
        config = {
            "spinner": False,
            "use_microphone": False,
            "level": resolve_log_level(self.settings.log_level),
            # C2 lifecycle invariant: lifecycle-relevant recordercallbacks
            # (wake detection, recording start/stop) must run synchronously.
            # Setting this explicitly - rather than relying on the constructor
            # default - is part of the C2 safety architecture (T14).
            "start_callback_in_new_thread": False,
            "model": self.settings.model,
            "realtime_model_type": self.settings.realtime_model,
            "language": self.settings.language,
            "transcription_engine": self.settings.transcription_engine,
            "realtime_transcription_engine": realtime_engine,
            "transcription_engine_options": self.settings.transcription_engine_options,
            "realtime_transcription_engine_options": (
                self.settings.realtime_transcription_engine_options
            ),
            "download_root": self.settings.download_root,
            "compute_type": self.settings.compute_type,
            "device": self.settings.device,
            "beam_size": self.settings.beam_size,
            "beam_size_realtime": self.settings.beam_size_realtime,
            "batch_size": self.settings.batch_size,
            "realtime_batch_size": self.settings.realtime_batch_size,
            "faster_whisper_vad_filter": self.settings.vad_filter,
            "normalize_audio": self.settings.normalize_audio,
            "enable_realtime_transcription": True,
            "use_main_model_for_realtime": self.settings.use_main_model_for_realtime,
            "realtime_processing_pause": self.settings.realtime_processing_pause,
            "realtime_transcription_use_syllable_boundaries": (
                self.settings.realtime_transcription_use_syllable_boundaries
            ),
            "realtime_boundary_detector_sensitivity": (
                self.settings.realtime_boundary_detector_sensitivity
            ),
            "realtime_boundary_followup_delays": (
                self.settings.realtime_boundary_followup_delays
            ),
            "silero_sensitivity": self.settings.silero_sensitivity,
            "webrtc_sensitivity": self.settings.webrtc_sensitivity,
            "warmup_vad": self.settings.model_warmup,
            "post_speech_silence_duration": self.settings.post_speech_silence_duration,
            "min_length_of_recording": self.settings.min_length_of_recording,
            "min_gap_between_recordings": self.settings.min_gap_between_recordings,
            "early_transcription_on_silence": self.settings.early_transcription_on_silence,
            "initial_prompt": self.settings.initial_prompt,
            "initial_prompt_realtime": self.settings.initial_prompt_realtime,
            "wakeword_backend": self.settings.wakeword_backend,
            "openwakeword_model_paths": self.settings.openwakeword_model_paths,
            "openwakeword_inference_framework": self.settings.openwakeword_inference_framework,
            "wake_words": self.settings.wake_words,
            "wake_words_sensitivity": self.settings.wake_words_sensitivity,
            "wake_word_activation_delay": self.settings.wake_word_activation_delay,
            "wake_word_timeout": self.settings.wake_word_timeout,
            "wake_word_buffer_duration": self.settings.wake_word_buffer_duration,
            # AP-SRV-060 selected-only initialisation: exactly the admitted
            # classifiers reach OpenWakeWord, no catalog scan and no fallback.
            "wake_word_selection": getattr(
                self.session_config, "wake_word_selection", None
            ),
            # AP-SRV-060 C3: the next_session wake engine values of the
            # one AP-SRV-050 settings plane.
            "wake_word_engine_options": self._wake_engine_options(),
            "pre_recording_buffer_duration": self.settings.pre_recording_buffer_duration,
            "allowed_latency_limit": self.settings.audio_queue_size,
            "handle_buffer_overflow": True,
            "on_recording_start": self._on_recording_start,
            "on_recording_stop": self._on_recording_stop,
            "on_transcription_start": self._on_transcription_start,
            "on_wakeword_detected": self._on_wakeword_detected,
            "on_wakeword_timeout": self._on_wakeword_timeout,
            "on_wakeword_detection_start": self._on_wakeword_detection_start,
            "on_wakeword_detection_end": self._on_wakeword_detection_end,
            "on_vad_start": self._on_vad_start,
            "on_vad_stop": self._on_vad_stop,
            "on_vad_detect_start": self._on_vad_detect_start,
            "on_vad_detect_stop": self._on_vad_detect_stop,
            "on_recorded_chunk": self._on_recorded_chunk,
            "no_log_file": True,
            "transcription_executor": SchedulerTranscriptionExecutor(
                self.service,
                self.session_id,
                "final",
            ),
            "realtime_transcription_executor": SchedulerTranscriptionExecutor(
                self.service,
                self.session_id,
                "realtime",
            ),
        }
        if use_structured_stabilization:
            config["on_realtime_text_stabilization_update"] = (
                self._on_realtime_stabilization_event
            )
        else:
            config[callback_key] = self._on_realtime_text
        return recorder_factory(**config)

    def start_streaming(self):
        with self.lock:
            self._lifecycle_epoch += 1
            self._wake_detection_epoch = None
            self.streaming = True
            self.status = (
                "wakeword_wait"
                if self.settings.wake_word_enabled()
                and self.settings.wake_word_activation_delay <= 0
                else "listening"
            )
        self.publish_status(self.status)

    def stop_streaming(self):
        with self.lock:
            self._lifecycle_epoch += 1
            self._wake_detection_epoch = None
            self.streaming = False
            self.status = "idle"
            # An activation cannot outlive the audio stream it belongs to.
            closed = self._reset_activation_locked("stream_stopped")
        try:
            self.recorder.flush_buffered_audio()
            self._trim_recorded_audio_queue()
        except Exception:
            LOGGER.debug("Gepuffertes Audio für %s konnte nicht geleert werden", self.session_id, exc_info=True)
        finally:
            self.service.deactivate_speaker(self.session_id)
        if closed is not None:
            self._publish_timeline_event(closed[0], **closed[1])
            self._close_ledger_activation(
                closed[1].get("activationId"),
                "stream_stopped",
                requested_terminal="cancelled",
                cancel_pending=True,
            )
        self.publish_status("idle")

    def close(self):
        with self.lock:
            cancelled_generation = self.generation
            cancelled_segment = self.segment_state.current()
            should_cancel = self.status in {"recording", "transcribing"}
            self.generation += 1
            self._lifecycle_epoch += 1
            self._wake_detection_epoch = None
            self.streaming = False
            self.status = "closed"
            self.timeline.reset()
            self._performance_first_text_segments.clear()
            self._realtime_event_stats.clear()
            self._wakeword_voice_window = False
            self._wakeword_followup_generation += 1
            self._clear_recorder_followup_gate_locked()
            # A reconnect must never revive an activation of the old session.
            closed_activation = self._reset_activation_locked("session_closed")
        if closed_activation is not None:
            self._publish_timeline_event(
                closed_activation[0], **closed_activation[1]
            )
        had_pending_ledger_segment = (
            self.segment_ledger.snapshot()["pendingSegmentCount"] > 0
        )
        self._dispatch_ledger_operation(
            self.segment_ledger.cancel_all, "session_closed"
        )
        if should_cancel and not had_pending_ledger_segment:
            self._emit_cancelled_transcription(
                cancelled_generation,
                cancelled_segment,
                "session_closed",
            )
        self.service.cancel_scheduler_session(self.session_id)
        self.service.cancel_pending_recorder_transcriptions(self.session_id)
        self.service.deactivate_speaker(self.session_id)
        try:
            self.recorder.shutdown()
        except Exception:
            LOGGER.debug("Recorder für %s konnte nicht beendet werden", self.session_id, exc_info=True)
        if self.text_thread is not None:
            self.text_thread.join(timeout=3)
        # The replay cache is session scoped by contract, so this is the one
        # place it is released.
        self._command_replay.clear()

        # C3/PHASE-05 terminal seal: recorder shutdown/abort may synchronously
        # fire lifecycle callbacks before ``close()`` returns. Those callbacks
        # may clean recording state, but they must never leave a terminal
        # session looking reusable again. Recorder lifecycle callbacks are
        # pinned to synchronous dispatch, so this is the final close
        # linearization point.
        with self.lock:
            self.streaming = False
            self.status = "closed"
            self._wake_detection_epoch = None

    def clear(self):
        with self.lock:
            cancelled_generation = self.generation
            cancelled_segment = self.segment_state.current()
            should_cancel = self.status in {"recording", "transcribing"}
            self.generation += 1
            next_segment = self.segment_state.reset()
            self.timeline.reset()
            self._performance_first_text_segments.clear()
            self._realtime_event_stats.clear()
            self.reject_current_recording = True
            self.recording_sample_count = 0
            self._wakeword_voice_window = False
            self._wakeword_followup_generation += 1
            self._clear_recorder_followup_gate_locked()
            # `clear` discards the current turn, so the activation goes with it.
            cleared_activation = self._reset_activation_locked("client_clear")
            self.status = self._waiting_state_locked()
        had_pending_ledger_segment = (
            self.segment_ledger.snapshot()["pendingSegmentCount"] > 0
        )
        if cleared_activation is not None:
            self._publish_timeline_event(
                cleared_activation[0], **cleared_activation[1]
            )
            self._close_ledger_activation(
                cleared_activation[1].get("activationId"),
                "client_clear",
                requested_terminal="cancelled",
                cancel_pending=True,
            )
        else:
            self._dispatch_ledger_operation(
                self.segment_ledger.cancel_all, "client_clear"
            )
        if should_cancel and not had_pending_ledger_segment:
            self._emit_cancelled_transcription(
                cancelled_generation,
                cancelled_segment,
                "client_clear",
            )
        self.service.cancel_scheduler_session(self.session_id)
        self.service.cancel_pending_recorder_transcriptions(self.session_id)
        self.service.deactivate_speaker(self.session_id)
        try:
            self.recorder.abort()
        except Exception:
            LOGGER.debug("Recorder-Abbruch beim Löschen für %s fehlgeschlagen", self.session_id, exc_info=True)
        self.service.manager.publish_session(
            self.session_id,
            {
                "type": "clear",
                "sessionId": self.session_id,
                "nextSegmentId": next_segment,
            },
        )
        self.publish_status(self.status)

    def ingest_audio_packet(self, packet):
        samples = self.service.packet_to_server_samples(packet)
        if samples.size == 0:
            return True, None
        with self.lock:
            if not self.streaming:
                self.rejected_audio_chunks += 1
                return False, "Der Audiostream ist gestoppt; sende vor Audiopaketen einen Startbefehl."
        try:
            self.recorder.feed_audio(samples, original_sample_rate=SERVER_SAMPLE_RATE)
        except Exception as exc:
            LOGGER.exception("Audio konnte nicht an den Recorder übergeben werden")
            self.dropped_audio_chunks += 1
            self.service.events.emit(
                "system",
                "recorder.failed",
                severity="error",
                message="Recorder konnte Audio nicht verarbeiten",
                transport="websocket",
                clientId=self.client_id,
                sessionId=self.session_id,
                errorType=type(exc).__name__,
                error=str(exc),
            )
            return False, str(exc)
        warning = self._enforce_recording_duration(samples)
        if warning:
            self.service.manager.publish_session(
                self.session_id,
                {"type": "warning", "sessionId": self.session_id, "message": warning},
            )
        return True, None

    def handle_inference_result(self, result: InferenceResult):
        # Recorder-backed sessions consume scheduler results through
        # transcribe_for_recorder(); direct event routing is only used by the
        # older inline session tests.
        self.service.complete_pending_recorder_transcription(result)

    def on_job_dropped(self, job: InferenceJob, reason: str):
        if reason == "coalesced" and job.kind == "realtime":
            self.coalesced_realtime += 1
        elif reason == "stale" and job.kind == "realtime":
            self.stale_realtime_discarded += 1
        elif reason == "cancelled":
            self.cancelled_jobs += 1
        if job.kind == "final" and job.segment_context is not None:
            terminal = "cancelled" if reason == "cancelled" else "failed"
            self._dispatch_ledger_operation(
                self.segment_ledger.resolve_terminal,
                job.segment_context,
                terminal,
                f"scheduler_{reason}",
            )
        self.service.fail_pending_recorder_transcription(
            job.request_id,
            f"{job.kind}-Transkription wurde verworfen: {reason}",
        )

    def on_submit_result(self, job: InferenceJob, result: QueueSubmitResult):
        if result.accepted:
            if job.kind == "realtime":
                self.realtime_submitted += 1
                if result.coalesced:
                    self.coalesced_realtime += 1
            else:
                self.final_submitted += 1
            return

        if job.kind == "realtime":
            self.realtime_rejected += 1
        else:
            self.final_rejected += 1
            if job.segment_context is not None:
                self._dispatch_ledger_operation(
                    self.segment_ledger.resolve_terminal,
                    job.segment_context,
                    "failed",
                    f"scheduler_rejected: {result.reason}",
                )
        self.service.fail_pending_recorder_transcription(job.request_id, result.reason)

    def record_executor_result(self, result: InferenceResult):
        self.queue_delay[result.kind].record(result.queue_delay)
        self.inference_duration[result.kind].record(result.inference_duration)
        self.total_latency[result.kind].record(result.total_latency)
        if result.kind == "realtime":
            self.realtime_completed += 1
        else:
            self.final_completed += 1

    def publish_status(self, state=None):
        # ``closed`` is terminal. A timer/recorder callback can complete after
        # close() invalidated its lifecycle; that stale completion must never
        # make this same session reusable again (PHASE-05/F9).
        #
        # Guard and write share one self.lock acquisition, giving close-vs-
        # publish a total order: if publish wins first, close overwrites it;
        # if close wins first, this stale non-closed publish becomes a no-op.
        with self.lock:
            state = state or self.status
            if self.status == "closed" and state != "closed":
                return False
            self.status = state
            message = {
                "type": "status",
                "sessionId": self.session_id,
                "state": state,
                "timestamp": time.time(),
                "activeClientId": self.session_id if self.streaming else None,
                "queueDepth": self._recorder_queue_depth(),
                "droppedChunks": self.dropped_audio_chunks,
                "coalescedRealtime": self.coalesced_realtime,
                "staleRealtimeDiscarded": self.stale_realtime_discarded,
                "activeSessions": self.service.session_count(),
                "activeSpeakers": self.service.active_speaker_count(),
                "wakeWordEnabled": self.settings.wake_word_enabled(),
                "wakeWord": {
                    "enabled": self.settings.wake_word_enabled(),
                    "backend": self.settings.wakeword_backend,
                    "wakeWords": self.settings.wake_words,
                    "state": state if str(state).startswith("wakeword") else None,
                },
            }
            message["timestampIso"] = timestamp_iso(message["timestamp"])
        self.service.manager.publish_session(self.session_id, message)
        return True

    def session_config_dict(self):
        session_config = getattr(self, "session_config", None)
        if session_config is None:
            session_config = ResolvedSessionWakeWordConfig(
                requested_enabled=None,
                effective_enabled=self.settings.wake_word_enabled(),
                effective_backend=str(self.settings.wakeword_backend or ""),
                effective_wake_words=_split_wake_word_ids(
                    self.settings.wake_words
                ),
                source="server",
            )
        return session_config.public_dict()

    def activation_config_dict(self):
        """The activation configuration this session actually resolved to."""
        return self.activation_config.public_dict()

    def _effective_activation_settings(self):
        """Returns the complete settings view latched by a new activation.

        The controller detaches and freezes this value. Later session-setting
        changes can therefore affect only a later activation. The nested shape
        stays the legacy (v1) view; v2 sessions latch the flat wire projection
        through :meth:`_new_activation_inputs`.
        """
        return {
            "activationConfig": self.activation_config_dict(),
            "sessionConfig": self.session_config_dict(),
            "sessionSettings": self.public_settings(),
        }

    # -- AP-SRV-050 session settings control ---------------------------------

    def _build_settings_state(self):
        """The session's own revised settings overlay, seeded from server defaults.

        ``wakeWord.selection`` and ``wakeWord.sensitivity`` reflect the values
        actually admitted for this session; the six trigger timings inherit the
        admin-managed server default overlay at admission time, so a later
        server-default patch never rewrites an already existing session
        (AP-SRV-050 prompt 21/52/53).
        """
        server_defaults = {}
        control = getattr(self.service, "settings_control", None)
        if control is not None:
            server_defaults = dict(control.server_effective())
        overrides = {}
        if self.session_config is not None and self.session_config.effective_enabled:
            overrides[settings_control_module.WAKE_WORD_SELECTION] = list(
                self.session_config.effective_wake_words
            )
        return settings_control_module.SessionSettingsState(
            settings_control_module.build_default_registry(),
            server_defaults=server_defaults,
            requested=overrides,
            validate_key=self._validate_wake_selection_key,
        )

    def _validate_wake_selection_key(self, key, value):
        """Session-aware ``wakeWord.selection`` rules (AP-SRV-050 C2 F2).

        Only the selection key is touched here; everything else is left to the
        registry. Validation is **fail-closed**: a non-empty selection must
        always be checked against the catalog, an empty available-catalog set
        makes every requested id unavailable, and a catalog lookup failure
        rejects the whole field.

        AP-SRV-060: the check goes through the *one* catalog resolver, so a
        human-written ``Hey Jarvis`` or an explicit alias is accepted exactly
        like the canonical id, and a globally disabled id is refused with the
        same machine-readable code as an unknown one.
        """
        if key != settings_control_module.WAKE_WORD_SELECTION:
            return []
        selection = list(value or [])
        errors = []
        if self.settings.wake_word_enabled() and not selection:
            errors.append(settings_control_module.FieldError(
                field=key,
                code=settings_control_module.CODE_WAKE_SELECTION_REQUIRED,
                message=(
                    "Wenn Wake Word für die Session konfiguriert ist, darf "
                    "die Auswahl nicht leer sein."
                ),
            ))
        if not selection:
            return errors
        from .protocol_v2 import ports as v2_ports

        try:
            port = v2_ports.WakeWordPort(self.service)
            available_ids = set(port.available_ids())
            catalog = port.catalog
        except Exception:  # noqa: BLE001 - fail closed, never an exception leak
            errors.append(settings_control_module.FieldError(
                field=key,
                code=settings_control_module.CODE_WAKE_WORD_UNAVAILABLE,
                message=(
                    "Der Wake-Word-Katalog ist momentan nicht verfügbar; "
                    "die Auswahl kann nicht geprüft werden."
                ),
            ))
            return errors
        unknown = []
        for requested in selection:
            resolved = catalog.resolve(requested) if catalog is not None else None
            if resolved is None or resolved not in available_ids:
                unknown.append(str(requested))
        unknown = sorted(set(unknown))
        if unknown:
            errors.append(settings_control_module.FieldError(
                field=key,
                code=settings_control_module.CODE_WAKE_WORD_UNAVAILABLE,
                message=(
                    "Unbekannte Wake-Word-IDs: "
                    + ", ".join(unknown)
                    + "."
                ),
            ))
        return errors

    def apply_settings_patch(self, base_revision, changes):
        """Transactional session patch; the wire layer projects the result."""
        return self.settings_state.apply_patch(base_revision, changes)

    def _latched_wire_effective(self):
        """The immutable wire settings a running activation started with.

        Empty while no controlled activation is open. v2 sessions latch the
        flat projection, so snapshot/event/ledger/timer views stay consistent.
        """
        if not self.canonical_ids:
            return {}
        controller = self._activation
        if controller is None:
            return {}
        snapshot = controller.snapshot()
        if snapshot.get("phase") in (None, "idle"):
            return {}
        settled = snapshot.get("effectiveSettings")
        return dict(settled) if isinstance(settled, dict) else {}

    def _suppression_live(self):
        """Live runtime suppression from the single controller authority."""
        controller = self._activation
        suppressed = {}
        if controller is not None:
            try:
                suppressed = (
                    (controller.trigger_state() or {}).get("suppressed") or {}
                )
            except Exception:  # noqa: BLE001 - defensive projection
                suppressed = {}
        return {
            settings_control_module.RUNTIME_SUPPRESSION_MANUAL: bool(
                suppressed.get("manual")
            ),
            settings_control_module.RUNTIME_SUPPRESSION_WAKE_WORD: bool(
                suppressed.get("wakeWord")
            ),
        }

    def settings_projection_for_wire(self):
        """One atomic projection bundle for the wire settings (AP-SRV-050 C3).

        ``settings_revision``, ``requestedSettings`` and ``effectiveSettings``
        all derive from the same ``SessionSettingsState.settings_projection()``
        snapshot - a snapshot can never span two settings revisions. The
        running-activation latch and the live runtime suppression are overlaid
        afterwards without re-reading the settings authority.
        """
        bundle = self.settings_state.settings_projection()
        requested = dict(bundle.requested_settings)
        effective = dict(bundle.effective_settings)
        latched = self._latched_wire_effective()
        if latched:
            for key in list(requested):
                if key in latched:
                    effective[key] = latched[key]
        live = self._suppression_live()
        for key, value in live.items():
            requested[key] = value
            effective[key] = value
        return settings_control_module.SessionSettingsProjection(
            settings_revision=bundle.settings_revision,
            requested_settings=settings_control_module._freeze(requested),
            effective_settings=settings_control_module._freeze(effective),
        )

    def settings_effective_for_wire(self):
        """The flat ``effectiveSettings`` projection for snapshot/events.

        While an activation runs, the latched view of that activation is
        published (next_activation values stay frozen per activation); in idle
        the session's current effective resolution is published. Runtime
        suppression is always read live from the controller - the control
        plane stores no suppression value.
        """
        return dict(self.settings_projection_for_wire().effective_settings)

    def settings_requested_for_wire(self):
        """The additive ``requestedSettings`` snapshot projection.

        Requested values come from the session settings authority filtered to
        server-managed session keys; runtime suppression keeps its live
        controller authority and is read live (AP-SRV-050 C2 F6). Reads never
        mutate a revision or the state version.
        """
        return dict(self.settings_projection_for_wire().requested_settings)

    def _new_activation_inputs(self):
        """``(wire_settings, timing_policy)`` for one activation admission.

        v2 sessions resolve both from the **one** atomic admission bundle
        (:meth:`SessionSettingsState.activation_admission_settings`): the wire
        effective settings and the six timing values come from exactly the same
        settings revision, so an admission can never publish a value that the
        controller would not really use (AP-SRV-050 C2 F3). Runtime suppression
        keeps its own live authority and is overlaid after the bundle. Legacy
        (v1) callers keep the nested legacy view and the controller defaults.
        """
        if self.canonical_ids:
            bundle = self.settings_state.activation_admission_settings()
            wire_settings = dict(bundle.effective_settings)
            controller = self._activation
            if controller is not None:
                try:
                    suppressed = (
                        (controller.trigger_state() or {}).get("suppressed")
                        or {}
                    )
                except Exception:  # noqa: BLE001 - defensive projection
                    suppressed = {}
                wire_settings[
                    settings_control_module.RUNTIME_SUPPRESSION_MANUAL
                ] = bool(suppressed.get("manual"))
                wire_settings[
                    settings_control_module.RUNTIME_SUPPRESSION_WAKE_WORD
                ] = bool(suppressed.get("wakeWord"))
            timings = bundle.timing_seconds
            policy = ActivationTimingPolicy(
                initial_speech_timeout=timings.get(
                    settings_control_module.ACTIVATION_INITIAL_SPEECH,
                    DEFAULT_INITIAL_SPEECH_TIMEOUT,
                ),
                followup_timeout=timings.get(
                    settings_control_module.ACTIVATION_FOLLOWUP,
                    DEFAULT_FOLLOWUP_TIMEOUT,
                ),
                segment_watchdog_initial=timings.get(
                    settings_control_module.ACTIVATION_WATCHDOG_INITIAL,
                    DEFAULT_SEGMENT_WATCHDOG_INITIAL,
                ),
                segment_watchdog_refresh=timings.get(
                    settings_control_module.ACTIVATION_WATCHDOG_REFRESH,
                    DEFAULT_SEGMENT_WATCHDOG_REFRESH,
                ),
                segment_watchdog_warning=timings.get(
                    settings_control_module.ACTIVATION_WATCHDOG_WARNING,
                    DEFAULT_SEGMENT_WATCHDOG_WARNING,
                ),
                closing_recovery_timeout=timings.get(
                    settings_control_module.ACTIVATION_CLOSING_RECOVERY,
                    DEFAULT_CLOSING_RECOVERY_TIMEOUT,
                ),
            )
            return wire_settings, policy
        return self._effective_activation_settings(), None

    # -- activation control -------------------------------------------------

    TRIGGER_ACTIONS = ACTIVATION_ACTIONS_PUBLIC
    TRIGGER_SOURCES = ACTIVATION_SOURCES_PUBLIC

    def _trigger_ack(
        self, command_id, accepted, reason, activation_id=None, phase=None
    ):
        return {
            "type": "trigger_ack",
            "commandId": command_id,
            "accepted": bool(accepted),
            "reason": reason,
            "activationId": activation_id,
            "phase": phase if phase is not None else self._current_phase(),
            "sessionId": self.session_id,
        }

    def _current_phase(self):
        activation = getattr(self, "_activation", None)
        if activation is None:
            return None
        return activation.snapshot().get("phase")

    def _current_activation_id(self):
        """The running activation id, used to correlate rejections as well."""
        activation = self._activation
        if activation is None:
            return None
        return activation.snapshot().get("activationId")

    def activation_snapshot(self):
        activation = self._activation
        if activation is None:
            return None
        return activation.snapshot()

    # -- protocol v2 seams ---------------------------------------------------
    #
    # Narrow, read-only accessors so the AP-SRV-040 wire layer never reaches
    # into private session state. None of them owns a decision.

    def activation_controller(self):
        """The foreground authority of this session, or ``None`` in legacy mode."""
        return self._activation

    def audio_available(self):
        """The generic device availability flag of this session."""
        with self.lock:
            return bool(self._audio_available)

    def active_segment_identity(self):
        """``(segmentId, segmentSequence)`` of the segment being recorded."""
        context = self._active_recording_context
        if context is None:
            return None, None
        return context.segment_id, context.segment_sequence

    def set_protocol_observer(self, observer):
        """Registers the single lifecycle subscriber of a protocol session."""
        with self.lock:
            self._protocol_observer = observer

    def protocol_replay_lookup(self, command_id, payload_key):
        """Shared ``commandId`` idempotency - there is only one replay cache."""
        return self._command_replay.lookup(command_id, payload_key)

    def protocol_replay_store(self, command_id, payload_key, result):
        """Occupies the replay identity of a command this session answered."""
        self._command_replay.store(command_id, payload_key, result)

    def _activation_correlation(self):
        """Fields every recording/transcription event carries in controlled mode.

        Safe to call without ``self.lock``: the controller synchronises itself
        and returns an immutable copy.
        """
        activation = getattr(self, "_activation", None)
        if activation is None:
            return {}
        snapshot = activation.snapshot()
        activation_id = snapshot.get("activationId")
        if not activation_id:
            return {}
        return {
            "activationId": activation_id,
            "activationSequence": snapshot.get("activationSequence"),
            "primarySource": snapshot.get("primarySource"),
            "sources": list(snapshot.get("sources") or ()),
        }

    def handle_trigger_command(self, data):
        """Processes one activation command and returns its ``trigger_ack``.

        Every syntactically valid command gets exactly one deterministic
        answer, and every answer carries the ``commandId`` so that the client
        can correlate it - rejections included.

        The order is deliberate and is what makes the replay rules hold:

        1. the envelope is prepared first; a usable ``commandId`` always owns a
           deterministic replay key, *including* fachlich rejected commands
           (F3);
        2. under the correct lock boundary the ``commandId`` is looked up - a
           replay returns the stored answer and never re-enters the state
           machine, a conflicting payload is refused without any effect;
        3. only then the command runs through the controller, which owns the
           phase matrix and the ``activationId`` validation.

        Explicit cancel is accepted under the outer dispatch boundary
        (``_ledger_dispatch_lock`` first), because its accept already sets the
        per-activation publication barrier (F4).
        """
        prepared = prepare_activation_command(data)
        if not prepared.command_id:
            # Keyless rejection: no usable commandId, no replay identity.
            return self._trigger_ack(
                "", False, prepared.rejection_reason or "invalid_payload"
            )

        if prepared.command is not None and prepared.command.action == CANCEL:
            return self._handle_cancel_accept(prepared)

        published = []
        with self.lock:
            lookup = self._command_replay.lookup(
                prepared.command_id, prepared.payload_key
            )
            if lookup.state == REPLAY:
                return dict(lookup.result)
            if lookup.state == CONFLICT:
                # A conflict is deliberately not stored: the original entry
                # stays authoritative for its own payload.
                return self._trigger_ack(
                    prepared.command_id,
                    False,
                    "command_id_conflict",
                    self._current_activation_id(),
                )

            if prepared.rejection_reason is not None:
                # A fachlich rejected command with a usable commandId still
                # occupies its replay identity (F3): the stored first answer
                # stays authoritative.
                ack = self._trigger_ack(
                    prepared.command_id,
                    False,
                    prepared.rejection_reason,
                    self._current_activation_id(),
                )
                self._command_replay.store(
                    prepared.command_id, prepared.payload_key, ack
                )
                return dict(ack)

            ack = self._run_activation_command_locked(
                prepared.command, published
            )
            self._command_replay.store(
                prepared.command_id, prepared.payload_key, ack
            )

        self._publish_collected_events(published)
        return dict(ack)

    def _handle_cancel_accept(self, prepared):
        """Cancel acceptance under the total order.

        The cancel barrier must be serialised with every other ledger
        publication, so the whole acceptance runs under ``_ledger_dispatch_lock``
        first and ``self.lock`` second:

        ``_ledger_dispatch_lock -> self.lock -> controller decides -> closing_input
        -> SegmentLedger.mark_cancel_requested() -> ack built and stored
        -> self.lock released -> barrier LedgerUpdate applied visibly (still
        under dispatch) -> _ledger_dispatch_lock released -> physical close``

        A final thread that already holds the dispatch boundary publishes its
        result before the cancel is accepted (Fall A); a cancel that wins the
        boundary makes every later final of this activation a ``cancelled``
        terminal (Fall B). There is no state in which a publication can escape
        after the cancel was accepted (F4).
        """
        cancel_update = None
        plan = None
        with self._ledger_dispatch_lock:
            with self.lock:
                if self._activation is None:
                    return self._trigger_ack(
                        prepared.command_id,
                        False,
                        "controlled_activation_disabled",
                    )
                if self.status == "closed":
                    return self._trigger_ack(
                        prepared.command_id,
                        False,
                        "session_closed",
                        self._current_activation_id(),
                    )
                if not self.streaming:
                    return self._trigger_ack(
                        prepared.command_id,
                        False,
                        "stream_not_started",
                        self._current_activation_id(),
                    )

                lookup = self._command_replay.lookup(
                    prepared.command_id, prepared.payload_key
                )
                if lookup.state == REPLAY:
                    return dict(lookup.result)
                if lookup.state == CONFLICT:
                    return self._trigger_ack(
                        prepared.command_id,
                        False,
                        "command_id_conflict",
                        self._current_activation_id(),
                    )

                decision = self._activation.cancel(
                    activation_id=prepared.command.activation_id,
                    command_id=prepared.command.command_id,
                )
                activation_id = self._apply_activation_decision_locked(
                    CANCEL, decision, [], command_id=prepared.command.command_id
                )
                plan = decision.snapshot.get("__close_plan__")
                if plan is not None:
                    close_reason = plan.reason or "cancelled"
                    cancel_update = self.segment_ledger.mark_cancel_requested(
                        plan.activation_id, close_reason
                    )
                    # Deterministic test hook (T9b): lets a test block the
                    # cancel accept *after* the barrier is set but while the
                    # dispatch boundary and the session lock are still held.
                    hook = getattr(self, "_test_cancel_after_barrier", None)
                    if hook is not None:
                        hook()
                ack = self._trigger_ack(
                    prepared.command_id,
                    decision.accepted,
                    decision.reason,
                    activation_id,
                )
                self._command_replay.store(
                    prepared.command_id, prepared.payload_key, ack
                )
            if cancel_update is not None:
                self._apply_ledger_update(cancel_update)

        if plan is not None:
            self._run_input_close(plan)
        return dict(ack)

    def _run_activation_command_locked(self, command, published):
        """Applies one already de-duplicated command. Requires ``self.lock``."""
        if self._activation is None:
            return self._trigger_ack(
                command.command_id, False, "controlled_activation_disabled"
            )

        # Stream lifecycle: triggers are only meaningful while the session is
        # streaming audio. Before start, after stop and after close the command
        # is rejected - but still acknowledged and correlated.
        if self.status == "closed":
            return self._trigger_ack(
                command.command_id,
                False,
                "session_closed",
                self._current_activation_id(),
            )
        if not self.streaming:
            return self._trigger_ack(
                command.command_id,
                False,
                "stream_not_started",
                self._current_activation_id(),
            )

        if command.action == ACTIVATE:
            if not self._audio_available:
                # Opening an activation without an input device would produce
                # a window that can never receive speech.
                return self._trigger_ack(
                    command.command_id,
                    False,
                    "audio_unavailable",
                    self._current_activation_id(),
                )
            activation_settings, timing_policy = self._new_activation_inputs()
            decision = self._activation.activate(
                command.source,
                activation_settings,
                timing_policy=timing_policy,
            )
        elif command.action == REFRESH:
            decision = self._activation.refresh(
                activation_id=command.activation_id
            )
        elif command.action == FINISH:
            decision = self._activation.finish(
                activation_id=command.activation_id,
                command_id=command.command_id,
            )
        else:  # pragma: no cover - the parser admits no other action
            return self._trigger_ack(
                command.command_id, False, "invalid_action"
            )

        activation_id = self._apply_activation_decision_locked(
            command.action, decision, published, command_id=command.command_id
        )
        return self._trigger_ack(
            command.command_id,
            decision.accepted,
            decision.reason,
            activation_id,
        )

    def handle_audio_availability_command(self, data):
        """Processes the generic ``audioAvailable`` status of one session.

        The server never learns *which* device changed or why; that stays with
        the client (DEVICE-01/DEVICE-02). Losing audio cancels the open
        activation and leaves the session and its background ledger intact
        (DEVICE-03). An audio loss that cancels an activation uses the same
        publication barrier as an explicit cancel (F7/T8), but the
        availability ``commandId`` stays replay-/ack-identity only and never
        becomes a finish-/cancel-``causedByCommandId``.

        The final v2 message (``audio_availability.set``) belongs to
        AP-SRV-040; this is the additive v1 form of the same server policy.
        """
        if not isinstance(data, dict):
            return self._audio_availability_ack("", False, "invalid_payload")

        raw_command_id = data.get("commandId")
        if raw_command_id is not None and not isinstance(raw_command_id, str):
            return self._audio_availability_ack("", False, "invalid_command_id")
        command_id = str(raw_command_id or "").strip()
        if not command_id:
            return self._audio_availability_ack("", False, "missing_command_id")

        available = data.get("audioAvailable")
        if not isinstance(available, bool):
            return self._audio_availability_ack(
                command_id, False, "invalid_payload"
            )

        payload_key = ("audio_availability", available)
        published = []

        def store_and_return(ack):
            self._command_replay.store(command_id, payload_key, ack)
            return dict(ack)

        if available:
            with self.lock:
                lookup = self._command_replay.lookup(command_id, payload_key)
                if lookup.state == REPLAY:
                    return dict(lookup.result)
                if lookup.state == CONFLICT:
                    return self._audio_availability_ack(
                        command_id, False, "command_id_conflict"
                    )
                changed = self._audio_available != available
                self._audio_available = available
                reason = "applied" if changed else "no_change"
                ack = self._audio_availability_ack(command_id, True, reason)
                return store_and_return(ack)

        # ``available=False``: cancels the open activation with the same
        # publication barrier as an explicit cancel.
        cancel_update = None
        plan = None
        discard = []
        with self._ledger_dispatch_lock:
            with self.lock:
                lookup = self._command_replay.lookup(command_id, payload_key)
                if lookup.state == REPLAY:
                    return dict(lookup.result)
                if lookup.state == CONFLICT:
                    return self._audio_availability_ack(
                        command_id, False, "command_id_conflict"
                    )
                changed = self._audio_available != available
                self._audio_available = available
                reason = "applied" if changed else "no_change"
                if self._activation is not None:
                    decision = self._activation.audio_unavailable()
                    activation_id = self._apply_activation_decision_locked(
                        "audio_unavailable",
                        decision,
                        discard,
                        command_id=None,
                    )
                    plan = decision.snapshot.get("__close_plan__")
                    if plan is not None:
                        cancel_update = self.segment_ledger.mark_cancel_requested(
                            plan.activation_id, "cancelled"
                        )
                ack = self._audio_availability_ack(command_id, True, reason)
                self._command_replay.store(command_id, payload_key, ack)
            if cancel_update is not None:
                self._apply_ledger_update(cancel_update)

        if plan is not None:
            self._run_input_close(plan)
        return dict(ack)

    def _audio_availability_ack(self, command_id, accepted, reason):
        return {
            "type": "audio_availability_ack",
            "commandId": command_id,
            "accepted": bool(accepted),
            "reason": reason,
            "audioAvailable": bool(self._audio_available),
            "activationId": self._current_activation_id(),
            "phase": self._current_phase(),
            "sessionId": self.session_id,
        }

    def _build_close_plan_locked(self, snapshot, *, requested_by_command_id=None,
                                 recovery=False):
        """Creates the immutable :class:`InputClosePlan` for a close decision.

        Requires ``self.lock``. The plan captures the accepted activation
        identity, gate generation, close reason/cause and - when a control
        command caused the close - the command identity from the persistent
        :class:`CloseContext` (F2/F7). A recovery plan keeps the same
        identity and requests the recovery orchestrator.
        """
        activation_id = (
            snapshot.get("activationId")
            or snapshot.get("closedActivationId")
        )
        activation_sequence = (
            snapshot.get("activationSequence")
            or snapshot.get("closedActivationSequence")
            or 0
        )
        reason = snapshot.get("closeReason") or "input_closed"
        cause = snapshot.get("closeCause") or snapshot.get("closeReason")
        requested_by_command_id = snapshot.get("closeRequestedByCommandId")
        requested_by_action = snapshot.get("closeRequestedByAction")
        close_reason = reason or "cancelled"
        plan = InputClosePlan(
            activation_id=activation_id or "",
            activation_sequence=activation_sequence,
            gate_generation=snapshot.get("generation") or activation_sequence,
            reason=close_reason,
            cause=cause or close_reason,
            requested_by_command_id=requested_by_command_id,
            requested_by_action=requested_by_action,
            cancel_pending=self._cancel_close_reason(close_reason),
            recovery=recovery,
        )
        snapshot["__close_plan__"] = plan
        return plan

    def _apply_activation_decision_locked(
        self, action, decision, published, command_id=None
    ):
        """Turns a controller decision into gate, timer and event side effects.

        Must be called with ``self.lock`` held. Events are collected into
        ``published`` and emitted by the caller **after** the lock is released,
        so that publishing can never deadlock against a recorder callback.

        Since AP-SRV-030 C2, entering ``closing_input`` is strictly a two-phase
        close:

        * **Phase A (here):** the controller moves to ``closing_input`` and
          creates the persistent :class:`CloseContext`. The session only builds
          the immutable :class:`InputClosePlan`; no gate close, no recorder
          flush and no idle happen under ``self.lock``.
        * **Phase B:** ``_run_input_close(plan)`` runs *outside* ``self.lock``
          and outside ``_ledger_dispatch_lock`` and performs the actual close.
        """
        snapshot = decision.snapshot
        activation_id = (
            snapshot.get("activationId") or snapshot.get("closedActivationId")
        )

        if not decision.accepted:
            return activation_id

        if not decision.changed:
            # An accepted but effect-free decision - the idempotent state
            # answer of a repeated finish/cancel in ``closing_input``, or a
            # refresh that did not move a longer remaining deadline. It must
            # not touch the gate, the ledger or the armed timer.
            return activation_id

        if decision.reason == "watchdog_warning":
            published.append(
                ("watchdog_warning", self._watchdog_warning_fields(snapshot))
            )
            return activation_id

        if snapshot.get("phase") == "closing_input":
            # Phase A only. For a recovery the controller has already consumed
            # its recovery deadline but stays in closing_input; the orchestration
            # is the same, only marked to run the hard cleanup first.
            recovery = bool(snapshot.get("recoveryRequested"))
            plan = self._build_close_plan_locked(
                snapshot,
                requested_by_command_id=command_id,
                recovery=recovery,
            )
            # The recovery deadline armed by the controller keeps the single
            # worker honest while the physical close runs.
            self._arm_activation_timer_locked(snapshot)
            published.append(("__input_close__", plan))
            return activation_id

        if decision.reason == "activated":
            self._open_ledger_activation(snapshot)

        generation = snapshot.get("generation")
        window_open = bool(snapshot.get("windowOpen"))
        if window_open:
            open_id = snapshot.get("activationId")
            if open_id:
                try:
                    self.recorder.open_controlled_activation(
                        open_id, replace=True, generation=generation
                    )
                except Exception:
                    LOGGER.debug(
                        "Controlled Gate konnte für %s nicht geöffnet werden",
                        self.session_id,
                        exc_info=True,
                    )

        self._arm_activation_timer_locked(snapshot)

        event = self._activation_event_name(action, decision.reason)
        if event is not None:
            fields = self._activation_event_fields(snapshot)
            published.append((event, fields))
        return activation_id

    @staticmethod
    def _cancel_close_reason(close_reason):
        """Whether a close reason suppresses still unpublished results.

        Finish, every timer expiry and the watchdog keep processing the audio
        that was already accepted; only a deliberate cancel, a lost device, a
        stopped stream or a closed session suppress it.
        """
        return close_reason in {
            "cancelled",
            "client_cancel",
            "session_closed",
            "stream_stopped",
        }

    def _reserve_input_close_event(self, plan, *, recovery=False):
        """Register the exactly-once logical input-close event before ``idle``.

        This does not perform manager/network publication. The session-local
        record exists while the controller is still in ``closing_input``.
        AP-SRV-040 can replace this seam with the v2 event registry without
        changing the close ordering established here.
        """
        key = (str(plan.activation_id), int(plan.activation_sequence))
        with self.lock:
            snapshot = self._activation.snapshot()
            sequence = snapshot.get("activationSequence")
            if (
                snapshot.get("phase") != "closing_input"
                or str(snapshot.get("activationId") or "") != key[0]
                or sequence is None
                or int(sequence) != key[1]
            ):
                return None

            if key in self._registered_input_close_events:
                return key

            fields = self._activation_event_fields(snapshot)
            # The event describes the state established by this close. The actual
            # foreground transition follows immediately after this registration.
            fields["phase"] = "idle"
            fields["reason"] = plan.reason
            # Captured before the ledger close, because closing an activation
            # whose segments are already terminal drops its record at once.
            fields["acceptedSegmentCount"] = int(
                getattr(plan, "accepted_segment_count", 0) or 0
            )
            if recovery:
                fields["cause"] = "closing_recovery_timeout"
                fields["recovered"] = True
                fields["causedByCommandId"] = None
            else:
                fields["cause"] = plan.cause
                fields["causedByCommandId"] = (
                    plan.requested_by_command_id
                    if plan.requested_by_action in ("finish", "cancel")
                    and plan.requested_by_command_id
                    else None
                )

            self._registered_input_close_events[key] = fields
            return key

    def _discard_registered_input_close_event(self, key):
        if key is None:
            return False
        with self.lock:
            return self._registered_input_close_events.pop(key, None) is not None

    def _publish_registered_input_close_event(self, key):
        """Publish an already-registered close event after lock release.

        On publisher failure the logical record remains present instead of being
        silently lost; SRV-040 can expose/resynchronise that record later.
        """
        if key is None:
            return False
        with self.lock:
            fields = self._registered_input_close_events.get(key)
            if fields is None:
                return False
            fields = dict(fields)

        try:
            self._publish_timeline_event("activation_closed", **fields)
        except Exception:
            LOGGER.exception(
                "Registriertes Input-Close-Event für %s konnte nicht publiziert werden",
                self.session_id,
            )
            return False

        with self.lock:
            self._registered_input_close_events.pop(key, None)
        return True

    def _run_input_close(self, plan):
        """Execute normal Phase B with the full PHASE-04 admission barrier.

        Strict order:
          1. generation-bound gate close,
          2. recorder stop/flush,
          3. ledger input-close registration,
          4. logical lifecycle-event registration,
          5. identity-bound ``input_closed()`` -> idle,
          6. transport publication of the already-registered event.

        Recorder/gate operations run outside both session and dispatch locks.
        """
        if plan.recovery:
            self._run_recovery_close(plan)
            return

        self._notify_input_closing(plan)
        activation_id = plan.activation_id
        generation = plan.gate_generation

        gate_closed = True
        try:
            self.recorder.close_controlled_activation(
                activation_id, generation=generation
            )
        except Exception:
            gate_closed = False
            LOGGER.debug(
                "Controlled Gate konnte für %s nicht geschlossen werden",
                self.session_id,
                exc_info=True,
            )

        recorder_ok = True
        if gate_closed:
            try:
                if bool(getattr(self.recorder, "is_recording", False)):
                    self.recorder.flush_buffered_audio()
            except Exception:
                recorder_ok = False
                LOGGER.exception(
                    "Controlled Input konnte für %s nicht geschlossen werden",
                    self.session_id,
                )

        if not (gate_closed and recorder_ok):
            LOGGER.debug(
                "Input-Close für %s bleibt in closing_input - Recovery übernimmt",
                self.session_id,
            )
            return

        plan = replace(
            plan,
            accepted_segment_count=self.segment_ledger.accepted_segment_count(
                activation_id
            ),
        )
        self._close_ledger_activation(
            activation_id,
            plan.reason,
            requested_terminal=("cancelled" if plan.cancel_pending else None),
            cancel_pending=plan.cancel_pending,
        )

        event_key = self._reserve_input_close_event(plan, recovery=False)
        if event_key is None:
            # A concurrent stream/session reset already won ownership.
            return

        with self.lock:
            completed = self._activation.input_closed(
                activation_id=activation_id,
                activation_sequence=plan.activation_sequence,
            )
            self._arm_activation_timer_locked(
                completed.snapshot
                if completed is not None
                else self._activation.snapshot()
            )

        if completed is None or not completed.accepted:
            self._discard_registered_input_close_event(event_key)
            return

        self._publish_registered_input_close_event(event_key)

    def _run_recovery_close(self, plan):
        """Hard recovery for a stuck ``closing_input`` (PHASE-05).

        If cleanup becomes safe, use the same PHASE-04 ordering as normal close.
        If even the hard abort cannot make the old input path safe, terminally
        close the session instead of leaving a live session stuck forever.
        """
        self._notify_input_closing(plan)
        activation_id = plan.activation_id

        try:
            self.recorder.abort_controlled_activation()
        except Exception:
            LOGGER.debug(
                "Controlled Gate konnte für %s im Recovery nicht abgebrochen werden",
                self.session_id,
                exc_info=True,
            )

        try:
            if bool(getattr(self.recorder, "is_recording", False)):
                self.recorder.flush_buffered_audio()
        except Exception:
            LOGGER.exception(
                "Recorder konnte für %s im Recovery nicht geschlossen werden",
                self.session_id,
            )
            abort_method = getattr(self.recorder, "abort", None)
            if callable(abort_method):
                try:
                    abort_method()
                except Exception:
                    LOGGER.exception(
                        "Harter Recorder-Abbruch für %s fehlgeschlagen",
                        self.session_id,
                    )

        try:
            gate_active = bool(
                self.recorder.controlled_activation_state().get("active")
            )
        except Exception:  # pragma: no cover - fakes may differ
            gate_active = bool(getattr(self.recorder, "is_recording", False))
        close_safe = not gate_active

        with self.lock:
            orphaned = self._active_recording_context
            if orphaned is not None and (
                activation_id is None or orphaned.activation_id == activation_id
            ):
                self._active_recording_context = None
                try:
                    self.recorder._active_recording_context = None
                except Exception:  # pragma: no cover - fakes may differ
                    pass
            else:
                orphaned = None

        if not close_safe:
            self.fail_closed_for_recovery(activation_id)
            return

        if orphaned is not None:
            self._dispatch_ledger_operation(
                self.segment_ledger.resolve_terminal,
                orphaned,
                "failed",
                "closing_recovery_timeout",
            )

        if activation_id:
            plan = replace(
                plan,
                accepted_segment_count=(
                    self.segment_ledger.accepted_segment_count(activation_id)
                ),
            )
            self._close_ledger_activation(
                activation_id,
                plan.reason,
                requested_terminal=("cancelled" if plan.cancel_pending else None),
                cancel_pending=plan.cancel_pending,
            )

        event_key = self._reserve_input_close_event(plan, recovery=True)
        if event_key is None:
            return

        with self.lock:
            completed = self._activation.input_closed(
                activation_id=activation_id,
                activation_sequence=plan.activation_sequence,
            )
            self._arm_activation_timer_locked(
                completed.snapshot
                if completed is not None
                else self._activation.snapshot()
            )

        if completed is None or not completed.accepted:
            self._discard_registered_input_close_event(event_key)
            return

        self._publish_registered_input_close_event(event_key)

    def fail_closed_for_recovery(self, activation_id):
        """Terminally close a session whose input path cannot be made safe.

        A live ``closing_input`` may not become a permanent state. The fallback
        therefore uses the existing terminal session-close lifecycle instead of
        claiming a reusable ``idle``.
        """
        with self.lock:
            if self.status == "closed":
                return False
            self._audio_available = False

        LOGGER.error(
            "Recovery für %s konnte den Eingabepfad nicht sicher schließen; "
            "Sitzung wird technisch beendet",
            self.session_id,
        )

        try:
            self.service.manager.publish_session(
                self.session_id,
                {
                    "type": "warning",
                    "sessionId": self.session_id,
                    "message": (
                        "Der Eingabepfad konnte nicht sicher geschlossen werden; "
                        "die Sitzung wird beendet und muss neu aufgebaut werden."
                    ),
                    "recovery": "session_terminated",
                    "activationId": activation_id,
                },
            )
        except Exception:
            LOGGER.debug(
                "Recovery-Warnung für %s konnte nicht publiziert werden",
                self.session_id,
                exc_info=True,
            )

        try:
            self.close()
        except Exception:
            # close() marks the session terminal before downstream cleanup. Keep
            # that terminal state even if a best-effort cleanup operation raises.
            LOGGER.exception(
                "Terminaler Session-Abschluss nach Recoveryfehler für %s "
                "war nur teilweise erfolgreich",
                self.session_id,
            )
            with self.lock:
                self.streaming = False
                self.status = "closed"
                self._activation_timer_generation += 1
                self._armed_timer_token = None
            try:
                self._dispatch_ledger_operation(
                    self.segment_ledger.cancel_all, "session_closed"
                )
            except Exception:
                LOGGER.exception(
                    "Ledger konnte nach terminalem Recoveryfehler für %s "
                    "nicht vollständig abgeräumt werden",
                    self.session_id,
                )
            return False

        return True

    def _watchdog_warning_fields(self, snapshot):
        context = self._active_recording_context
        deadline = snapshot.get("deadline")
        return {
            "activationId": snapshot.get("activationId"),
            "activationSequence": snapshot.get("activationSequence"),
            # ``segment_id`` is a named parameter of the timeline publisher, so
            # it must not travel as a plain field.
            "segment_id": None if context is None else context.segment_id,
            "segmentSequence": (
                None if context is None else context.segment_sequence
            ),
            "phase": snapshot.get("phase"),
            "timerRevision": snapshot.get("timerRevision"),
            "remainingSeconds": (
                None if deadline is None
                else max(0.0, float(deadline) - time.monotonic())
            ),
        }

    @staticmethod
    def _activation_event_name(action, reason):
        if reason == "activated":
            return "activation_started"
        if reason == "refreshed":
            return "activation_refreshed"
        if reason in {
            "finished",
            "cancelled",
            "timed_out",
            "segment_watchdog_timeout",
        }:
            return "activation_closed"
        if reason == "recording_started":
            return None
        if reason == "followup_started":
            return None
        return None

    @staticmethod
    def _activation_event_fields(snapshot):
        activation_id = (
            snapshot.get("activationId") or snapshot.get("closedActivationId")
        )
        sources = snapshot.get("sources") or snapshot.get("closedSources") or ()
        fields = {
            "activationId": activation_id,
            "generation": snapshot.get("generation"),
            "activationSequence": (
                snapshot.get("closedActivationSequence")
                or snapshot.get("activationSequence")
            ),
            "primarySource": (
                snapshot.get("primarySource")
                or snapshot.get("closedPrimarySource")
            ),
            "sources": list(sources),
            "phase": snapshot.get("phase"),
            "timerRevision": snapshot.get("timerRevision"),
        }
        if snapshot.get("closeReason"):
            fields["reason"] = snapshot["closeReason"]
            fields["cause"] = (
                snapshot.get("closeCause") or snapshot["closeReason"]
            )
        return fields

    def _arm_activation_timer_locked(self, snapshot):
        """Owns exactly one scheduled worker per armed deadline.

        The worker is bound to the controller's :class:`TimerToken`, which
        carries the activation id, the activation sequence, the
        ``timerRevision``, the phase and the segment token. A worker whose
        token is no longer the armed one stops without touching anything, and
        an unchanged token deliberately does not spawn a second worker - a
        watchdog warning, for instance, keeps the very same deadline.
        """
        token = snapshot.get("timerToken")
        deadline = snapshot.get("deadline")
        if deadline is None or token is None or token.kind is None:
            self._activation_timer_generation += 1
            self._armed_timer_token = None
            return
        if token == getattr(self, "_armed_timer_token", None):
            return

        self._activation_timer_generation += 1
        self._armed_timer_token = token
        thread = threading.Thread(
            target=self._activation_timer_worker,
            args=(token,),
            name=f"VoiceSTTActivationTimeout-{self.session_id}",
            daemon=True,
        )
        thread.start()

    def _next_timer_due_locked(self, token):
        """The next monotonic instant this worker has to look at, or ``None``."""
        if getattr(self, "_armed_timer_token", None) != token:
            return None
        activation = self._activation
        if activation is None:
            return None
        snapshot = activation.snapshot()
        if snapshot.get("timerToken") != token:
            return None
        deadline = snapshot.get("deadline")
        if deadline is None:
            return None
        warning = snapshot.get("warningDeadline")
        if warning is not None and warning < deadline:
            return min(float(warning), float(deadline))
        return float(deadline)

    def _activation_timer_worker(self, token):
        """Drives one armed deadline, including its optional warning."""
        while True:
            with self.lock:
                due = self._next_timer_due_locked(token)
            if due is None:
                return
            remaining = due - time.monotonic()
            if remaining > 0 and self.service.stop_event.wait(timeout=remaining):
                return

            published = []
            waiting_state = None
            expired = False
            with self.lock:
                if getattr(self, "_armed_timer_token", None) != token:
                    # A newer timer took over; this one has nothing to do.
                    return
                activation = self._activation
                if activation is None:
                    return
                decision = activation.tick(token)
                if not decision.accepted:
                    if decision.reason != "not_due":
                        return
                    # `Event.wait` may return marginally early - on Windows the
                    # timer granularity is around 15 ms. Treating that as "the
                    # timeout did not happen" would drop the deadline forever,
                    # so the loop simply waits out the rest.
                    continue
                self._apply_activation_decision_locked(
                    "timer", decision, published
                )
                expired = decision.reason != "watchdog_warning"
                if expired:
                    waiting_state = self._waiting_state_locked()
            self._publish_collected_events(published)
            if expired:
                self.publish_status(waiting_state)
                return

    def _reset_activation_locked(self, reason):
        """Drops any activation and closes the gate. Used by stop/close/clear.

        A reconnect must never revive an activation, and a stopped stream must
        never leave the recorder gate open.
        """
        activation = self._activation
        self._activation_timer_generation += 1
        self._armed_timer_token = None
        if activation is None:
            return None
        decision = activation.reset()
        try:
            self.recorder.abort_controlled_activation()
        except Exception:
            LOGGER.debug(
                "Controlled Gate konnte für %s nicht zurückgesetzt werden",
                self.session_id,
                exc_info=True,
            )
        if not decision.changed:
            return None
        fields = self._activation_event_fields(decision.snapshot)
        fields["reason"] = reason
        return ("activation_closed", fields)

    def _open_ledger_activation(self, snapshot):
        activation_id = snapshot.get("activationId")
        if not activation_id:
            return False
        return self.segment_ledger.open_activation(
            activation_id,
            snapshot.get("activationSequence") or snapshot.get("generation") or 0,
            snapshot.get("effectiveSettings") or {},
        )

    def _close_ledger_activation(
        self,
        activation_id,
        reason,
        *,
        requested_terminal=None,
        cancel_pending=False,
    ):
        if not activation_id:
            return False
        update = self._dispatch_ledger_operation(
            self.segment_ledger.close_activation,
            activation_id,
            reason,
            requested_terminal=requested_terminal,
            cancel_pending=cancel_pending,
        )
        return update.changed

    def _dispatch_ledger_operation(self, operation, *args, **kwargs):
        """Serializes ledger mutation together with all observable output.

        Lock order (L1/L4): this boundary is the *outermost* lock, so the only
        permitted order is ``_ledger_dispatch_lock`` then (briefly)
        ``self.lock`` for a session snapshot read. Callers must not hold
        ``self.lock`` here, and no recorder operation that can synchronously
        fire callbacks (flush/stop/abort) may run under either lock (L5).
        Because these callers deliberately never hold ``self.lock`` while a
        dispatch is in flight, a dispatch can never wait on a session lock
        that is held by the same input-close path (T10).
        """
        with self._ledger_dispatch_lock:
            update = operation(*args, **kwargs)
            self._apply_ledger_update(update)
            return update

    def _apply_ledger_update(self, update: LedgerUpdate):
        for resolution in update.resolutions:
            self._publish_noncompleted_segment_terminal(resolution)
        for publication in update.publications:
            self._publish_ordered_final(publication.context, publication.text)
        for terminal in update.activation_terminals:
            self._publish_timeline_event(
                "activation_drained",
                activationId=terminal.activation_id,
                activationSequence=terminal.activation_sequence,
                state=terminal.state,
                reason=terminal.reason,
                acceptedSegmentCount=terminal.accepted_segment_count,
                terminalSegmentCount=terminal.terminal_segment_count,
            )

    def _publish_collected_events(self, published):
        for event, fields in published:
            if event == "__input_close__":
                # Phase B runs outside self.lock and outside the dispatch lock.
                self._run_input_close(fields)
            else:
                self._publish_timeline_event(event, **fields)

    def _publish_noncompleted_segment_terminal(self, resolution):
        context = resolution.context
        timestamp = time.time()
        segment = self._timeline_snapshot(context.segment_id)
        event = {
            "discarded": "final_transcript_discarded",
            "cancelled": "final_transcript_cancelled",
            "failed": "final_transcript_failed",
        }[resolution.state]
        self._publish_timeline_event(
            event,
            timestamp=timestamp,
            segment_id=context.segment_id,
            segment=segment,
            reason=resolution.reason,
            activationId=context.activation_id,
            activationSequence=context.activation_sequence,
            segmentSequence=context.segment_sequence,
            requestId=context.request_id,
        )
        self._emit_realtime_summary(context.segment_id, timestamp, segment)
        self._emit_structured_event(
            "transcription",
            f"transcription.{resolution.state}",
            segment_id=context.segment_id,
            severity=("error" if resolution.state == "failed" else "warning"),
            reason=resolution.reason,
            requestId=context.request_id,
            activationId=context.activation_id,
            activationSequence=context.activation_sequence,
            segmentSequence=context.segment_sequence,
            language=self.settings.language,
            engine=self.settings.transcription_engine,
            model=self.settings.model,
        )

    def current_transcription_context(self):
        with self.lock:
            return (
                getattr(self.recorder, "_current_transcription_context", None)
                or self._active_text_context
                or self._last_final_context
            )

    def public_settings(self):
        return public_session_settings(self.settings)

    def snapshot(self):
        with self.lock:
            state = self.status
            streaming = self.streaming
            recording = bool(getattr(self.recorder, "is_recording", False))
        return {
            "sessionId": self.session_id,
            "streaming": streaming,
            "recording": recording,
            "state": state,
            "wakeWordEnabled": self.settings.wake_word_enabled(),
            "sessionConfig": self.session_config_dict(),
            "currentSegmentId": self.segment_state.current(),
            "currentSegment": self.timeline.snapshot(self.segment_state.current()),
            "queueDepth": self._recorder_queue_depth(),
            "recordingSeconds": self.recording_sample_count / float(SERVER_SAMPLE_RATE),
            "droppedAudioChunks": self.dropped_audio_chunks,
            "rejectedAudioChunks": self.rejected_audio_chunks,
            "coalescedRealtime": self.coalesced_realtime,
            "staleRealtimeDiscarded": self.stale_realtime_discarded,
            "cancelledJobs": self.cancelled_jobs,
            "realtimeSubmitted": self.realtime_submitted,
            "finalSubmitted": self.final_submitted,
            "realtimeCompleted": self.realtime_completed,
            "finalCompleted": self.final_completed,
            "realtimeRejected": self.realtime_rejected,
            "finalRejected": self.final_rejected,
            "forcedFinalizations": self.forced_finalizations,
            "droppedRecordedSegments": self.dropped_recorded_segments,
            "segmentLedger": self.segment_ledger.snapshot(),
            "queueDelay": {
                "realtime": self.queue_delay["realtime"].snapshot_ms(),
                "final": self.queue_delay["final"].snapshot_ms(),
            },
            "inferenceDuration": {
                "realtime": self.inference_duration["realtime"].snapshot_ms(),
                "final": self.inference_duration["final"].snapshot_ms(),
            },
            "totalLatency": {
                "realtime": self.total_latency["realtime"].snapshot_ms(),
                "final": self.total_latency["final"].snapshot_ms(),
            },
        }

    def _text_worker(self):
        while not self.service.stop_event.is_set():
            try:
                text = self.recorder.text()
            except Exception as exc:
                if getattr(self.recorder, "is_shut_down", False):
                    break
                LOGGER.exception("Textschleife des Sitzungs-Recorders fehlgeschlagen")
                with self.lock:
                    context = self._active_text_context
                    self._active_text_context = None
                segment_id = (
                    context.segment_id
                    if context is not None
                    else self.segment_state.current()
                )
                if context is not None:
                    self._dispatch_ledger_operation(
                        self.segment_ledger.resolve_terminal,
                        context,
                        "failed",
                        str(exc),
                    )
                if context is None:
                    self._emit_structured_event(
                        "transcription",
                        "transcription.failed",
                        segment_id=segment_id,
                        severity="error",
                        error=str(exc),
                        where="recorder",
                    )
                self.service.manager.publish_session(
                    self.session_id,
                    {
                        "type": "error",
                        "sessionId": self.session_id,
                        "message": str(exc),
                        "where": "recorder",
                    },
                )
                time.sleep(0.1)
                continue

            if getattr(self.recorder, "is_shut_down", False):
                break
            with self.lock:
                context = self._active_text_context
                self._active_text_context = None
            if context is None:
                continue
            text = (text or "").strip()
            if not text:
                self._publish_discarded_empty_final(
                    context=context,
                )
                continue
            self._publish_final_text(
                text,
                context=context,
            )

    def _compat_final_context(self, text_generation, expected_segment_id=None):
        with self._ledger_dispatch_lock:
            with self.lock:
                if text_generation != self.generation:
                    return None
                context = self._last_final_context
                if context is not None and (
                    expected_segment_id is None
                    or context.segment_id == expected_segment_id
                ):
                    return context
                segment_id = (
                    self.segment_state.current()
                    if expected_segment_id is None
                    else expected_segment_id
                )
                if segment_id != self.segment_state.current():
                    return None
                self._legacy_activation_sequence += 1
                activation_id = (
                    f"legacy-{self.session_id}-"
                    f"{self._legacy_activation_sequence}"
                )
                self.segment_ledger.open_activation(
                    activation_id,
                    self._legacy_activation_sequence,
                    self._effective_activation_settings(),
                )
                context = self.segment_ledger.accept_segment(
                    activation_id, segment_id
                )
                self.segment_state.final()
                # The segment is still pending, so close cannot produce an
                # observable update here. Holding the dispatch lock still
                # keeps this compatibility mutation ordered with terminals.
                self.segment_ledger.close_activation(
                    activation_id, "compat_final"
                )
                self._last_final_context = context
                return context

    def _publish_discarded_empty_final(
        self,
        text_generation=None,
        expected_segment_id=None,
        context=None,
    ):
        if context is None:
            context = self._compat_final_context(
                text_generation, expected_segment_id
            )
        if context is None:
            return False
        update = self._dispatch_ledger_operation(
            self.segment_ledger.resolve_terminal,
            context,
            "discarded",
            "empty_final",
        )
        if update.changed:
            with self.lock:
                foreground = self.status
            if foreground not in {"recording", "closed"}:
                self.publish_status(self._waiting_state_locked())
        return update.changed

    def _publish_final_text(
        self,
        text,
        text_generation=None,
        expected_segment_id=None,
        context=None,
    ):
        if context is None:
            context = self._compat_final_context(
                text_generation, expected_segment_id
            )
        if context is None:
            return False
        update = self._dispatch_ledger_operation(
            self.segment_ledger.resolve_completed,
            context,
            text,
        )
        return update.changed

    def _publish_ordered_final(self, context, text):
        segment_id = context.segment_id
        segment = self._timeline_snapshot(segment_id)
        timestamp = time.time()
        payload = {
            "type": "final",
            "sessionId": self.session_id,
            "segmentId": segment_id,
            "text": text,
            "timestamp": timestamp,
            "timestampIso": timestamp_iso(timestamp),
            "requestId": context.request_id,
            "activationId": context.activation_id,
            "activationSequence": context.activation_sequence,
            "segmentSequence": context.segment_sequence,
        }
        if segment is not None:
            payload["segment"] = segment
            payload.update(segment_text_fields(segment))
        self.service.manager.publish_session(
            self.session_id,
            payload,
        )
        self._publish_timeline_event(
            "final_transcript",
            timestamp=timestamp,
            segment_id=segment_id,
            segment=segment,
            text=text,
            requestId=context.request_id,
            activationId=context.activation_id,
            activationSequence=context.activation_sequence,
            segmentSequence=context.segment_sequence,
        )
        started_at = segment.get("recordingStartedAt") if segment else None
        ended_at = segment.get("recordingEndedAt") if segment else None
        performance = getattr(self.service, "performance", None)
        if performance is not None:
            performance.event(
                "stream.final_text",
                sessionId=self.session_id,
                clientId=self.client_id,
                transcriptionId=self._transcription_id(segment_id),
                transport="websocket",
                segmentId=segment_id,
                engine=self.settings.transcription_engine,
                model=self.settings.model,
                utteranceToFinalMs=(
                    round((timestamp - started_at) * 1000.0, 3)
                    if started_at is not None else None
                ),
                speechEndToFinalMs=(
                    round((timestamp - ended_at) * 1000.0, 3)
                    if ended_at is not None else None
                ),
                characterCount=len(text),
                wordCount=len(text.split()),
                memory=process_memory_snapshot(),
            )
        self._emit_realtime_summary(segment_id, timestamp, segment)
        self._emit_structured_event(
            "transcription",
            "transcription.completed",
            segment_id=segment_id,
            text=text,
            requestId=context.request_id,
            activationId=context.activation_id,
            activationSequence=context.activation_sequence,
            segmentSequence=context.segment_sequence,
            language=self.settings.language,
            engine=self.settings.transcription_engine,
            model=self.settings.model,
            audioDurationMs=(
                round(float(segment.get("durationSeconds")) * 1000.0, 3)
                if segment and segment.get("durationSeconds") is not None
                else None
            ),
        )
        with self.lock:
            foreground = self.status
        if foreground not in {"recording", "closed"}:
            self.publish_status(self._waiting_state_locked())
        return True

    def _on_realtime_text(self, text):
        with self.lock:
            if self.reject_current_recording:
                return
            segment_id = self.segment_state.realtime()
            segment = self._timeline_snapshot(segment_id)
        text = (text or "").strip()
        if not text:
            return
        timestamp = time.time()
        self._record_realtime_performance(
            segment_id,
            timestamp,
            segment,
            text,
        )
        payload = {
            "type": "realtime",
            "sessionId": self.session_id,
            "segmentId": segment_id,
            "text": text,
            "timestamp": timestamp,
            "timestampIso": timestamp_iso(timestamp),
        }
        if segment is not None:
            payload["segment"] = segment
            payload.update(segment_text_fields(segment))
        self.service.manager.publish_session(
            self.session_id,
            payload,
        )
        self._publish_timeline_event(
            "realtime_transcript",
            timestamp=timestamp,
            segment_id=segment_id,
            segment=segment,
            text=text,
        )

    def _on_realtime_stabilization_event(self, event):
        with self.lock:
            if self.reject_current_recording:
                return

        raw_text = (getattr(event, "raw_observation_text", "") or "").strip()
        committed_stable_text = getattr(event, "stable_text", "") or ""
        unstable_text = getattr(event, "unstable_text", "") or ""
        display_text = (getattr(event, "display_text", "") or "").strip()
        consensus_text = getattr(event, "consensus_text", "") or committed_stable_text
        consensus_unstable_text = getattr(event, "consensus_unstable_text", "") or ""
        consensus_display_text = (
            getattr(event, "consensus_display_text", "") or display_text
        ).strip()
        if (
            not raw_text
            and not display_text
            and not committed_stable_text
            and not unstable_text
        ):
            return

        segment_id = getattr(event, "segment_id", None)
        if segment_id is None:
            segment_id = self.segment_state.realtime()

        text = (
            display_text
            if self.settings.realtime_callback == "stabilized"
            else raw_text or display_text
        )
        timing = getattr(event, "timing", None)
        timestamp = time.time()
        segment = self._timeline_snapshot(segment_id)
        self._record_realtime_performance(
            segment_id,
            timestamp,
            segment,
            text,
            sequence=getattr(event, "sequence", None),
            stable_text=committed_stable_text,
            unstable_text=unstable_text,
            is_outlier=bool(getattr(event, "is_outlier", False)),
        )
        payload = {
            "type": "realtime",
            "sessionId": self.session_id,
            "segmentId": segment_id,
            "recordingId": getattr(event, "recording_id", None),
            "sequence": getattr(event, "sequence", None),
            "text": text,
            "rawText": raw_text,
            "displayText": display_text or raw_text,
            "stableText": committed_stable_text,
            "stableDelta": getattr(event, "stable_delta", "") or "",
            "unstableText": unstable_text,
            "committedStableText": committed_stable_text,
            "committedStableDelta": getattr(event, "stable_delta", "") or "",
            "visualStableText": committed_stable_text,
            "visualUnstableText": unstable_text,
            "consensusText": consensus_text,
            "consensusUnstableText": consensus_unstable_text,
            "consensusDisplayText": consensus_display_text,
            "publicConsensusAligned": bool(
                getattr(event, "public_consensus_aligned", True)
            ),
            "internalRevision": bool(getattr(event, "internal_revision", False)),
            "isOutlier": bool(getattr(event, "is_outlier", False)),
            "stablePrefixConflict": bool(
                getattr(event, "stable_prefix_conflict", False)
            ),
            "commitReason": getattr(event, "commit_reason", None),
            "stableNormalizedOffset": getattr(
                event,
                "stable_normalized_offset",
                None,
            ),
            "timestamp": timestamp,
            "timestampIso": timestamp_iso(timestamp),
        }
        if timing is not None:
            payload["timing"] = asdict(timing)
        if segment is not None:
            payload["segment"] = segment
            payload.update(segment_text_fields(segment))

        self.service.manager.publish_session(self.session_id, payload)
        self._publish_timeline_event(
            "realtime_transcript",
            timestamp=timestamp,
            segment_id=segment_id,
            segment=segment,
            text=text,
            sequence=payload.get("sequence"),
        )

    def _record_first_text_performance(self, segment_id, timestamp, segment, text):
        if not str(text or "").strip():
            return
        performance = getattr(self.service, "performance", None)
        if performance is None:
            return
        with self.lock:
            key = (getattr(self, "generation", 0), segment_id)
            first_text_segments = getattr(self, "_performance_first_text_segments", None)
            if first_text_segments is None:
                first_text_segments = set()
                self._performance_first_text_segments = first_text_segments
            if key in first_text_segments:
                return
            first_text_segments.add(key)
        started_at = segment.get("recordingStartedAt") if segment else None
        performance.event(
            "stream.first_text",
            sessionId=self.session_id,
            clientId=self.client_id,
            transcriptionId=self._transcription_id(segment_id),
            transport="websocket",
            segmentId=segment_id,
            engine=(
                self.settings.realtime_transcription_engine
                or self.settings.transcription_engine
            ),
            model=self.settings.realtime_model or self.settings.model,
            timeToFirstTextMs=(
                round((timestamp - started_at) * 1000.0, 3)
                if started_at is not None else None
            ),
            audioElapsedSeconds=(
                round(timestamp - started_at, 6)
                if started_at is not None else None
            ),
            memory=process_memory_snapshot(),
        )

    def _record_realtime_performance(
        self,
        segment_id,
        timestamp,
        segment,
        text,
        *,
        sequence=None,
        stable_text="",
        unstable_text="",
        is_outlier=False,
    ):
        self._record_first_text_performance(
            segment_id,
            timestamp,
            segment,
            text,
        )
        now_monotonic = time.monotonic()
        with self.lock:
            realtime_stats = getattr(self, "_realtime_event_stats", None)
            if realtime_stats is None:
                realtime_stats = {}
                self._realtime_event_stats = realtime_stats
            stats = realtime_stats.setdefault(
                segment_id,
                {
                    "count": 0,
                    "firstMonotonic": now_monotonic,
                    "firstTimestamp": timestamp,
                    "lastMonotonic": None,
                    "intervalsMs": [],
                },
            )
            previous = stats["lastMonotonic"]
            interval_ms = (
                round((now_monotonic - previous) * 1000.0, 3)
                if previous is not None
                else None
            )
            if interval_ms is not None:
                stats["intervalsMs"].append(interval_ms)
            stats["count"] += 1
            stats["lastMonotonic"] = now_monotonic
            emitted_sequence = sequence or stats["count"]
        if self.settings.realtime_log_detail != "events":
            return
        started_at = segment.get("recordingStartedAt") if segment else None
        performance = getattr(self.service, "performance", None)
        if performance is not None:
            performance.event(
                "transcription.realtime_emitted",
                sessionId=self.session_id,
                clientId=self.client_id,
                transcriptionId=self._transcription_id(segment_id),
                transport="websocket",
                segmentId=segment_id,
                sequence=emitted_sequence,
                sincePreviousMs=interval_ms,
                sinceRecordingStartMs=(
                    round((timestamp - started_at) * 1000.0, 3)
                    if started_at is not None
                    else None
                ),
                characterCount=len(str(text or "")),
                stableCharacterCount=len(str(stable_text or "")),
                unstableCharacterCount=len(str(unstable_text or "")),
                isOutlier=bool(is_outlier),
            )

    def _emit_realtime_summary(self, segment_id, timestamp, segment):
        with self.lock:
            stats = getattr(self, "_realtime_event_stats", {}).pop(
                segment_id,
                None,
            )
        if self.settings.realtime_log_detail == "off":
            return
        stats = stats or {
            "count": 0,
            "firstMonotonic": None,
            "firstTimestamp": None,
            "lastMonotonic": None,
            "intervalsMs": [],
        }
        intervals = sorted(stats["intervalsMs"])

        def percentile(values, fraction):
            if not values:
                return None
            index = max(
                0,
                min(len(values) - 1, math.ceil(len(values) * fraction) - 1),
            )
            return round(values[index], 3)

        started_at = segment.get("recordingStartedAt") if segment else None
        performance = getattr(self.service, "performance", None)
        if performance is not None:
            performance.event(
                "transcription.performance_summary",
                sessionId=self.session_id,
                clientId=self.client_id,
                transcriptionId=self._transcription_id(segment_id),
                transport="websocket",
                segmentId=segment_id,
                realtimeEventCount=stats["count"],
                averageRealtimeIntervalMs=(
                    round(sum(intervals) / len(intervals), 3)
                    if intervals
                    else None
                ),
                minRealtimeIntervalMs=min(intervals) if intervals else None,
                maxRealtimeIntervalMs=max(intervals) if intervals else None,
                p50RealtimeIntervalMs=percentile(intervals, 0.50),
                p95RealtimeIntervalMs=percentile(intervals, 0.95),
                timeToFirstRealtimeMs=(
                    round(
                        (stats["firstTimestamp"] - started_at) * 1000.0,
                        3,
                    )
                    if (
                        stats["firstTimestamp"] is not None
                        and started_at is not None
                    )
                    else None
                ),
                timeToFinalMs=(
                    round((timestamp - started_at) * 1000.0, 3)
                    if started_at is not None
                    else None
                ),
            )

    def _on_recording_start(self):
        segment = None
        segment_id = None
        recording_admitted = False
        stop_unadmitted_recording = False
        with self.lock:
            # C2 recording admission: a late or barely-lost recorder start after
            # stop/close/cancel must not accept a segment, create a ledger
            # record or keep a speaker active (F9/T15). Callback-capable work is
            # deferred until the lock is released below.
            lifecycle_ok = self.streaming and self.status != "closed"
            if not lifecycle_ok:
                stop_unadmitted_recording = True
                self.service.deactivate_speaker(self.session_id)
            else:
                self._active_recording_context = None
                self.recorder._active_recording_context = None
                self._wakeword_followup_generation += 1
                self._clear_recorder_followup_gate_locked()
                if not self.service.try_activate_speaker(self.session_id):
                    self.reject_current_recording = True
                    self.recording_sample_count = 0
                    self._force_finalize_in_progress = False
                    self._wakeword_voice_window = False
                    self.rejected_audio_chunks += 1
                    self.service.manager.publish_session(
                        self.session_id,
                        {
                            "type": "warning",
                            "sessionId": self.session_id,
                            "message": "Die maximale Anzahl gleichzeitig sprechender Personen ist erreicht; die Aufnahme wird ignoriert.",
                        },
                    )
                else:
                    activation_admitted = True
                    if self._activation is not None:
                        current_activation = self._activation.snapshot()
                        recording_activation = None
                        if hasattr(
                            self.recorder,
                            "controlled_recording_activation_state",
                        ):
                            recording_activation = (
                                self.recorder.controlled_recording_activation_state()
                            )
                        if (
                            recording_activation
                            and recording_activation.get("activationId")
                            and (
                                recording_activation.get("activationId")
                                != current_activation.get("activationId")
                                or recording_activation.get("generation")
                                != current_activation.get("generation")
                            )
                        ):
                            activation_admitted = False
                        else:
                            decision = self._activation.recording_started()
                            activation_admitted = decision.accepted
                            if decision.changed:
                                # Speech has started, so the initial deadline is
                                # over; invalidate the timer armed for it.
                                self._arm_activation_timer_locked(decision.snapshot)
                    if activation_admitted:
                        recording_admitted = True
                        self.reject_current_recording = False
                        self.recording_sample_count = 0
                        self._force_finalize_in_progress = False
                        self._wakeword_voice_window = False
                        segment_id = self.segment_state.current()
                        if self._activation is not None:
                            activation_snapshot = self._activation.snapshot()
                            activation_id = activation_snapshot.get("activationId")
                        else:
                            self._legacy_activation_sequence += 1
                            activation_id = (
                                f"legacy-{self.session_id}-"
                                f"{self._legacy_activation_sequence}"
                            )
                            activation_snapshot = {
                                "activationId": activation_id,
                                "activationSequence": self._legacy_activation_sequence,
                                "effectiveSettings": self._effective_activation_settings(),
                            }
                            self._open_ledger_activation(activation_snapshot)
                        try:
                            context = self.segment_ledger.accept_segment(
                                activation_id, segment_id
                            )
                        except (KeyError, RuntimeError):
                            LOGGER.exception(
                                "Segment %s konnte nicht im Ledger registriert werden",
                                segment_id,
                            )
                            recording_admitted = False
                            self.reject_current_recording = True
                            stop_unadmitted_recording = True
                            self.service.deactivate_speaker(self.session_id)
                        else:
                            self._active_recording_context = context
                            self._last_final_context = context
                            self.recorder._active_recording_context = context
                        segment = self.timeline.mark_recording_started(segment_id)
                    else:
                        # The gate-close barrier won a race after the recorder had
                        # observed the old open gate. Do not resurrect a segment
                        # after the controller has published idle.
                        self.reject_current_recording = True
                        self._active_recording_context = None
                        self.recorder._active_recording_context = None
                        stop_unadmitted_recording = True
                        self.service.deactivate_speaker(self.session_id)
        if stop_unadmitted_recording:
            try:
                self.recorder.flush_buffered_audio()
            except Exception:
                LOGGER.exception(
                    "Nicht zugelassene Aufnahme konnte für %s nicht gestoppt werden",
                    self.session_id,
                )
        if segment is not None:
            self._publish_timeline_event(
                "recording_started",
                timestamp=segment.get("recordingStartedAt"),
                segment_id=segment_id,
                segment=segment,
                preRecordingBuffer=segment.get("preRecordingBuffer"),
            )
        self.publish_status(
            "recording" if recording_admitted else self._waiting_state_locked()
        )

    def _on_recording_stop(self):
        self._trim_recorded_audio_queue()
        segment = None
        segment_id = None
        legacy_activation_id = None
        empty_recording_context = None
        with self.lock:
            context = self._active_recording_context
            segment_id = (
                context.segment_id
                if context is not None
                else self.segment_state.current()
            )
            duration_seconds = (
                self.recording_sample_count / float(SERVER_SAMPLE_RATE)
                if self.recording_sample_count
                else None
            )
            segment = self.timeline.mark_recording_ended(
                "recording_stop",
                segment_id=segment_id,
                actual_duration_seconds=duration_seconds,
            )
            self.recording_sample_count = 0
            self._force_finalize_in_progress = False
            self._wakeword_voice_window = False
            if context is not None:
                self.segment_state.final()
                self._last_final_context = context
                # Real recorder queues carry this context with their audio.
                # Recorder fakes and direct executor users get the same stable
                # identity through the current-transcription fallback.
                self.recorder._current_transcription_context = context
                self._active_recording_context = None
                self.recorder._active_recording_context = None
                if getattr(
                    self.recorder, "_last_recording_was_queued", None
                ) is False:
                    empty_recording_context = context
                self.recorder._last_recording_was_queued = None
            if self._activation is not None:
                decision = self._activation.recording_ended()
                if decision.changed:
                    # The follow-up window is now the authoritative deadline.
                    self._arm_activation_timer_locked(decision.snapshot)
            elif context is not None:
                legacy_activation_id = context.activation_id
        self.service.deactivate_speaker(self.session_id)
        if segment is not None:
            self._publish_timeline_event(
                "recording_ended",
                timestamp=segment.get("recordingEndedAt"),
                segment_id=segment_id,
                segment=segment,
                durationSeconds=segment.get("durationSeconds"),
                reason=segment.get("endReason"),
            )
        if empty_recording_context is not None:
            self._dispatch_ledger_operation(
                self.segment_ledger.resolve_terminal,
                empty_recording_context,
                "discarded",
                "empty_recording",
            )
        if legacy_activation_id is not None:
            self._close_ledger_activation(
                legacy_activation_id,
                "recording_stop",
            )
        if self._activation is None:
            # The legacy wake-word follow-up owns a second timer and writes
            # recorder state directly. In the controlled mode the
            # ActivationController is the only follow-up authority, so this
            # path must stay switched off there.
            self._start_wakeword_followup_window()
        self.publish_status(self._waiting_state_locked())

    def _on_transcription_start(self, *_):
        with self._ledger_dispatch_lock:
            with self.lock:
                rejected = self.reject_current_recording
                context = getattr(
                    self.recorder, "_current_transcription_context", None
                )
                if context is None and not rejected:
                    context = self._compat_final_context(
                        self.generation,
                        self.segment_state.current(),
                    )
                self.recorder._current_transcription_context = context
                self._active_text_context = context
                segment_id = (
                    context.segment_id
                    if context is not None
                    else self.segment_state.current()
                )
        if not rejected:
            self._emit_structured_event(
                "transcription",
                "transcription.accepted",
                segment_id=segment_id,
                requestId=(context.request_id if context is not None else None),
                activationId=(context.activation_id if context is not None else None),
                activationSequence=(
                    context.activation_sequence if context is not None else None
                ),
                segmentSequence=(
                    context.segment_sequence if context is not None else None
                ),
            )
        self._publish_timeline_event(
            "transcription_started",
            segment_id=segment_id,
            segment=self._timeline_snapshot(segment_id),
        )
        if self._activation is None:
            self.publish_status("transcribing")
        return bool(rejected)

    def _waiting_state_locked(self, streaming=None):
        if streaming is None:
            streaming = self.streaming
        if not streaming:
            return "idle"
        if self.settings.wake_word_enabled():
            if self._wakeword_voice_window:
                return "wakeword_detected"
            return "wakeword_wait"
        return "listening"

    def _start_wakeword_followup_window(self):
        try:
            window = max(0.0, float(self.settings.wake_word_followup_window))
        except (TypeError, ValueError):
            window = 0.0
        if not self.settings.wake_word_enabled() or window <= 0:
            return False

        with self.lock:
            if not self.streaming or self.reject_current_recording:
                return False
            self._wakeword_voice_window = True
            self._wakeword_followup_generation += 1
            generation = self._wakeword_followup_generation
            recorder = self.recorder
            try:
                if self._recorder_wake_word_timeout_before_followup is None:
                    self._recorder_wake_word_timeout_before_followup = getattr(
                        recorder,
                        "wake_word_timeout",
                        None,
                    )
                if self._recorder_start_recording_before_followup is None:
                    self._recorder_start_recording_before_followup = getattr(
                        recorder,
                        "start_recording_on_voice_activity",
                        None,
                    )
                if self._recorder_stop_recording_before_followup is None:
                    self._recorder_stop_recording_before_followup = getattr(
                        recorder,
                        "stop_recording_on_voice_deactivity",
                        None,
                    )
                recorder.wakeword_detected = True
                recorder.wake_word_detect_time = time.time()
                recorder.wake_word_timeout = window
                recorder.start_recording_on_voice_activity = True
                recorder.stop_recording_on_voice_deactivity = True
            except Exception:
                self._wakeword_voice_window = False
                self._clear_recorder_followup_gate_locked()
                LOGGER.debug(
                "Nachfragefenster für das Weckwort konnte für %s nicht aktiviert werden",
                    self.session_id,
                    exc_info=True,
                )
                return False

        self._publish_timeline_event(
            "wakeword_followup_started",
            durationSeconds=window,
        )
        threading.Thread(
            target=self._wakeword_followup_timeout_worker,
            args=(generation, window),
            name=f"VoiceSTTSessionWakeFollowup-{self.session_id}",
            daemon=True,
        ).start()
        return True

    def _wakeword_followup_timeout_worker(self, generation, window):
        time.sleep(window)
        self._finish_wakeword_followup(generation)

    def _finish_wakeword_followup(self, generation=None):
        with self.lock:
            if generation is not None and generation != self._wakeword_followup_generation:
                return False
            if not self._wakeword_voice_window:
                return False
            if bool(getattr(self.recorder, "is_recording", False)):
                return False
            self._wakeword_voice_window = False
            self._wakeword_followup_generation += 1
            self._clear_recorder_followup_gate_locked()
            streaming = self.streaming

        self._publish_timeline_event("wakeword_followup_timeout")
        self.publish_status("wakeword_wait" if streaming else "idle")
        return True

    def _clear_recorder_followup_gate_locked(self):
        recorder = self.recorder
        try:
            recorder.wakeword_detected = False
            recorder.wake_word_detect_time = 0
            if self._recorder_wake_word_timeout_before_followup is not None:
                recorder.wake_word_timeout = self._recorder_wake_word_timeout_before_followup
            if self._recorder_start_recording_before_followup is not None:
                recorder.start_recording_on_voice_activity = (
                    self._recorder_start_recording_before_followup
                )
            if self._recorder_stop_recording_before_followup is not None:
                recorder.stop_recording_on_voice_deactivity = (
                    self._recorder_stop_recording_before_followup
                )
        except Exception:
            LOGGER.debug(
                "Nachfragefenster-Sperre für das Weckwort konnte für %s nicht aufgehoben werden",
                self.session_id,
                exc_info=True,
            )
        self._recorder_wake_word_timeout_before_followup = None
        self._recorder_start_recording_before_followup = None
        self._recorder_stop_recording_before_followup = None

    def _on_vad_start(self):
        self.publish_status(self._voice_or_waiting_state())

    def _on_vad_stop(self):
        self.publish_status(self._silence_or_waiting_state())

    def _on_vad_detect_start(self):
        self.publish_status(self._voice_or_waiting_state())

    def _on_vad_detect_stop(self):
        self.publish_status(self._silence_or_waiting_state())

    def _voice_or_waiting_state(self):
        with self.lock:
            if not self.settings.wake_word_enabled():
                return "voice"
            if self._wakeword_voice_window:
                return "voice"
            return self._waiting_state_locked()

    def _silence_or_waiting_state(self):
        with self.lock:
            if not self.settings.wake_word_enabled():
                return "silence"
            if self._wakeword_voice_window:
                return "silence"
            return self._waiting_state_locked()

    def _on_wakeword_detection_start(self):
        """Records the wake-detection epoch for the *current* lifecycle.

        Only a valid, synchronously executed start may arm the detection: the
        stream must be running and the session not closed. Stop/close have
        already invalidated the epoch, so a stale start can never re-arm it
        (F9/T13).
        """
        with self.lock:
            if not self.streaming or self.status == "closed":
                return
            self._wake_detection_epoch = self._lifecycle_epoch
            self._wakeword_voice_window = False
            self._wakeword_followup_generation += 1
            self._clear_recorder_followup_gate_locked()
        event = self.timeline.mark_wakeword_wait_started()
        self._publish_timeline_event(
            "wakeword_wait_started",
            wakeWord=event.get("wakeWord"),
        )
        self.publish_status("wakeword_wait")

    def _on_wakeword_detection_end(self):
        event = self.timeline.mark_wakeword_wait_ended()
        self._publish_timeline_event(
            "wakeword_wait_ended",
            wakeWord=event.get("wakeWord"),
        )

    def _on_wakeword_detected(self, candidate=None, boundary=None):
        """Admission-gated wake detection.

        A late wake callback from a stopped/closed session - or one whose
        detection epoch no longer matches the current lifecycle (a stale
        callback from a previous stream) - returns without any fachlich
        effect: no gate open, no activation, no timeline event (F9/T11-T13).

        AP-SRV-060: with a structured candidate the decision belongs to the
        wake admission coordinator, which answers with the accepted detection
        or ``None``. A refused admission publishes **nothing** - the legacy
        path below published ``wakeword_detected`` even when the activation was
        locked, which the frozen contract forbids.
        """
        if candidate is not None:
            coordinator = getattr(self, "_wake_admission", None)
            if coordinator is None:
                return None
            return coordinator.admit(candidate, boundary)

        with self.lock:
            if not self.streaming or self.status == "closed":
                return
            if self._wake_detection_epoch != self._lifecycle_epoch:
                return
            published = []
            self._wakeword_voice_window = True
            self._wakeword_followup_generation += 1
            if self._activation is not None and self._audio_available:
                # A wake word is a trigger like any other: it goes through the
                # same admission as a manual command, including the generic
                # audio-availability gate, and reaches the recorder only via
                # the controlled gate. It never opens a recording on its own.
                activation_settings, timing_policy = self._new_activation_inputs()
                decision = self._activation.activate(
                    "wake_word",
                    activation_settings,
                    timing_policy=timing_policy,
                )
                self._apply_activation_decision_locked(
                    "activate", decision, published
                )
        event = self.timeline.mark_wakeword_detected()
        self._publish_timeline_event(
            "wakeword_detected",
            wakeWord=event.get("wakeWord"),
        )
        self._publish_collected_events(published)
        self.publish_status("wakeword_detected")

    def _on_wakeword_timeout(self):
        with self.lock:
            self._wakeword_voice_window = False
            self._wakeword_followup_generation += 1
            self._clear_recorder_followup_gate_locked()
        event = self.timeline.mark_wakeword_timeout()
        self._publish_timeline_event(
            "wakeword_timeout",
            wakeWord=event.get("wakeWord"),
        )
        self.publish_status("wakeword_timeout")

    def _transcription_id(self, segment_id):
        return f"{self.session_id}:{self.generation}:{segment_id}"

    def _emit_cancelled_transcription(
        self,
        generation,
        segment_id,
        reason,
    ):
        hub = getattr(self.service, "events", None)
        if hub is None:
            return None
        return hub.emit(
            "transcription",
            "transcription.cancelled",
            severity="warning",
            transport="websocket",
            clientId=self.client_id,
            sessionId=self.session_id,
            transcriptionId=(
                f"{self.session_id}:{generation}:{segment_id}"
            ),
            segmentId=segment_id,
            reason=reason,
        )

    def _emit_structured_event(
        self,
        channel,
        event,
        *,
        segment_id=None,
        severity="info",
        **fields,
    ):
        hub = getattr(self.service, "events", None)
        if hub is None:
            return None
        return hub.emit(
            channel,
            event,
            severity=severity,
            transport="websocket",
            clientId=self.client_id,
            sessionId=self.session_id,
            transcriptionId=(
                self._transcription_id(segment_id)
                if segment_id is not None
                else None
            ),
            segmentId=segment_id,
            **fields,
        )

    def _publish_timeline_event(
        self,
        event,
        *,
        timestamp=None,
        segment_id=None,
        segment=None,
        **fields,
    ):
        if not hasattr(self, "timeline"):
            return
        if event == "activation_closed":
            # AP-SRV-060: the wake latch is released exactly at the *safe input
            # close* of the activation it belongs to. ``activation_closed`` is
            # the exactly-once close record of every close path (regular,
            # recovery, stream/session reset), so this is the single seam - not
            # VAD end, not segment end, not a final inference and not a
            # cooldown expiry.
            self._release_wake_latch(fields.get("activationId"))
        timestamp = time.time() if timestamp is None else float(timestamp)
        payload = {
            "type": "timeline",
            "sessionId": self.session_id,
            "event": event,
            "timestamp": timestamp,
            "timestampIso": timestamp_iso(timestamp),
        }
        if segment_id is not None:
            payload["segmentId"] = segment_id
        if segment is not None:
            payload["segment"] = segment
        # Recording and transcription events carry the activation they belong
        # to, so a client can correlate a segment back to the trigger that
        # opened it. Explicit fields on the call win over the correlation.
        for key, value in self._activation_correlation().items():
            payload.setdefault(key, value)
            fields.setdefault(key, value)
        for key, value in fields.items():
            if value is not None:
                payload[key] = value
        self.service.manager.publish_session(self.session_id, payload)
        structured_events = {
            "activation_started": "activation.started",
            "activation_refreshed": "activation.refreshed",
            "activation_closed": "activation.closed",
            "activation_drained": "activation.drained",
            "watchdog_warning": "watchdog.warning",
            "recording_started": "transcription.recording_started",
            "recording_ended": "transcription.recording_ended",
            "transcription_started": "transcription.started",
            "wakeword_detected": "wakeword.detected",
            "wakeword_followup_started": "wakeword.followup_started",
            "wakeword_followup_timeout": "wakeword.followup_timeout",
            "wakeword_timeout": "wakeword.timeout",
            "wakeword_wait_ended": "wakeword.wait_ended",
            "wakeword_wait_started": "wakeword.wait_started",
        }
        structured_name = structured_events.get(event)
        if structured_name is not None:
            event_fields = {
                key: value
                for key, value in fields.items()
                if key != "text" and value is not None
            }
            self._emit_structured_event(
                "transcription",
                structured_name,
                segment_id=segment_id,
                **event_fields,
            )
        self._notify_protocol_observer(event, payload)

    #: Synthetic notification for the visible entry into ``closing_input``.
    #: The phase transition itself has already happened under the session lock;
    #: AP-SRV-030 publishes no lifecycle event for it, so the wire layer needs
    #: this marker to version a visible state change that has no own event.
    #: It is not a domain event and never becomes one.
    INPUT_CLOSING_NOTIFICATION = "__input_closing__"

    def _notify_input_closing(self, plan):
        self._notify_protocol_observer(
            self.INPUT_CLOSING_NOTIFICATION,
            {
                "activationId": plan.activation_id,
                "activationSequence": plan.activation_sequence,
                "reason": plan.reason,
                "recovery": bool(plan.recovery),
            },
        )

    def _notify_protocol_observer(self, event, payload):
        """Hands one already published lifecycle event to the wire projection.

        This is a notification, not a second emitter: the event has already
        happened and has already been published on the legacy path. A failing
        observer must never break the domain, so it is fully contained.
        """
        observer = self._protocol_observer
        if observer is None:
            return
        try:
            observer(event, dict(payload))
        except Exception:
            LOGGER.exception(
                "Protokollbeobachter für '%s' ist fehlgeschlagen", event
            )

    def _timeline_snapshot(self, segment_id=None):
        timeline = getattr(self, "timeline", None)
        if timeline is None:
            return None
        return timeline.snapshot(segment_id)

    def _recorder_queue_depth(self):
        depth = 0
        try:
            depth += int(self.recorder.audio_queue.qsize())
        except Exception:
            pass
        try:
            depth += int(self.recorder.recorded_audio_queue.qsize())
        except Exception:
            pass
        return depth

    def _enforce_recording_duration(self, samples):
        if self._recorded_chunk_callback_seen:
            return None

        max_samples = int(self.settings.max_audio_queue_seconds_per_session * SERVER_SAMPLE_RATE)
        if max_samples <= 0:
            return None

        should_finalize = False
        with self.lock:
            if bool(getattr(self.recorder, "is_recording", False)):
                self.recording_sample_count += int(samples.size)
                should_finalize = self.recording_sample_count >= max_samples

        if not should_finalize:
            return None

        self._force_finalize_after_limit()
        return None

    def _on_recorded_chunk(self, data):
        self._recorded_chunk_callback_seen = True
        max_samples = int(self.settings.max_audio_queue_seconds_per_session * SERVER_SAMPLE_RATE)
        if max_samples <= 0:
            return
        if not bool(getattr(self.recorder, "is_recording", False)):
            return

        try:
            sample_count = len(data) // 2
        except Exception:
            return

        should_finalize = False
        with self.lock:
            self.recording_sample_count += int(sample_count)
            if (
                self.recording_sample_count >= max_samples
                and not self._force_finalize_in_progress
            ):
                self._force_finalize_in_progress = True
                should_finalize = True

        if should_finalize:
            threading.Thread(
                target=self._force_finalize_after_limit,
                name=f"VoiceSTTSessionForceFinalize-{self.session_id}",
                daemon=True,
            ).start()

    def _force_finalize_after_limit(self):
        finalized = False
        try:
            finalized = bool(self.recorder.flush_buffered_audio())
            self._trim_recorded_audio_queue()
        except Exception:
            LOGGER.debug("Lange Aufnahme für %s konnte nicht zwangsfinalisiert werden", self.session_id, exc_info=True)
        finally:
            with self.lock:
                self.recording_sample_count = 0
                self._force_finalize_in_progress = False
                if finalized:
                    self.forced_finalizations += 1

        if not finalized:
            return
        self.service.deactivate_speaker(self.session_id)
        self.service.manager.publish_session(
            self.session_id,
            {
                "type": "warning",
                "sessionId": self.session_id,
                "message": "Maximaler Audiopuffer der Sitzung erreicht; das aktuelle Segment wurde finalisiert.",
            },
        )

    def _trim_recorded_audio_queue(self):
        queue_obj = getattr(self.recorder, "recorded_audio_queue", None)
        if queue_obj is None:
            return 0

        max_pending = max(0, int(self.settings.max_final_queue_depth_per_session))
        dropped = 0
        while True:
            try:
                if queue_obj.qsize() <= max_pending:
                    break
                queued = queue_obj.get_nowait()
                dropped += 1
                context = (
                    queued.get("segment_context")
                    if isinstance(queued, dict)
                    else None
                )
                if context is not None:
                    self._dispatch_ledger_operation(
                        self.segment_ledger.resolve_terminal,
                        context,
                        "discarded",
                        "recorded_audio_queue_trimmed",
                    )
            except Exception:
                break

        if dropped:
            with self.lock:
                self.dropped_recorded_segments += dropped
                self.final_rejected += dropped
            self.service.manager.publish_session(
                self.session_id,
                {
                    "type": "warning",
                    "sessionId": self.session_id,
                    "message": (
                        "Der Rückstau finaler Transkriptionen hat das Sitzungslimit überschritten; "
                        f"{dropped} aufgezeichnete(s) Segment(e) aus der Warteschlange verworfen."
                    ),
                },
            )
        return dropped


class SessionStore:
    def __init__(self, settings: ServerSettings):
        self.settings = settings
        self._lock = threading.Lock()
        self._sessions: Dict[str, RecorderBackedRealtimeSession] = {}
        self._reserved_session_ids = set()
        self._active_speakers = set()
        self.rejected_sessions = 0

    def reserve(self, session_id):
        with self._lock:
            if session_id in self._sessions or session_id in self._reserved_session_ids:
                self.rejected_sessions += 1
                return False
            if self._session_slots_used_locked() >= self.settings.max_sessions:
                self.rejected_sessions += 1
                return False
            self._reserved_session_ids.add(session_id)
            return True

    def add(self, session):
        with self._lock:
            reserved = session.session_id in self._reserved_session_ids
            if session.session_id in self._sessions:
                self._reserved_session_ids.discard(session.session_id)
                self.rejected_sessions += 1
                return False
            if not reserved and self._session_slots_used_locked() >= self.settings.max_sessions:
                self.rejected_sessions += 1
                return False
            self._reserved_session_ids.discard(session.session_id)
            self._sessions[session.session_id] = session
            return True

    def can_accept(self):
        with self._lock:
            if self._session_slots_used_locked() >= self.settings.max_sessions:
                self.rejected_sessions += 1
                return False
            return True

    def release_reservation(self, session_id):
        with self._lock:
            self._reserved_session_ids.discard(session_id)

    def remove(self, session_id):
        with self._lock:
            session = self._sessions.pop(session_id, None)
            self._reserved_session_ids.discard(session_id)
            self._active_speakers.discard(session_id)
            return session

    def remove_all(self):
        with self._lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
            self._reserved_session_ids.clear()
            self._active_speakers.clear()
            return sessions

    def get(self, session_id):
        with self._lock:
            return self._sessions.get(session_id)

    def all(self):
        with self._lock:
            return list(self._sessions.values())

    def try_activate_speaker(self, session_id):
        with self._lock:
            if session_id in self._active_speakers:
                return True
            if len(self._active_speakers) >= self.settings.max_active_speakers:
                return False
            self._active_speakers.add(session_id)
            return True

    def deactivate_speaker(self, session_id):
        with self._lock:
            self._active_speakers.discard(session_id)

    def count(self):
        with self._lock:
            return len(self._sessions)

    def active_speaker_count(self):
        with self._lock:
            return len(self._active_speakers)

    def snapshots(self):
        with self._lock:
            sessions = list(self._sessions.values())
            rejected = self.rejected_sessions
            active_speakers = len(self._active_speakers)
            reserved_sessions = len(self._reserved_session_ids)
        return {
            "activeSessions": len(sessions),
            "activeSpeakers": active_speakers,
            "pendingSessionAdmissions": reserved_sessions,
            "rejectedSessions": rejected,
            "sessions": {session.session_id: session.snapshot() for session in sessions},
        }

    def _session_slots_used_locked(self):
        return len(self._sessions) + len(self._reserved_session_ids)


class VoiceSTTService:
    def __init__(
        self,
        settings: ServerSettings,
        manager: ConnectionManager,
        scheduler_factory: Optional[Callable[..., Any]] = None,
        recorder_factory: Optional[Callable[..., Any]] = None,
    ):
        self.settings = settings
        self.manager = manager
        self.ready = threading.Event()
        self.stop_event = threading.Event()
        self.sessions = SessionStore(settings)
        self.startup_errors = []
        self._pending_recorder_results = {}
        self._pending_recorder_lock = threading.Lock()
        self._pending_api_results = {}
        self._pending_api_lock = threading.Lock()
        self._scheduler_lock = threading.RLock()
        self._model_condition = threading.Condition(self._scheduler_lock)
        self._settings_lock = threading.RLock()
        self.loop = None
        self.recorder_factory = recorder_factory
        self.scheduler_factory = scheduler_factory or InferenceScheduler
        self.scheduler = self._new_scheduler()
        self._model_state = "loaded"
        self._model_state_error = None
        self._last_model_activity_monotonic = time.monotonic()
        self._last_model_activity_at = datetime.datetime.now(datetime.timezone.utc)
        self.model_registry = LocalModelRegistry()
        self.wakeword_registry = WakeWordRegistry()
        self._apply_openwakeword_manifest_default()
        self.events = StructuredEventHub(settings)
        self.audit = AuditLogManager(settings, self.events)
        self.performance = PerformanceLogManager(settings, self.events)
        self.config_store = RuntimeConfigStore(settings.runtime_config_path)
        # AP-SRV-050 server-authoritative defaults with their own revision
        # stream, loaded from the single runtime config document.
        persisted_overlay, persisted_revision = self.config_store.load_control()
        self.settings_control = settings_control_module.ServerSettingsState(
            settings_control_module.build_default_registry(),
            overlay=persisted_overlay,
            revision=persisted_revision,
            persist=self._persist_settings_control,
        )
        self.settings_registry = self.settings_control.registry
        # AP-SRV-060: the one server-wide wake-word catalog authority. It holds
        # the last-known-good manifest snapshot, the public projection, the
        # internal artifact projection, the single resolver, availability, the
        # global disable projection and ``catalogRevision`` - which is
        # deliberately separate from ``settingsRevision``.
        self.wakeword_catalog = wakeword_catalog_module.WakeWordCatalogAuthority(
            global_disabled_ids=self._configured_global_disabled_wake_words(),
            on_catalog_changed=self._on_wake_word_catalog_changed,
        )
        self._log_access_tokens = {}
        self._log_access_lock = threading.RLock()
        self.ready_thread = None
        self.idle_thread = None

    # -- AP-SRV-060 wake-word catalog ---------------------------------------

    def _configured_global_disabled_wake_words(self):
        """The AP-SRV-050 ``wakeWord.globalDisabledIds`` server value.

        The catalog never owns this list; it only projects it into
        availability. Reading it here keeps the settings control plane the one
        settings authority.
        """
        try:
            effective = self.settings_control.server_effective()
        except Exception:  # noqa: BLE001 - startup must not depend on it
            return ()
        values = effective.get(settings_control_module.WAKE_WORD_GLOBAL_DISABLED)
        if not isinstance(values, (list, tuple)):
            return ()
        return tuple(str(value) for value in values)

    def wake_word_inference_backend(self):
        """The AP-SRV-050 ``wakeWord.inferenceBackend`` server value.

        AP-SRV-060 C3 section 10: an admin/server setting, applied per session
        admission. The catalog never owns it; it only receives it as the
        requested backend policy of one admission, and there is no
        wake-specific validation outside the settings registry.
        """
        try:
            effective = self.settings_control.server_effective()
        except Exception:  # noqa: BLE001 - never break an admission on a read
            return "auto"
        value = effective.get(settings_control_module.WAKE_WORD_INFERENCE_BACKEND)
        return str(value or "auto")

    def _on_wake_word_catalog_changed(
        self, catalog_revision, available_wake_word_ids, availability_changed
    ):
        """Announces a visible catalog change on every live v2 session.

        Root F8: *every* change that raises ``catalogRevision`` is announced,
        not only one that adds or removes ids. A renamed display name, a new
        alias or a new ``artifactVersion`` is visible in
        ``GET /api/v2/wake-words``, so a live client must be able to notice the
        new revision too. ``availabilityChanged`` stays available as
        diagnostics for the caller.

        It uses the existing AP-SRV-040 event authority through each session's
        lifecycle funnel; there is no second event stream, no second sequence
        and no new event family - the frozen contract already designates this
        event as the wake-catalog change seam.
        """
        for session in self.sessions.all():
            try:
                session.publish_wake_word_availability(
                    catalog_revision, available_wake_word_ids
                )
            except Exception:  # noqa: BLE001 - one session must not break the rest
                LOGGER.debug(
                    "wakeword.availability_changed konnte für %s nicht "
                    "veröffentlicht werden",
                    getattr(session, "session_id", "?"),
                    exc_info=True,
                )

    def refresh_wake_word_catalog(self):
        """Admin refresh: rebuild, validate, swap atomically or keep the old one.

        Root F10: manifest reload and the global disable projection happen in
        **one** locked catalog operation, and the returned result carries the
        committed snapshot. Nothing downstream has to read the authority a
        second time, so a response can never pair a revision from one state
        with entries from another.

        A refresh never touches an already built session or the models it has
        already initialised; it only affects new session admissions.
        """
        return self.wakeword_catalog.refresh(
            global_disabled_ids=self._configured_global_disabled_wake_words()
        )

    def apply_wake_word_global_disable(self):
        """Re-projects the current server disable list onto the catalog."""
        return self.wakeword_catalog.set_global_disabled(
            self._configured_global_disabled_wake_words()
        )

    def _apply_openwakeword_manifest_default(self):
        backend = (
            str(self.settings.wakeword_backend or "")
            .strip()
            .lower()
            .replace("-", "_")
        )
        if (
            backend not in OPENWAKEWORD_SESSION_BACKENDS
            or _split_wake_word_ids(self.settings.wake_words)
        ):
            return
        resolved, missing = self.wakeword_registry.resolve_openwakeword(
            None,
            self.settings.openwakeword_model_paths,
            self.settings.openwakeword_inference_framework,
        )
        if missing or not resolved:
            return
        self.settings.wakeword_backend = "openwakeword"
        self.settings.wake_words = ",".join(
            item["id"] for item in resolved
        )
        self.settings.openwakeword_model_paths = ",".join(
            item["path"] for item in resolved
        )

    def _new_scheduler(self):
        return self.scheduler_factory(
            self.settings,
            self._on_inference_result,
            self._on_scheduler_drop,
            self._on_scheduler_error,
        )

    def start(self, loop):
        self.loop = loop
        self.manager.bind_loop(loop)
        self.events.emit(
            "system",
            "server.starting",
            message="Server wird gestartet",
            host=self.settings.host,
            port=self.settings.port,
        )
        load_started = time.monotonic()
        memory_before = process_memory_snapshot()
        with self._scheduler_lock:
            scheduler = self.scheduler
            scheduler.start()
        self.ready_thread = threading.Thread(
            target=self._ready_worker,
            args=(scheduler, load_started, memory_before),
            name="VoiceSTTServerReady",
            daemon=True,
        )
        self.ready_thread.start()
        self.idle_thread = threading.Thread(
            target=self._model_idle_worker,
            name="VoiceSTTModelIdleMonitor",
            daemon=True,
        )
        self.idle_thread.start()

    def stop(self):
        self.stop_event.set()
        for session in self.sessions.remove_all():
            session.close()
        with self._scheduler_lock:
            scheduler = self.scheduler
        if scheduler is not None:
            scheduler.stop()
        if self.ready_thread is not None:
            self.ready_thread.join(timeout=5)
        if self.idle_thread is not None:
            self.idle_thread.join(timeout=5)
        self.audit.close()
        self.performance.close()
        self.events.emit(
            "system",
            "server.stopping",
            message="Server wird beendet",
        )
        self.events.close()

    def admit_session(
        self,
        session_id,
        wake_word_request=None,
        client_id=None,
        activation_request=None,
        canonical_ids=False,
    ):
        self.touch_model_activity("websocket_connection")
        wake_word_request = wake_word_request or SessionWakeWordRequest()
        with self._settings_lock:
            base_settings = replace(self.settings)
        session_settings, session_config = resolve_session_wake_word_config(
            base_settings,
            wake_word_request,
            self.wakeword_registry,
        )
        # The activation configuration has to be resolved against the wake word
        # profile that was actually granted for this session, so it is done
        # here and not at the WebSocket entry point.
        activation_config = resolve_session_activation_config(
            activation_request or SessionActivationRequest(),
            session_settings.wake_word_enabled(),
        )
        if not self.sessions.reserve(session_id):
            return None
        session = None
        try:
            session = RecorderBackedRealtimeSession(
                self,
                session_id,
                client_id=client_id,
                settings=session_settings,
                session_config=session_config,
                activation_config=activation_config,
                canonical_ids=canonical_ids,
            )
            if not self.sessions.add(session):
                session.close()
                return None
            return session
        except Exception:
            self.sessions.release_reservation(session_id)
            if session is not None:
                session.close()
            raise

    def remove_session(self, session_id):
        session = self.sessions.remove(session_id)
        if session is not None:
            session.close()

    def submit_inference_job(self, job: InferenceJob):
        result = self._submit_scheduler_job(job, f"{job.kind}_submitted")
        session = self.sessions.get(job.session_id)
        if session is not None:
            session.on_submit_result(job, result)
        return result

    def cancel_scheduler_session(self, session_id):
        with self._scheduler_lock:
            if self.scheduler is not None:
                self.scheduler.cancel_session(session_id)

    def touch_model_activity(self, reason=None):
        self._last_model_activity_monotonic = time.monotonic()
        self._last_model_activity_at = datetime.datetime.now(datetime.timezone.utc)

    def ensure_models_loaded(self, timeout=180.0):
        deadline = time.monotonic() + timeout
        with self._model_condition:
            waited_for_loader = False
            while self._model_state == "loading":
                waited_for_loader = True
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("Zeitüberschreitung beim Warten auf einen laufenden Modellladevorgang.")
                self._model_condition.wait(timeout=remaining)
            if waited_for_loader and self._model_state_error:
                raise RuntimeError(
                    f"Transkriptionsmodelle konnten nicht geladen werden: {self._model_state_error}"
                )
            if self.stop_event.is_set():
                raise RuntimeError("Der Transkriptionsdienst wird beendet.")
            if self.scheduler is not None:
                return self.scheduler
            self._model_state = "loading"
            self._model_state_error = None

        load_started = time.monotonic()
        memory_before = process_memory_snapshot()
        replacement = self._new_scheduler()
        try:
            replacement.start()
            remaining = max(0.0, deadline - time.monotonic())
            if not replacement.wait_ready(timeout=remaining) or not replacement.healthy():
                raise RuntimeError("Die Modell-Worker haben keinen fehlerfreien Zustand erreicht.")
        except Exception as exc:
            try:
                replacement.stop()
            except Exception:
                LOGGER.debug("Fehlerhafte Modell-Worker konnten nicht beendet werden", exc_info=True)
            with self._model_condition:
                self._model_state = "unloaded"
                self._model_state_error = str(exc)
                self._model_condition.notify_all()
            self._log_model_performance(
                "models.load_failed", load_started, memory_before,
                reason="lazy_reload", error=str(exc),
            )
            raise RuntimeError(f"Transkriptionsmodelle konnten nicht geladen werden: {exc}") from exc

        discard = False
        with self._model_condition:
            if self.stop_event.is_set():
                self._model_state = "stopped"
                self._model_state_error = "Der Transkriptionsdienst wird beendet."
                discard = True
            else:
                self.scheduler = replacement
                self._model_state = "loaded"
                self.touch_model_activity("models_loaded")
                self.ready.set()
            self._model_condition.notify_all()
        if discard:
            replacement.stop()
            raise RuntimeError("Der Transkriptionsdienst wird beendet.")
        self.audit.event("models.loaded", active=self.active_models())
        self._log_model_performance(
            "models.loaded", load_started, memory_before, reason="lazy_reload"
        )
        return replacement

    def _submit_scheduler_job(self, job, activity):
        while True:
            scheduler = self.ensure_models_loaded()
            with self._scheduler_lock:
                if scheduler is not self.scheduler:
                    continue
                self.touch_model_activity(activity)
                result = scheduler.submit(job)
                if not result.accepted and "voll" in str(result.reason).lower():
                    transcription_id = (
                        f"{job.session_id}:{job.generation}:{job.segment_id}"
                        if job.session_id
                        else None
                    )
                    self.events.emit(
                        "system",
                        "scheduler.overloaded",
                        severity="warning",
                        message="Scheduler-Warteschlange ist ausgelastet",
                        sessionId=job.session_id,
                        clientId=job.client_id,
                        requestId=job.request_id,
                        transcriptionId=transcription_id,
                        lane=job.kind,
                        reason=result.reason,
                    )
                    self.performance.event(
                        "queue.limit_reached",
                        sessionId=job.session_id,
                        clientId=job.client_id,
                        requestId=job.request_id,
                        transcriptionId=transcription_id,
                        lane=job.kind,
                        reason=result.reason,
                    )
                return result

    def load_models(self, timeout=180.0):
        with self._scheduler_lock:
            was_loaded = self.scheduler is not None
        self.ensure_models_loaded(timeout=timeout)
        return {
            "changed": not was_loaded,
            "lifecycle": self.model_lifecycle_status(),
        }

    def _models_busy(self):
        with self._pending_api_lock:
            pending_api = len(self._pending_api_results)
        with self._pending_recorder_lock:
            pending_recorder = len(self._pending_recorder_results)
        return self.active_speaker_count() > 0 or pending_api > 0 or pending_recorder > 0

    def unload_models(self, reason="manual"):
        unload_started = time.monotonic()
        memory_before = process_memory_snapshot()
        with self._scheduler_lock:
            if self._model_state == "loading":
                raise RuntimeError("Modelle können während eines laufenden Modellladevorgangs nicht entladen werden.")
            if self.scheduler is None:
                return {"changed": False, "lifecycle": self.model_lifecycle_status()}
            if self._models_busy():
                raise RuntimeError(
                    "Modelle können nicht entladen werden, solange Audio aktiv ist oder Transkriptionen laufen."
                )
            scheduler = self.scheduler
            self.scheduler = None
            self._model_state = "unloading"
            try:
                scheduler.stop()
            except Exception:
                self.scheduler = scheduler
                self._model_state = "loaded"
                raise
            self._model_state = "unloaded"
            self._model_state_error = None
        del scheduler
        gc.collect()
        self.audit.event("models.unloaded", reason=reason, active=self.active_models())
        self._log_model_performance(
            "models.unloaded", unload_started, memory_before, reason=reason
        )
        return {"changed": True, "lifecycle": self.model_lifecycle_status()}

    def _log_model_performance(self, event, started_at, memory_before, **fields):
        memory_after = process_memory_snapshot()
        rss_before = memory_before.get("rssBytes")
        rss_after = memory_after.get("rssBytes")
        unique_models = {
            (lane["engine"], str(lane["model"]).lower())
            for lane in self.active_models().values()
            if lane.get("engine") and lane.get("model")
        }
        self.performance.event(
            event,
            durationMs=round((time.monotonic() - started_at) * 1000.0, 3),
            active=self.active_models(),
            uniqueModelCount=len(unique_models),
            memoryBefore=memory_before,
            memoryAfter=memory_after,
            rssDeltaBytes=(
                rss_after - rss_before
                if rss_before is not None and rss_after is not None
                else None
            ),
            **fields,
        )

    def model_lifecycle_status(self):
        with self._scheduler_lock:
            loaded = self.scheduler is not None
            state = self._model_state
            error = self._model_state_error
            last_activity_at = self._last_model_activity_at
            idle_seconds = max(0.0, time.monotonic() - self._last_model_activity_monotonic)
        timeout = max(0.0, float(self.settings.model_idle_timeout_seconds))
        remaining = max(0.0, timeout - idle_seconds) if loaded and self.settings.model_idle_unload_enabled else None
        return {
            "state": state,
            "loaded": loaded,
            "error": error,
            "lastActivityAt": last_activity_at.isoformat(),
            "idleSeconds": round(idle_seconds, 3),
            "automaticUnloadEnabled": bool(self.settings.model_idle_unload_enabled),
            "idleTimeoutSeconds": timeout,
            "idleSecondsRemaining": None if remaining is None else round(remaining, 3),
            "memoryPolicyEnabled": bool(self.settings.model_memory_policy_enabled),
            "allowTwoMediumModels": bool(self.settings.allow_two_medium_models),
            "mediumEquivalentLimit": 2 if self.settings.allow_two_medium_models else 1,
            "active": self.active_models(),
        }

    def _model_idle_worker(self):
        while not self.stop_event.is_set():
            timeout = max(0.1, float(self.settings.model_idle_timeout_seconds))
            interval = min(30.0, max(0.1, timeout / 4.0))
            if self.stop_event.wait(interval):
                return
            if not self.settings.model_idle_unload_enabled:
                continue
            if time.monotonic() - self._last_model_activity_monotonic < timeout:
                continue
            try:
                self.unload_models(reason="idle_timeout")
            except RuntimeError:
                # Active audio and pending work are expected reasons to postpone unloading.
                continue
            except Exception:
                LOGGER.exception("Automatisches Entladen inaktiver Modelle fehlgeschlagen")

    def try_activate_speaker(self, session_id):
        return self.sessions.try_activate_speaker(session_id)

    def deactivate_speaker(self, session_id):
        self.sessions.deactivate_speaker(session_id)

    def session_count(self):
        return self.sessions.count()

    def active_speaker_count(self):
        return self.sessions.active_speaker_count()

    def packet_to_server_samples(self, packet):
        if len(packet.audio) > self.settings.max_audio_packet_bytes:
            raise AudioPacketError("Das Audiopaket ist zu groß")

        sample_rate = require_positive_int(packet.metadata, "sampleRate")
        channels = packet.metadata.get("channels", 1)
        if isinstance(channels, bool) or not isinstance(channels, int) or channels <= 0:
            raise AudioPacketError("Das Audiopaket-Metadatenfeld 'channels' muss eine positive Ganzzahl sein")
        if channels > 8:
            raise AudioPacketError("Das Audiopaket-Metadatenfeld 'channels' darf höchstens 8 sein")
        audio_format = packet.metadata.get("format", "pcm_s16le")
        if audio_format != "pcm_s16le":
            raise AudioPacketError("Es werden nur pcm_s16le-Audiopakete unterstützt")
        frame_width = channels * 2
        if len(packet.audio) % frame_width:
            raise AudioPacketError("Das pcm_s16le-Audiopaket ist nicht an vollständigen Frames ausgerichtet")
        if "frames" in packet.metadata:
            expected_frames = require_positive_int(packet.metadata, "frames")
            expected_bytes = expected_frames * frame_width
            if len(packet.audio) != expected_bytes:
                raise AudioPacketError(
                    "Das Audiopaket-Metadatenfeld 'frames' stimmt nicht mit der Nutzdatenlänge überein"
                )

        samples = np.frombuffer(packet.audio, dtype=np.int16)
        if channels > 1:
            usable = len(samples) - (len(samples) % channels)
            if usable <= 0:
                return np.array([], dtype=np.int16)
            samples = samples[:usable].reshape(-1, channels).mean(axis=1).astype(np.int16)
        return resample_int16(samples, sample_rate, SERVER_SAMPLE_RATE)

    def metrics(self):
        data = self.sessions.snapshots()
        data["ready"] = self.ready.is_set()
        with self._scheduler_lock:
            scheduler = self.scheduler
            data["ok"] = self.ready.is_set() and (scheduler is None or scheduler.healthy())
            data["scheduler"] = (
                scheduler.snapshot()
                if scheduler is not None
                else {"mode": "unloaded", "queues": {}, "workers": {}}
            )
        data["models"] = self.model_lifecycle_status()
        data["limits"] = self.limits_dict()
        data["startupErrors"] = list(self.startup_errors)
        return data

    def limits_dict(self):
        return {
            "maxSessions": self.settings.max_sessions,
            "maxActiveSpeakers": self.settings.max_active_speakers,
            "maxAudioQueueSecondsPerSession": self.settings.max_audio_queue_seconds_per_session,
            "maxRealtimeQueueAgeMs": self.settings.max_realtime_queue_age_ms,
            "maxFinalQueueDepthPerSession": self.settings.max_final_queue_depth_per_session,
            "maxGlobalInferenceQueueDepth": self.settings.max_global_inference_queue_depth,
            "realtimeDegradationThresholdMs": self.settings.realtime_degradation_threshold_ms,
        }

    def runtime_settings_contract(self):
        return runtime_settings_contract()

    def session_capabilities(self):
        with self._settings_lock:
            configured_paths = self.settings.openwakeword_model_paths
            inference_framework = (
                self.settings.openwakeword_inference_framework
            )
        models = self.wakeword_registry.openwakeword_models(
            configured_paths,
            inference_framework,
        )
        return {
            "version": 1,
            "wakeWord": {
                "supported": bool(models),
                "backends": ["openwakeword"],
                "availableWakeWords": [
                    {
                        "id": item["id"],
                        "label": item["label"],
                        "availableFormats": item["availableFormats"],
                        "default": bool(item.get("default")),
                    }
                    for item in models
                ],
                "queryParameters": [
                    "wakeWordEnabled",
                    *SESSION_WAKE_WORD_QUERY_FIELDS,
                ],
            },
            # Announced only because the whole contract behind it works: the
            # `trigger` command is processed, every command is answered with a
            # correlated `trigger_ack`, `commandId` is idempotent, and an
            # accepted activation actually drives the recorder gate.
            "activationTriggers": {
                "supported": True,
                "version": 2,
                "sources": list(ACTIVATION_SOURCES_PUBLIC),
                "actions": list(ACTIVATION_ACTIONS_PUBLIC),
                "commandType": "trigger",
                "ackType": "trigger_ack",
                "commandIdRequired": True,
                "commandIdIdempotent": True,
                # The replay cache holds for the whole session, as required by
                # the frozen idempotency contract.
                "commandHistory": "session",
                "activationIdValidated": True,
                "audioAvailabilityCommandType": "audio_availability",
                "audioAvailabilityAckType": "audio_availability_ack",
                "queryParameters": list(SESSION_ACTIVATION_QUERY_FIELDS),
                "activationEvents": [
                    "activation.started",
                    "activation.refreshed",
                    "activation.closed",
                    "watchdog.warning",
                ],
            },
        }

    def create_log_access(self, session_id):
        store_status = self.events.store_status()
        base = {
            "available": bool(
                self.settings.log_live_enabled
                and store_status["available"]
            ),
            "websocketPath": "/ws/logs",
            "historyPath": "/api/logs/events",
            "sessionId": session_id,
            "logProtocolVersion": 2,
            "deliveryMode": "sqlite_first",
            "replayAvailable": bool(store_status["available"]),
            "serverInstanceId": self.events.server_instance_id,
            "oldestCursor": store_status["oldestCursor"],
            "latestCursor": store_status["latestCursor"],
        }
        if not base["available"]:
            if not self.settings.log_live_enabled:
                base.update({
                    "code": "log_live_disabled",
                    "reason": "Der Live-Logzugriff ist deaktiviert.",
                })
            else:
                base.update({
                    "code": "event_store_unavailable",
                    "reason": "Der kanonische SQLite-Eventstore ist nicht verfügbar.",
                })
            return base
        token = uuid.uuid4().hex + uuid.uuid4().hex
        expires_at = time.time() + 24 * 60 * 60
        with self._log_access_lock:
            now = time.time()
            self._log_access_tokens = {
                existing: value
                for existing, value in self._log_access_tokens.items()
                if value["expiresAt"] > now
            }
            self._log_access_tokens[token] = {
                "sessionId": session_id,
                "expiresAt": expires_at,
            }
        return {
            **base,
            "accessToken": token,
            "expiresAt": timestamp_iso(expires_at),
        }

    def validate_log_access(self, token, session_id=None):
        if not token:
            return None
        with self._log_access_lock:
            access = self._log_access_tokens.get(str(token))
            if access is None or access["expiresAt"] <= time.time():
                self._log_access_tokens.pop(str(token), None)
                return None
            if session_id and access["sessionId"] != session_id:
                return None
            return dict(access)

    def ready_payload(self, session):
        model_status = self.model_lifecycle_status()
        return {
            "type": "ready",
            "sessionId": session.session_id,
            "settings": session.public_settings(),
            "sessionConfig": session.session_config_dict(),
            "activationConfig": session.activation_config_dict(),
            "sessionCapabilities": self.session_capabilities(),
            "limits": self.limits_dict(),
            "runtimeSettings": self.runtime_settings_contract(),
            "ok": model_status["loaded"] is False or self.metrics()["ok"],
            "models": model_status,
        }

    def update_settings(self, updates):
        applied = {}
        rejected = {}
        if not isinstance(updates, dict):
            raise ValueError("Die Einstellungsänderung muss ein JSON-Objekt sein")

        with self._settings_lock:
            coerced_updates = {}
            for name, value in updates.items():
                if name in STARTUP_ONLY_SETTINGS:
                    rejected[name] = {
                        "reason": "startup_only",
                        "message": "Diese Einstellung erfordert einen Serverneustart, da gemeinsam genutzte Ressourcen bereits initialisiert sind.",
                    }
                    continue
                if name not in ACTIVE_RUNTIME_SETTINGS and name not in NEW_SESSION_RUNTIME_SETTINGS:
                    rejected[name] = {
                        "reason": "unknown",
                        "message": "Unbekannte oder nicht unterstützte Servereinstellung.",
                    }
                    continue
                try:
                    coerced = coerce_setting_value(name, value)
                except ValueError as exc:
                    rejected[name] = {
                        "reason": "invalid_value",
                        "message": str(exc),
                    }
                    continue
                coerced_updates[name] = coerced

            proposed_live = coerced_updates.get(
                "log_live_enabled",
                self.settings.log_live_enabled,
            )
            proposed_live = coerced_updates.get(
                "log_live_enabled",
                self.settings.log_live_enabled,
            )
            if (
                proposed_live
                and not self.settings.event_store_enabled
                and "log_live_enabled" in coerced_updates
            ):
                rejected["log_live_enabled"] = {
                    "reason": "invalid_dependency",
                    "message": (
                        "log_live_enabled erfordert den beim Start aktivierten "
                        "event_store_enabled."
                    ),
                }
                coerced_updates.pop("log_live_enabled", None)

            for name, coerced in coerced_updates.items():
                setattr(self.settings, name, coerced)
                applied[name] = {
                    "value": coerced,
                    "appliesTo": (
                        "active_sessions"
                        if name in ACTIVE_RUNTIME_SETTINGS
                        else "new_sessions"
                    ),
                }
            if "transcript_log_mode" in applied:
                self.settings.request_log_transcripts = (
                    self.settings.transcript_log_mode != "none"
                )
            elif "request_log_transcripts" in applied:
                self.settings.transcript_log_mode = (
                    "final"
                    if self.settings.request_log_transcripts
                    else "none"
                )

        if applied:
            logging_names = {
                "log_calendar_timezone",
                "log_live_enabled",
                "realtime_log_detail",
                "transcript_log_mode",
                "request_log_backup_count",
                "request_log_max_bytes",
                "request_log_retention_days",
                "request_log_stdout",
                "request_log_transcripts",
                "request_logging_enabled",
                "save_audio_files",
                "performance_log_backup_count",
                "performance_log_max_bytes",
                "performance_log_mirror_enabled",
                "performance_log_retention_days",
                "performance_log_stdout",
                "performance_logging_enabled",
                "system_event_log_backup_count",
                "system_event_log_max_bytes",
                "system_event_log_retention_days",
                "system_event_log_stdout",
                "system_event_logging_enabled",
                "transcription_log_backup_count",
                "transcription_log_max_bytes",
                "transcription_log_retention_days",
                "transcription_log_stdout",
                "transcription_logging_enabled",
            }
            if any(name in logging_names for name in applied):
                self.events.configure(self.settings)
                self.audit.configure(self.settings, configure_hub=False)
                self.performance.configure(
                    self.settings,
                    configure_hub=False,
                )
            if "log_level" in applied:
                apply_process_log_level(self.settings.log_level)
            self.audit.event("config.updated", applied=applied)
            self.persist_settings()

        return {
            "applied": applied,
            "rejected": rejected,
            "settings": self.settings.public_dict(),
            "runtimeSettings": self.runtime_settings_contract(),
        }

    def persist_settings(self):
        allowed = (
            ACTIVE_RUNTIME_SETTINGS
            | NEW_SESSION_RUNTIME_SETTINGS
            | STARTUP_ONLY_SETTINGS
        ) - {
            "admin_api_key", "data_root_path", "openai_api_key",
            "runtime_config_path",
            "device", "host", "port",
        }
        return self.config_store.save(self.settings, allowed)

    def _persist_settings_control(self, overlay, revision):
        """Persists the AP-SRV-050 server-default overlay + its revision."""
        return self.config_store.save_settings_control(overlay, revision)

    def model_catalog(self):
        main_engine = normalize_engine_name(self.settings.transcription_engine)
        realtime_engine = normalize_engine_name(
            self.settings.realtime_transcription_engine or self.settings.transcription_engine
        )
        main_aliases = {value.lower() for value in self.model_registry.aliases_for(
            main_engine, self.settings.model
        )}
        realtime_aliases = {value.lower() for value in self.model_registry.aliases_for(
            realtime_engine, self.settings.realtime_model or self.settings.model
        )}
        entries = []
        for entry in self.model_registry.list_models():
            candidates = {
                str(entry.get("id") or "").lower(), str(entry.get("alias") or "").lower(),
                str(entry.get("name") or "").lower(), str(entry.get("folder") or "").lower(),
                str(entry.get("path") or "").lower(),
            }
            lanes = []
            if entry["engine"] == main_engine and candidates & main_aliases:
                lanes.append("final")
            if entry["engine"] == realtime_engine and candidates & realtime_aliases:
                lanes.append("realtime")
            item = dict(entry)
            item["loaded"] = bool(lanes) and self.scheduler is not None
            item["lanes"] = lanes
            entries.append(item)
        return entries

    def active_models(self):
        return {
            "final": {
                "engine": normalize_engine_name(self.settings.transcription_engine),
                "model": self.settings.model,
            },
            "realtime": {
                "engine": normalize_engine_name(
                    self.settings.realtime_transcription_engine or self.settings.transcription_engine
                ),
                "model": self.settings.realtime_model or self.settings.model,
                "sharedWithFinal": bool(self.settings.use_main_model_for_realtime),
            },
        }

    def switch_models(self, updates, timeout=180.0):
        allowed = {
            "model", "realtime_model", "transcription_engine",
            "realtime_transcription_engine", "use_main_model_for_realtime",
            "language", "transcription_engine_options",
            "realtime_transcription_engine_options",
        }
        unknown = set(updates) - allowed
        if unknown:
            raise ValueError("Nicht unterstützte Modelleinstellung(en): " + ", ".join(sorted(unknown)))

        candidate = replace(self.settings)
        for name, value in updates.items():
            setattr(candidate, name, coerce_setting_value(name, value))
        if (
            "use_main_model_for_realtime" not in updates
            and any(name in updates for name in {
                "model", "realtime_model", "transcription_engine",
                "realtime_transcription_engine",
            })
        ):
            candidate.use_main_model_for_realtime = False
        enforce_cpu_model_policy(candidate)
        requested_lanes = (
            (
                "final", normalize_engine_name(candidate.transcription_engine),
                candidate.model, normalize_engine_name(self.settings.transcription_engine),
                self.settings.model,
            ),
            (
                "realtime",
                normalize_engine_name(candidate.realtime_transcription_engine or candidate.transcription_engine),
                candidate.realtime_model or candidate.model,
                normalize_engine_name(
                    self.settings.realtime_transcription_engine or self.settings.transcription_engine
                ),
                self.settings.realtime_model or self.settings.model,
            ),
        )
        for lane, engine, model, current_engine, current_model in requested_lanes:
            if engine == current_engine and str(model).lower() == str(current_model).lower():
                continue
            if self.model_registry.resolve(model, preferred_engine=engine) is None:
                raise ValueError(
                    f"Das angeforderte {lane}-Modell '{model}' ist nicht in der eingebundenen lokalen Modellregistrierung vorhanden."
                )
        changed = {
            name: {"old": getattr(self.settings, name), "new": getattr(candidate, name)}
            for name in allowed
            if getattr(self.settings, name) != getattr(candidate, name)
        }
        if not changed:
            return {"changed": {}, "active": self.active_models(), "reloaded": False}

        switch_started = time.monotonic()
        memory_before = process_memory_snapshot()
        with self._scheduler_lock:
            self.ready.clear()
            if self._model_state == "loading":
                self.ready.set()
                raise RuntimeError("Ein Modellwechsel ist während des Ladens der Modell-Worker gesperrt.")
            previous = {name: getattr(self.settings, name) for name in allowed}
            old_scheduler = self.scheduler
            if old_scheduler is None:
                for name in allowed:
                    setattr(self.settings, name, getattr(candidate, name))
                self.ready.set()
                self.audit.event("models.switched", changed=changed, active=self.active_models())
                self._log_model_performance(
                    "models.switched", switch_started, memory_before,
                    reloaded=False, changed=changed,
                )
                self.persist_settings()
                return {
                    "changed": changed,
                    "active": self.active_models(),
                    "reloaded": False,
                    "lifecycle": self.model_lifecycle_status(),
                }
            replacement = None
            try:
                old_scheduler.stop()
                for name in allowed:
                    setattr(self.settings, name, getattr(candidate, name))
                replacement = self._new_scheduler()
                self.scheduler = replacement
                replacement.start()
                ready = replacement.wait_ready(timeout=timeout)
                if not ready or not replacement.healthy():
                    raise RuntimeError("Der neue Modell-Worker hat keinen fehlerfreien Zustand erreicht.")
            except Exception as exc:
                if replacement is not None:
                    try:
                        replacement.stop()
                    except Exception:
                        pass
                for name, value in previous.items():
                    setattr(self.settings, name, value)
                rollback = self._new_scheduler()
                self.scheduler = rollback
                rollback.start()
                rollback_ready = rollback.wait_ready(timeout=timeout)
                if rollback_ready and rollback.healthy():
                    self.ready.set()
                    raise RuntimeError(
                        "Der neue Modell-Worker ist fehlgeschlagen; die vorherige Modellkonfiguration wurde wiederhergestellt. "
                        f"Ursache: {exc}"
                    ) from exc
                raise RuntimeError(
                    "Der neue Modell-Worker ist fehlgeschlagen und der vorherige Worker konnte nicht wiederhergestellt werden. "
                    f"Ursache: {exc}"
                ) from exc
            self.ready.set()

        self.audit.event("models.switched", changed=changed, active=self.active_models())
        self._log_model_performance(
            "models.switched", switch_started, memory_before,
            reloaded=True, changed=changed,
        )
        self.persist_settings()
        return {"changed": changed, "active": self.active_models(), "reloaded": True}

    def transcribe_for_recorder(
        self,
        session_id,
        kind,
        audio,
        language,
        use_prompt,
        segment_context=None,
    ):
        from VoiceSTT.transcription_engines import TranscriptionResult

        session = self.sessions.get(session_id)
        if session is None:
            return TranscriptionResult(text="")

        generation = getattr(session, "generation", 0)
        request_id = (
            segment_context.request_id
            if kind == "final" and segment_context is not None
            else uuid.uuid4().hex
        )
        holder = {
            "event": threading.Event(),
            "result": None,
            "error": None,
            "sessionId": session_id,
            "generation": generation,
            "segmentContext": segment_context,
        }
        with self._pending_recorder_lock:
            self._pending_recorder_results[request_id] = holder

        job = InferenceJob(
            request_id=request_id,
            session_id=session_id,
            kind=kind,
            audio=audio,
            language=language,
            use_prompt=use_prompt,
            segment_id=(
                segment_context.segment_id
                if segment_context is not None
                else session.segment_state.current()
            ),
            sequence=0,
            generation=generation,
            created_at=time.monotonic(),
            deadline_at=(
                time.monotonic() + (self.settings.max_realtime_queue_age_ms / 1000.0)
                if kind == "realtime"
                else None
            ),
            client_id=getattr(session, "client_id", None),
            segment_context=segment_context,
        )

        submit_result = self.submit_inference_job(job)
        if not submit_result.accepted:
            self._pop_pending_recorder_result(request_id)
            raise RuntimeError(submit_result.reason)

        while not holder["event"].wait(timeout=0.1):
            current_session = self.sessions.get(session_id)
            if (
                self.stop_event.is_set()
                or current_session is None
                or getattr(current_session, "generation", generation) != generation
            ):
                self._pop_pending_recorder_result(request_id)
                return TranscriptionResult(text="")

        self._pop_pending_recorder_result(request_id)
        current_session = self.sessions.get(session_id)
        if current_session is None or getattr(current_session, "generation", generation) != generation:
            return TranscriptionResult(text="")

        if holder["error"]:
            if kind == "final" and segment_context is not None:
                current_session._dispatch_ledger_operation(
                    current_session.segment_ledger.resolve_terminal,
                    segment_context,
                    "failed",
                    str(holder["error"]),
                )
            raise RuntimeError(holder["error"])

        result = holder["result"]
        if result is None:
            return TranscriptionResult(text="")
        if result.error:
            if kind == "final" and segment_context is not None:
                current_session._dispatch_ledger_operation(
                    current_session.segment_ledger.resolve_terminal,
                    segment_context,
                    "failed",
                    str(result.error),
                )
            raise RuntimeError(result.error)

        current_session.record_executor_result(result)
        return TranscriptionResult(text=result.text)

    def complete_pending_recorder_transcription(self, result: InferenceResult):
        with self._pending_recorder_lock:
            holder = self._pending_recorder_results.get(result.request_id)
        if holder is None:
            return False
        holder["result"] = result
        holder["event"].set()
        return True

    def transcribe_openai(
        self,
        lane,
        audio,
        language=None,
        options=None,
        timeout=600.0,
        correlation_id=None,
        client_id=None,
    ):
        """Submit an OpenAI request to the same fair queues as realtime clients."""

        request_id = uuid.uuid4().hex
        session_id = f"openai-{request_id}"
        holder = {
            "event": threading.Event(),
            "result": None,
            "error": None,
            "correlationId": correlation_id,
            "clientId": client_id,
        }
        with self._pending_api_lock:
            self._pending_api_results[request_id] = holder
        job = InferenceJob(
            request_id=request_id,
            session_id=session_id,
            kind=lane,
            audio=audio,
            language=language,
            use_prompt=True,
            segment_id=0,
            sequence=0,
            generation=0,
            created_at=time.monotonic(),
            request_options=dict(options or {}),
            client_id=client_id,
        )
        submitted = self._submit_scheduler_job(job, "openai_transcription_submitted")
        if not submitted.accepted:
            with self._pending_api_lock:
                self._pending_api_results.pop(request_id, None)
            raise RuntimeError(submitted.reason)
        if not holder["event"].wait(timeout=timeout):
            self.cancel_scheduler_session(session_id)
            with self._pending_api_lock:
                self._pending_api_results.pop(request_id, None)
            raise TimeoutError("Zeitüberschreitung der Transkriptionsanfrage.")
        with self._pending_api_lock:
            self._pending_api_results.pop(request_id, None)
        if holder["error"]:
            raise RuntimeError(holder["error"])
        return holder["result"]

    def complete_pending_api_transcription(self, result):
        with self._pending_api_lock:
            holder = self._pending_api_results.get(result.request_id)
        if holder is None:
            return False
        holder["result"] = result
        holder["error"] = result.error
        holder["event"].set()
        return True

    def resolve_openai_model(self, model, override=None, override_source=None):
        requested = str(model or "").strip()
        selected = str(override or "").strip()
        if selected and requested.lower() != "whisper-1":
            raise OpenAIRequestError(
                "Eine Modellüberschreibung wird nur bei model='whisper-1' akzeptiert.",
                "voicestt_model",
                "invalid_model_override",
            )
        effective = selected or requested
        aliases = {
            "whisper-1": "final",
            "main": "final",
            "default": "final",
            str(self.settings.model).lower(): "final",
        }
        for value in self.model_registry.aliases_for(
            self.settings.transcription_engine, self.settings.model
        ):
            aliases[str(value).lower()] = "final"
        if not self.settings.use_main_model_for_realtime:
            aliases.update({
                "realtime": "realtime",
                str(self.settings.realtime_model).lower(): "realtime",
            })
            for value in self.model_registry.aliases_for(
                self.settings.realtime_transcription_engine or self.settings.transcription_engine,
                self.settings.realtime_model or self.settings.model,
            ):
                aliases[str(value).lower()] = "realtime"
        for key, value in dict(self.settings.openai_model_aliases or {}).items():
            normalized_lane = str(value).strip().lower()
            if normalized_lane == "main":
                normalized_lane = "final"
            if normalized_lane not in {"final", "realtime"}:
                raise ValueError(f"Ungültige OpenAI-Modellroute für '{key}': {value}")
            aliases[str(key).lower()] = normalized_lane
        lane = aliases.get(effective.lower())
        if lane is None:
            available = self.model_registry.resolve(effective)
            if available is not None:
                raise OpenAIRequestError(
                    f"Modell '{effective}' ist lokal verfügbar, aber nicht geladen. "
                    "Aktiviere es zuerst über PUT /api/models/active.",
                    "model",
                    "model_not_loaded",
                    409,
                )
            raise OpenAIRequestError(
                f"Modell '{effective}' ist nicht geladen. Verfügbare Aliasse: {', '.join(sorted(aliases))}.",
                "model",
                "model_not_found",
                404,
            )
        resolved_model = (
            self.settings.model
            if lane == "final"
            else (self.settings.realtime_model or self.settings.model)
        )
        return {
            "lane": lane,
            "requested": requested,
            "override": selected or None,
            "overrideSource": override_source if selected else None,
            "effective": effective,
            "resolved": str(resolved_model),
        }

    def resolve_openai_lane(self, model):
        return self.resolve_openai_model(model)["lane"]

    def fail_pending_recorder_transcription(self, request_id, error):
        with self._pending_recorder_lock:
            holder = self._pending_recorder_results.get(request_id)
        if holder is None:
            return False
        holder["error"] = error
        holder["event"].set()
        return True

    def cancel_pending_recorder_transcriptions(self, session_id):
        with self._pending_recorder_lock:
            pending = [
                (request_id, holder)
                for request_id, holder in self._pending_recorder_results.items()
                if holder["sessionId"] == session_id
            ]
        for request_id, holder in pending:
            holder["error"] = "Die Sitzung wurde abgebrochen"
            holder["event"].set()
            self._pop_pending_recorder_result(request_id)

    def _pop_pending_recorder_result(self, request_id):
        with self._pending_recorder_lock:
            return self._pending_recorder_results.pop(request_id, None)

    def _ready_worker(self, scheduler, load_started=None, memory_before=None):
        scheduler.wait_ready()
        self.ready.set()
        self.events.emit(
            "system",
            "server.ready",
            message="Server ist bereit",
            healthy=scheduler.healthy(),
            models=self.active_models(),
        )
        if load_started is not None:
            self._log_model_performance(
                "models.loaded" if scheduler.healthy() else "models.load_failed",
                load_started,
                memory_before or {},
                reason="startup",
            )
        for session in self.sessions.all():
            self.manager.publish_session(
                session.session_id,
                self.ready_payload(session),
            )
        if self.startup_errors:
            for error in self.startup_errors:
                self.manager.publish_all(error)

    def _on_inference_result(self, result: InferenceResult):
        self.touch_model_activity(f"{result.kind}_completed")
        audio_duration = max(0.0, float(result.audio_duration_seconds or 0.0))
        inference_duration = max(0.0, float(result.inference_duration or 0.0))
        lane = "realtime" if result.kind == "realtime" else "final"
        active = self.active_models()[lane]
        with self._pending_api_lock:
            api_holder = self._pending_api_results.get(result.request_id)
        external_request_id = (
            api_holder.get("correlationId")
            if api_holder is not None
            else None
        )
        session = self.sessions.get(result.session_id)
        correlated_client_id = (
            api_holder.get("clientId")
            if api_holder is not None
            else getattr(session, "client_id", None)
        ) or result.client_id
        transport = "http" if external_request_id else "websocket"
        correlated_session_id = external_request_id or result.session_id
        transcription_id = (
            external_request_id
            or (
                f"{result.session_id}:{result.generation}:{result.segment_id}"
                if result.session_id
                else result.request_id
            )
        )
        self.performance.event(
            "inference.completed",
            requestId=external_request_id or result.request_id,
            schedulerRequestId=result.request_id,
            sessionId=correlated_session_id,
            transcriptionId=transcription_id,
            transport=transport,
            clientId=correlated_client_id,
            segmentId=result.segment_id,
            lane=lane,
            engine=active["engine"],
            model=active["model"],
            success=result.error is None,
            error=result.error,
            audioDurationSeconds=round(audio_duration, 6),
            queueDelayMs=round(result.queue_delay * 1000.0, 3),
            inferenceMs=round(inference_duration * 1000.0, 3),
            totalLatencyMs=round(result.total_latency * 1000.0, 3),
            realTimeFactor=(
                round(inference_duration / audio_duration, 6)
                if audio_duration > 0 else None
            ),
            realTimeFactorX=(
                round(audio_duration / inference_duration, 6)
                if inference_duration > 0 else None
            ),
            activeSessions=self.session_count(),
            activeSpeakers=self.active_speaker_count(),
            memory=process_memory_snapshot(),
        )
        if self.complete_pending_api_transcription(result):
            return
        if self.complete_pending_recorder_transcription(result):
            return
        if session is not None:
            session.handle_inference_result(result)

    def _on_scheduler_drop(self, job: InferenceJob, reason: str, lane: str):
        with self._pending_api_lock:
            api_holder = self._pending_api_results.get(job.request_id)
        if api_holder is not None:
            api_holder["error"] = f"{job.kind} transcription was {reason}"
            api_holder["event"].set()
            return
        session = self.sessions.get(job.session_id)
        if session is not None:
            session.on_job_dropped(job, reason)
        else:
            self.fail_pending_recorder_transcription(
                job.request_id,
                f"{job.kind} transcription was {reason}",
            )

    def _on_scheduler_error(self, lane, exc):
        message = {
            "type": "error",
            "message": str(exc),
            "where": f"{lane}_engine",
        }
        self.events.emit(
            "system",
            "worker.failed",
            message="Serverkomponente fehlgeschlagen",
            severity="error",
            component=f"{lane}_engine",
            errorType=type(exc).__name__,
            error=str(exc),
        )
        self.startup_errors.append(message)
        self.manager.publish_all(message)


@dataclass(frozen=True)
class AudioData:
    samples: Any
    sample_rate: int


def read_wav_float32(path: Path):
    with wave.open(str(path), "rb") as wav:
        channels = wav.getnchannels()
        sample_width = wav.getsampwidth()
        sample_rate = wav.getframerate()
        frames = wav.readframes(wav.getnframes())

    if sample_width != 2:
        raise ValueError(f"{path} muss eine 16-Bit-PCM-WAV-Datei sein")
    samples = np.frombuffer(frames, dtype=np.int16)
    if channels > 1:
        usable = len(samples) - (len(samples) % channels)
        samples = samples[:usable].reshape(-1, channels).mean(axis=1).astype(np.int16)
    samples = resample_int16(samples, sample_rate, SERVER_SAMPLE_RATE)
    return AudioData(samples=samples.astype(np.float32) / INT16_MAX_ABS_VALUE, sample_rate=SERVER_SAMPLE_RATE)


def decode_audio_float32(data):
    """Decode every official transcription upload format to mono 16 kHz float32."""

    try:
        from faster_whisper.audio import decode_audio
    except ModuleNotFoundError as exc:
        raise RuntimeError("faster-whisper wird zum Dekodieren hochgeladener Audiodateien benötigt") from exc
    samples = decode_audio(io.BytesIO(data), sampling_rate=SERVER_SAMPLE_RATE)
    return np.asarray(samples, dtype=np.float32).reshape(-1)


def resample_int16(samples, source_rate, target_rate):
    samples = np.asarray(samples, dtype=np.int16)
    if source_rate == target_rate or samples.size == 0:
        return samples.copy()

    try:
        from scipy.signal import resample_poly

        divisor = math.gcd(int(source_rate), int(target_rate))
        up = int(target_rate // divisor)
        down = int(source_rate // divisor)
        resampled = resample_poly(samples.astype(np.float32), up, down)
    except Exception:
        duration = samples.size / float(source_rate)
        target_size = max(1, int(round(duration * target_rate)))
        source_positions = np.linspace(0.0, 1.0, num=samples.size, endpoint=False)
        target_positions = np.linspace(0.0, 1.0, num=target_size, endpoint=False)
        resampled = np.interp(target_positions, source_positions, samples.astype(np.float32))

    return np.clip(np.rint(resampled), -32768, 32767).astype(np.int16)


def effective_device(device):
    if str(device).lower() != "cpu":
        raise ValueError("Diese Installation arbeitet ausschließlich mit der CPU; device muss 'cpu' sein.")
    return "cpu"
    return device


def model_size_rank(engine, model):
    """Return the CPU memory class used by the two-model admission policy."""

    engine = normalize_engine_name(engine or "faster_whisper")
    value = str(model or "").lower().replace("_", "-")
    if engine in {"kroko", "kroko_onnx", "banafo_kroko"}:
        return 2
    if engine != "faster_whisper":
        return None
    standard_turbo_names = {
        "large-v3-turbo",
        "faster-whisper-large-v3-turbo",
        "large-turbo",
    }
    is_standard_large_v3_turbo = (
        value in standard_turbo_names
        or value.endswith("--faster-whisper-large-v3-turbo")
        or value.endswith("/faster-whisper-large-v3-turbo")
        or value.endswith("\\faster-whisper-large-v3-turbo")
    )
    if is_standard_large_v3_turbo:
        return 3
    if "large" in value:
        return 4
    if "medium" in value:
        return 3
    if "small" in value:
        return 2
    if "base" in value or "tiny" in value:
        return 1
    return None


def enforce_cpu_model_policy(settings):
    """Enforce the configurable CPU-only two-lane model memory guard."""

    settings.device = "cpu"
    realtime_engine = settings.realtime_transcription_engine or settings.transcription_engine
    if (
        normalize_engine_name(realtime_engine) == normalize_engine_name(settings.transcription_engine)
        and str(settings.realtime_model or settings.model) == str(settings.model)
    ):
        settings.use_main_model_for_realtime = True
    if settings.use_main_model_for_realtime:
        return
    if not settings.model_memory_policy_enabled:
        return
    ranks = [
        model_size_rank(settings.transcription_engine, settings.model),
        model_size_rank(realtime_engine, settings.realtime_model or settings.model),
    ]
    if None in ranks:
        return
    medium_equivalents = sum(rank >= 3 for rank in ranks)
    allowed_medium_equivalents = 2 if settings.allow_two_medium_models else 1
    if max(ranks) > 3 or medium_equivalents > allowed_medium_equivalents:
        raise ValueError(
            "Die CPU-Modellrichtlinie hat diese Kombination abgelehnt. Zwei geladene Engines dürfen höchstens "
            f"{allowed_medium_equivalents} Modell(e) bis Medium-Größe verwenden; das originale Faster-Whisper-"
            "large-v3-turbo zählt als Medium, andere Large-Modelle werden abgelehnt. Verwende "
            "--use-main-model-for-realtime für parallele Anfragen an dasselbe Modell oder deaktiviere "
            "die Begrenzung ausdrücklich, wenn du das zusätzliche CPU-/RAM-Risiko akzeptierst."
        )


def load_fastapi():
    try:
        from fastapi import FastAPI, WebSocket, WebSocketDisconnect
        from fastapi.responses import HTMLResponse, JSONResponse
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "FastAPI-Serverabhängigkeiten fehlen. Installiere sie mit "
            "'python -m pip install -r api_fastapi_server/requirements.txt'."
        ) from exc
    return FastAPI, WebSocket, WebSocketDisconnect, HTMLResponse, JSONResponse


def create_app(settings: Optional[ServerSettings] = None, scheduler_factory=None, recorder_factory=None):
    FastAPI, WebSocket, WebSocketDisconnect, HTMLResponse, JSONResponse = load_fastapi()
    from contextlib import asynccontextmanager
    from fastapi import Request
    from fastapi.responses import Response, StreamingResponse
    from VoiceSTT.transcription_engines import get_supported_transcription_engines

    settings = settings or ServerSettings()
    if settings.runtime_config_path:
        persisted = RuntimeConfigStore(settings.runtime_config_path).load()
        for name, value in persisted.items():
            if (
                hasattr(settings, name)
                and name not in DERIVED_DATA_PATH_SETTINGS
                and name not in {
                    "admin_api_key",
                    "data_root_path",
                    "openai_api_key",
                }
            ):
                setattr(settings, name, coerce_setting_value(name, value))
    # Re-derive generated paths and validate cross-setting dependencies after
    # persisted startup/runtime values have been applied.
    settings.__post_init__()
    enforce_cpu_model_policy(settings)
    manager = ConnectionManager()
    service = VoiceSTTService(
        settings,
        manager,
        scheduler_factory=scheduler_factory,
        recorder_factory=recorder_factory,
    )

    @asynccontextmanager
    async def lifespan(app):
        service.start(asyncio.get_running_loop())
        yield
        service.stop()

    app = FastAPI(
        title="VoiceSTT FastAPI-Server",
        version="2.0.0",
        lifespan=lifespan,
    )

    @app.get("/")
    async def index():
        return HTMLResponse(INDEX_PATH.read_text(encoding="utf-8"))

    @app.get("/health")
    async def health():
        metrics = service.metrics()
        event_store = service.events.store_status()
        logging_ready = (
            not settings.log_live_enabled
            or event_store["available"]
        )
        return JSONResponse({
            "ok": bool(metrics["ok"] and logging_ready),
            "ready": metrics["ready"],
            "activeSessions": metrics["activeSessions"],
            "activeSpeakers": metrics["activeSpeakers"],
            "rejectedSessions": metrics["rejectedSessions"],
            "scheduler": metrics["scheduler"],
            "models": metrics["models"],
            "startupErrors": metrics["startupErrors"],
            "eventStore": event_store,
        })

    @app.get("/api/config")
    async def config():
        return JSONResponse({
            "settings": settings.public_dict(),
            "limits": service.limits_dict(),
            "supportedEngines": get_supported_transcription_engines(),
            "runtimeSettings": service.runtime_settings_contract(),
            "sessionCapabilities": service.session_capabilities(),
            "adminAuthRequired": bool(settings.admin_api_key or os.getenv("VOICESTT_ADMIN_API_KEY")),
        })

    def _admin_key_matches(supplied):
        configured_key = settings.admin_api_key or os.getenv(
            "VOICESTT_ADMIN_API_KEY"
        )
        if not configured_key or supplied is None:
            return False
        return secrets.compare_digest(str(supplied), str(configured_key))

    def admin_auth_error(request):
        configured_key = settings.admin_api_key or os.getenv("VOICESTT_ADMIN_API_KEY")
        supplied = request.headers.get("x-voicestt-admin-key")
        authorization = request.headers.get("authorization", "")
        if not supplied and authorization.startswith("Bearer "):
            supplied = authorization[7:]
        if not supplied:
            # AP-SRV-050: ``X-Admin-Key`` is an alias inside the *same* guard,
            # so the frozen server contract header works without weakening any
            # existing compatible auth path.
            supplied = request.headers.get("x-admin-key")
        if configured_key:
            if not _admin_key_matches(supplied):
                return JSONResponse(
                    {"error": "Admin-Authentifizierung erforderlich."},
                    status_code=401,
                    headers={"WWW-Authenticate": "Bearer"},
                )
            return None
        client_host = getattr(getattr(request, "client", None), "host", "")
        if client_host not in {"127.0.0.1", "::1", "localhost", "testclient"}:
            return JSONResponse(
                {"error": "Die Remote-Verwaltung ist deaktiviert, bis VOICESTT_ADMIN_API_KEY gesetzt ist."},
                status_code=403,
            )
        return None

    @app.patch("/api/config")
    async def update_config(payload: dict, request: Request):
        auth_error = admin_auth_error(request)
        if auth_error is not None:
            return auth_error
        updates = payload.get("settings", payload)
        try:
            result = service.update_settings(updates)
        except ValueError as exc:
            return JSONResponse(
                {"error": str(exc)},
                status_code=400,
            )
        return JSONResponse(
            result,
            status_code=400 if result["rejected"] else 200,
        )

    @app.get("/api/metrics")
    async def metrics():
        return JSONResponse(service.metrics())

    @app.get("/api/models")
    async def api_models(request: Request):
        auth_error = admin_auth_error(request)
        if auth_error is not None:
            return auth_error
        catalog = []
        for entry in service.model_catalog():
            catalog.append({key: value for key, value in entry.items() if key != "path"})
        return JSONResponse({
            "object": "list",
            "active": service.active_models(),
            "lifecycle": service.model_lifecycle_status(),
            "data": catalog,
        })

    @app.get("/api/models/lifecycle")
    async def get_model_lifecycle(request: Request):
        auth_error = admin_auth_error(request)
        if auth_error is not None:
            return auth_error
        return JSONResponse(service.model_lifecycle_status())

    @app.put("/api/models/lifecycle")
    async def configure_model_lifecycle(payload: dict, request: Request):
        auth_error = admin_auth_error(request)
        if auth_error is not None:
            return auth_error
        mapping = {
            "automaticUnloadEnabled": "model_idle_unload_enabled",
            "idleTimeoutSeconds": "model_idle_timeout_seconds",
            "memoryPolicyEnabled": "model_memory_policy_enabled",
            "allowTwoMediumModels": "allow_two_medium_models",
            "model_idle_unload_enabled": "model_idle_unload_enabled",
            "model_idle_timeout_seconds": "model_idle_timeout_seconds",
            "model_memory_policy_enabled": "model_memory_policy_enabled",
            "allow_two_medium_models": "allow_two_medium_models",
        }
        unknown = set(payload) - set(mapping)
        if unknown:
            return JSONResponse(
                {"error": "Nicht unterstützte Lebenszykluseinstellung(en): " + ", ".join(sorted(unknown))},
                status_code=400,
            )
        updates = {}
        try:
            for supplied, name in mapping.items():
                if supplied in payload:
                    updates[name] = coerce_setting_value(name, payload[supplied])
            if "model_idle_timeout_seconds" in updates and updates["model_idle_timeout_seconds"] < 1:
                raise ValueError("idleTimeoutSeconds muss mindestens 1 Sekunde betragen")
            candidate = replace(settings)
            for name, value in updates.items():
                setattr(candidate, name, value)
            enforce_cpu_model_policy(candidate)
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        service.update_settings(updates)
        service.touch_model_activity("lifecycle_configuration_updated")
        return JSONResponse(service.model_lifecycle_status())

    @app.post("/api/models/load")
    async def load_models(request: Request):
        auth_error = admin_auth_error(request)
        if auth_error is not None:
            return auth_error
        try:
            return JSONResponse(await asyncio.to_thread(service.load_models))
        except RuntimeError as exc:
            return JSONResponse({"error": str(exc)}, status_code=500)

    @app.post("/api/models/unload")
    async def unload_models(request: Request):
        auth_error = admin_auth_error(request)
        if auth_error is not None:
            return auth_error
        try:
            return JSONResponse(await asyncio.to_thread(service.unload_models, "manual_api"))
        except RuntimeError as exc:
            return JSONResponse({"error": str(exc)}, status_code=409)

    @app.get("/api/models/active")
    async def active_models(request: Request):
        auth_error = admin_auth_error(request)
        if auth_error is not None:
            return auth_error
        return JSONResponse(service.active_models())

    @app.put("/api/models/active")
    async def switch_active_models(payload: dict, request: Request):
        auth_error = admin_auth_error(request)
        if auth_error is not None:
            return auth_error
        try:
            result = await asyncio.to_thread(service.switch_models, payload)
            return JSONResponse(result)
        except ValueError as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        except RuntimeError as exc:
            status = 409 if "keine WebSocket-Sitzungen" in str(exc) else 500
            return JSONResponse({"error": str(exc)}, status_code=status)

    @app.get("/api/language")
    async def get_language(request: Request):
        auth_error = admin_auth_error(request)
        if auth_error is not None:
            return auth_error
        return JSONResponse({"language": settings.language, "default": "de"})

    @app.put("/api/language")
    async def set_language(payload: dict, request: Request):
        auth_error = admin_auth_error(request)
        if auth_error is not None:
            return auth_error
        language = str(payload.get("language") or "").strip().lower()
        if not language:
            return JSONResponse({"error": "language ist erforderlich"}, status_code=400)
        result = service.update_settings({"language": language})
        if "language" in result["rejected"]:
            # Language is startup-only in the generic contract but safe for new requests/sessions.
            settings.language = language
            service.persist_settings()
            service.audit.event("language.updated", language=language)
        return JSONResponse({"language": settings.language, "appliesTo": "new_requests_and_sessions"})

    @app.get("/api/wake-word")
    async def get_wake_word(request: Request):
        auth_error = admin_auth_error(request)
        if auth_error is not None:
            return auth_error
        available_models = service.wakeword_registry.catalog(
            settings.openwakeword_model_paths,
            settings.openwakeword_inference_framework,
        )
        return JSONResponse({
            "enabled": settings.wake_word_enabled(),
            "backend": settings.wakeword_backend,
            "words": settings.wake_words,
            "sensitivity": settings.wake_words_sensitivity,
            "timeout": settings.wake_word_timeout,
            "bufferDuration": settings.wake_word_buffer_duration,
            "followupWindow": settings.wake_word_followup_window,
            "openwakewordModelPaths": settings.openwakeword_model_paths,
            "availableModels": available_models,
            "appliesTo": "new_sessions",
        })

    @app.put("/api/wake-word")
    async def set_wake_word(payload: dict, request: Request):
        auth_error = admin_auth_error(request)
        if auth_error is not None:
            return auth_error
        enabled = payload.get("enabled", True)
        if not isinstance(enabled, bool):
            return JSONResponse({"error": "enabled muss ein boolescher Wert sein"}, status_code=400)
        if not enabled:
            updates = {"wakeword_backend": "", "wake_words": ""}
        else:
            backend = str(payload.get("backend") or settings.wakeword_backend or "openwakeword").strip().lower()
            words = str(payload.get("words") or settings.wake_words or "").strip()
            if backend not in OPENWAKEWORD_SESSION_BACKENDS:
                return JSONResponse(
                    {"error": "backend muss openwakeword sein"},
                    status_code=400,
                )
            candidate_paths = payload.get(
                "openwakewordModelPaths",
                settings.openwakeword_model_paths,
            )
            resolved, missing = service.wakeword_registry.resolve_openwakeword(
                words or None,
                candidate_paths,
                settings.openwakeword_inference_framework,
            )
            if missing:
                return JSONResponse({
                    "error": "Mindestens ein Wake Word ist nicht verfügbar.",
                    "unavailableWakeWords": missing,
                }, status_code=400)
            if not resolved:
                return JSONResponse({
                    "error": "Kein verfügbares OpenWakeWord-Standardmodell gefunden."
                }, status_code=400)
            updates = {
                "wakeword_backend": "openwakeword",
                "wake_words": ",".join(item["id"] for item in resolved),
                "openwakeword_model_paths": ",".join(
                    item["path"] for item in resolved
                ),
            }
        mapping = {
            "sensitivity": "wake_words_sensitivity",
            "timeout": "wake_word_timeout",
            "bufferDuration": "wake_word_buffer_duration",
            "followupWindow": "wake_word_followup_window",
        }
        for source, target in mapping.items():
            if source in payload:
                updates[target] = payload[source]
        try:
            sensitivity = float(updates.get("wake_words_sensitivity", settings.wake_words_sensitivity))
            if not 0.0 <= sensitivity <= 1.0:
                raise ValueError("sensitivity muss zwischen 0 und 1 liegen")
            for name in ("wake_word_timeout", "wake_word_buffer_duration", "wake_word_followup_window"):
                if name in updates and float(updates[name]) < 0:
                    raise ValueError(f"{name} muss null oder größer sein")
        except (TypeError, ValueError) as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        result = service.update_settings(updates)
        return JSONResponse(result, status_code=400 if result["rejected"] else 200)

    # -- AP-SRV-050 settings REST-v2 surface ---------------------------------

    def _settings_server_identity():
        try:
            from api_fastapi_server.protocol_v2 import identity as _identity

            return _identity.server_version(), _identity.server_commit()
        except Exception:  # noqa: BLE001 - metadata must never break REST
            return "unknown", "unknown"

    @app.get("/api/v2/settings/schema")
    async def settings_schema_v2():
        # Public, non-secret registry metadata, deterministically sorted by key.
        version, commit = _settings_server_identity()
        return JSONResponse({
            "protocolVersion": protocol_v2_schema.PROTOCOL_VERSION,
            "serverVersion": version,
            "serverCommit": commit,
            "secretsExposed": False,
            "settings": service.settings_registry.schema_payload(),
        })

    @app.get("/api/v2/settings/server")
    async def settings_server_v2():
        # Public read: only non-secret server values and the server revision.
        version, commit = _settings_server_identity()
        return JSONResponse(service.settings_control.server_public(
            server_version=version,
            server_commit=commit,
        ))

    @app.patch("/api/v2/settings/server")
    async def patch_settings_server_v2(payload: dict, request: Request):
        auth_error = admin_auth_error(request)
        if auth_error is not None:
            return auth_error
        if not isinstance(payload, dict):
            return JSONResponse({
                "accepted": False,
                "result": protocol_v2_schema.RESULT_SETTINGS_REJECTED,
                "errors": [{
                    "field": "body",
                    "code": "invalid_payload",
                    "message": "Der Patch muss ein JSON-Objekt sein.",
                }],
            }, status_code=400)
        result = service.settings_control.patch_server(
            payload.get("baseSettingsRevision"),
            payload.get("changes"),
        )
        if result.accepted and settings_control_module.WAKE_WORD_GLOBAL_DISABLED in (
            result.changed_keys or ()
        ):
            # The catalog owns availability, the settings plane owns the value:
            # re-project the confirmed disable list onto the one catalog.
            service.apply_wake_word_global_disable()
        status = 409 if result.result == "settings_revision_conflict" else (
            500 if result.result == "internal_error" else (
                422 if result.result == "settings_rejected" else 200
            )
        )
        return JSONResponse(result.to_dict(), status_code=status)

    @app.get("/api/v2/wake-words")
    async def wake_words_v2():
        # SET-13b: the versioned, publicly readable build catalog. It never
        # contains a filesystem path, a source marker or an internal artifact
        # map, and availability already includes the global disable list.
        return JSONResponse(service.wakeword_catalog.public_payload(
            protocol_version=protocol_v2_schema.PROTOCOL_VERSION,
        ))

    @app.post("/api/v2/wake-words/refresh")
    async def refresh_wake_words_v2(request: Request):
        # Additive admin action behind the *same* existing admin guard as the
        # v2 server settings - there is no second auth implementation.
        auth_error = admin_auth_error(request)
        if auth_error is not None:
            return auth_error
        result = service.refresh_wake_word_catalog()
        # Root F10: revision, entries and availability all come from the one
        # snapshot this refresh committed - the authority is never read again.
        payload = result.public_payload(
            protocol_version=protocol_v2_schema.PROTOCOL_VERSION
        )
        # A failed refresh keeps the last known good catalog untouched and
        # says so; it never empties or half-replaces the running catalog.
        return JSONResponse(payload, status_code=200 if result.ok else 422)

    @app.get("/api/logging")
    async def get_logging_config(request: Request):
        auth_error = admin_auth_error(request)
        if auth_error is not None:
            return auth_error
        event_store = service.events.store_status()
        return JSONResponse({
            "dataRoot": settings.data_root_path,
            "enabled": settings.request_logging_enabled,
            "stdout": settings.request_log_stdout,
            "file": settings.request_log_path,
            "transcripts": settings.request_log_transcripts,
            "transcriptMode": (
                settings.transcript_log_mode
                or (
                    "final"
                    if settings.request_log_transcripts
                    else "none"
                )
            ),
            "saveAudio": settings.save_audio_files,
            "audioDirectory": settings.audio_log_dir,
            "maxBytes": settings.request_log_max_bytes,
            "backupCount": settings.request_log_backup_count,
            "retentionDays": settings.request_log_retention_days,
            "performance": {
                "enabled": settings.performance_logging_enabled,
                "mirrorEnabled": settings.performance_log_mirror_enabled,
                "stdout": settings.performance_log_stdout,
                "file": settings.performance_log_path,
                "maxBytes": settings.performance_log_max_bytes,
                "backupCount": settings.performance_log_backup_count,
                "retentionDays": settings.performance_log_retention_days,
            },
            "transcription": {
                "enabled": settings.transcription_logging_enabled,
                "stdout": settings.transcription_log_stdout,
                "directory": settings.transcription_log_path,
                "maxBytes": settings.transcription_log_max_bytes,
                "backupCount": settings.transcription_log_backup_count,
                "retentionDays": settings.transcription_log_retention_days,
            },
            "system": {
                "enabled": settings.system_event_logging_enabled,
                "stdout": settings.system_event_log_stdout,
                "directory": settings.system_event_log_path,
                "maxBytes": settings.system_event_log_max_bytes,
                "backupCount": settings.system_event_log_backup_count,
                "retentionDays": settings.system_event_log_retention_days,
            },
            "calendarTimezone": settings.log_calendar_timezone,
            "realtimeDetail": settings.realtime_log_detail,
            "liveEnabled": settings.log_live_enabled,
            "logProtocolVersion": 2,
            "deliveryMode": "sqlite_first",
            "replayAvailable": event_store["available"],
            "eventStore": {
                "enabled": settings.event_store_enabled,
                "path": settings.event_store_path,
                **event_store,
            },
        })

    @app.put("/api/logging")
    async def set_logging_config(payload: dict, request: Request):
        auth_error = admin_auth_error(request)
        if auth_error is not None:
            return auth_error
        derived_path_fields = {
            "audioDirectory",
            "file",
            "performanceFile",
            "systemDirectory",
            "transcriptionDirectory",
        }
        supplied_path_fields = sorted(derived_path_fields.intersection(payload))
        if supplied_path_fields:
            return JSONResponse({
                "error": (
                    "Logpfade werden aus data_root_path abgeleitet und sind "
                    "nicht einzeln konfigurierbar."
                ),
                "fields": supplied_path_fields,
            }, status_code=400)
        mapping = {
            "enabled": "request_logging_enabled", "stdout": "request_log_stdout",
            "transcripts": "request_log_transcripts",
            "transcriptMode": "transcript_log_mode",
            "saveAudio": "save_audio_files",
            "maxBytes": "request_log_max_bytes", "backupCount": "request_log_backup_count",
            "retentionDays": "request_log_retention_days",
            "performanceEnabled": "performance_logging_enabled",
            "performanceMirrorEnabled": "performance_log_mirror_enabled",
            "performanceStdout": "performance_log_stdout",
            "performanceMaxBytes": "performance_log_max_bytes",
            "performanceBackupCount": "performance_log_backup_count",
            "performanceRetentionDays": "performance_log_retention_days",
            "transcriptionEnabled": "transcription_logging_enabled",
            "transcriptionStdout": "transcription_log_stdout",
            "transcriptionMaxBytes": "transcription_log_max_bytes",
            "transcriptionBackupCount": "transcription_log_backup_count",
            "transcriptionRetentionDays": "transcription_log_retention_days",
            "systemEnabled": "system_event_logging_enabled",
            "systemStdout": "system_event_log_stdout",
            "systemMaxBytes": "system_event_log_max_bytes",
            "systemBackupCount": "system_event_log_backup_count",
            "systemRetentionDays": "system_event_log_retention_days",
            "calendarTimezone": "log_calendar_timezone",
            "realtimeDetail": "realtime_log_detail",
            "liveEnabled": "log_live_enabled",
        }
        updates = {target: payload[source] for source, target in mapping.items() if source in payload}
        try:
            if "request_log_max_bytes" in updates and int(updates["request_log_max_bytes"]) <= 0:
                raise ValueError("maxBytes muss größer als null sein")
            if "request_log_backup_count" in updates and int(updates["request_log_backup_count"]) < 0:
                raise ValueError("backupCount muss null oder größer sein")
            if "performance_log_max_bytes" in updates and int(updates["performance_log_max_bytes"]) <= 0:
                raise ValueError("performanceMaxBytes muss größer als null sein")
            if "performance_log_backup_count" in updates and int(updates["performance_log_backup_count"]) < 0:
                raise ValueError("performanceBackupCount muss null oder größer sein")
        except (TypeError, ValueError) as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        result = service.update_settings(updates)
        return JSONResponse(result, status_code=400 if result["rejected"] else 200)

    def _split_filter(value):
        return [
            item.strip()
            for item in str(value or "").split(",")
            if item.strip()
        ]

    def _log_access_scope(request, requested_session_id=None):
        configured_key = settings.admin_api_key or os.getenv(
            "VOICESTT_ADMIN_API_KEY"
        )
        authorization = request.headers.get("authorization", "")
        supplied = request.headers.get("x-voicestt-admin-key")
        bearer = authorization[7:] if authorization.startswith("Bearer ") else ""
        supplied = supplied or bearer
        if configured_key and _admin_key_matches(supplied):
            return {"admin": True, "sessionId": requested_session_id}
        client_host = getattr(getattr(request, "client", None), "host", "")
        if not configured_key and client_host in {
            "127.0.0.1",
            "::1",
            "localhost",
            "testclient",
        }:
            return {"admin": True, "sessionId": requested_session_id}
        token = request.headers.get("x-voicestt-log-token") or bearer
        access = service.validate_log_access(token, requested_session_id)
        if access is None:
            return None
        return {"admin": False, "sessionId": access["sessionId"]}

    def _log_events_response(
        request,
        *,
        session_id_override=None,
        transcription_id_override=None,
    ):
        requested_session_id = (
            session_id_override
            if session_id_override is not None
            else request.query_params.get("sessionId")
        )
        scope = _log_access_scope(request, requested_session_id)
        if scope is None:
            return JSONResponse(
                {"error": "Logzugriff nicht autorisiert."},
                status_code=401,
            )
        session_id = (
            requested_session_id
            if scope["admin"]
            else scope["sessionId"]
        )
        channels = _split_filter(request.query_params.get("channels"))
        if not scope["admin"]:
            allowed = {"audit", "performance", "transcription"}
            if channels:
                channels = [
                    channel for channel in channels if channel in allowed
                ] or ["__not_authorized__"]
            else:
                channels = sorted(allowed)
        if not service.events.store_available():
            return JSONResponse(
                {
                    "error": "Der kanonische SQLite-Eventstore ist nicht verfügbar.",
                    "code": "event_store_unavailable",
                },
                status_code=503,
            )
        try:
            events = service.events.query(
                channels=channels,
                events=_split_filter(request.query_params.get("events")),
                session_id=session_id,
                transcription_id=(
                    transcription_id_override
                    if transcription_id_override is not None
                    else request.query_params.get("transcriptionId")
                ),
                from_timestamp=request.query_params.get("from"),
                to_timestamp=request.query_params.get("to"),
                after_cursor=int(request.query_params.get("afterCursor") or 0),
                limit=int(request.query_params.get("limit") or 200),
            )
            oldest_cursor = service.events.oldest_cursor()
            latest_cursor = service.events.latest_cursor()
            retention_cursor = service.events.retention_cursor(
                channels=channels,
                session_id=session_id,
            )
        except (TypeError, ValueError) as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        except Exception:
            LOGGER.exception("Historische Eventabfrage ist fehlgeschlagen")
            return JSONResponse(
                {
                    "error": "Der kanonische SQLite-Eventstore ist nicht verfügbar.",
                    "code": "event_store_unavailable",
                },
                status_code=503,
            )
        return JSONResponse({
            "object": "list",
            "data": events,
            "nextCursor": events[-1]["cursor"] if events else None,
            "oldestCursor": oldest_cursor,
            "latestCursor": latest_cursor,
            "retentionCursor": retention_cursor,
            "authorizationScope": "admin" if scope["admin"] else "session",
            "allSessions": bool(scope["admin"] and not session_id),
            "deliveryMode": "sqlite_first",
        })

    @app.get("/api/logs/events")
    async def get_log_events(request: Request):
        return _log_events_response(request)

    @app.get("/api/logs/sessions/{session_id}")
    async def get_session_log_events(session_id: str, request: Request):
        return _log_events_response(
            request,
            session_id_override=session_id,
        )

    @app.get("/api/logs/transcriptions/{transcription_id}")
    async def get_transcription_log_events(
        transcription_id: str,
        request: Request,
    ):
        return _log_events_response(
            request,
            transcription_id_override=transcription_id,
        )

    @app.websocket("/ws/logs")
    async def websocket_logs(websocket: WebSocket):
        await websocket.accept()
        if not settings.log_live_enabled:
            await websocket.send_text(json.dumps({
                "type": "log.error",
                "code": "log_live_disabled",
                "message": "Der Live-Logzugriff ist deaktiviert.",
            }))
            await websocket.close(code=1008)
            return
        if not service.events.store_available():
            await websocket.send_text(json.dumps({
                "type": "log.error",
                "code": "event_store_unavailable",
                "message": (
                    "Der kanonische SQLite-Eventstore ist nicht verfügbar."
                ),
            }))
            await websocket.close(code=1011)
            return
        subscription_id = None
        try:
            raw = await websocket.receive_text()
            request_payload = json.loads(raw)
            if (
                not isinstance(request_payload, dict)
                or request_payload.get("type") != "subscribe"
            ):
                raise ValueError("Erste Nachricht muss ein subscribe-Objekt sein.")
            token = str(request_payload.get("accessToken") or "")
            requested_session_id = request_payload.get("sessionId")
            configured_key = settings.admin_api_key or os.getenv(
                "VOICESTT_ADMIN_API_KEY"
            )
            is_admin = bool(configured_key and _admin_key_matches(token))
            access = (
                None
                if is_admin
                else service.validate_log_access(token, requested_session_id)
            )
            if not is_admin and access is None:
                await websocket.send_text(json.dumps({
                    "type": "log.error",
                    "code": "not_authorized",
                    "message": "Logzugriff nicht autorisiert.",
                }))
                await websocket.close(code=1008)
                return
            session_id = (
                requested_session_id
                if is_admin
                else access["sessionId"]
            )
            channels = {
                str(channel)
                for channel in request_payload.get("channels", [])
                if str(channel)
            }
            if not is_admin:
                allowed = {"audit", "performance", "transcription"}
                channels = (
                    channels & allowed
                    if channels
                    else allowed
                ) or {"__not_authorized__"}
            after_cursor = int(request_payload.get("afterCursor") or 0)
            if after_cursor < 0:
                await websocket.send_text(json.dumps({
                    "type": "log.error",
                    "code": "invalid_cursor",
                    "message": "afterCursor darf nicht negativ sein.",
                }))
                await websocket.close(code=1008)
                return
            live_queue = asyncio.Queue(maxsize=1000)
            subscription_id = service.events.subscribe_async(
                asyncio.get_running_loop(),
                live_queue,
                channels=channels,
                session_id=session_id,
            )
            oldest_cursor = service.events.oldest_cursor()
            latest_cursor = service.events.latest_cursor()
            retention_cursor = service.events.retention_cursor(
                channels=channels,
                session_id=session_id,
            )
            if after_cursor > latest_cursor:
                await websocket.send_text(json.dumps({
                    "type": "log.error",
                    "code": "cursor_ahead",
                    "message": (
                        "afterCursor liegt vor dem aktuellen SQLite-Cursor."
                    ),
                    "afterCursor": after_cursor,
                    "latestCursor": latest_cursor,
                    "serverInstanceId": service.events.server_instance_id,
                }))
                await websocket.close(code=1008)
                return
            await websocket.send_text(json.dumps({
                "type": "log.hello",
                "schemaVersion": 1,
                "logProtocolVersion": 2,
                "deliveryMode": "sqlite_first",
                "replayAvailable": True,
                "serverInstanceId": service.events.server_instance_id,
                "oldestCursor": oldest_cursor,
                "latestCursor": latest_cursor,
                "retentionCursor": retention_cursor,
            }))
            authorization_scope = "admin" if is_admin else "session"
            await websocket.send_text(json.dumps({
                "type": "log.subscribed",
                "channels": sorted(channels),
                "sessionId": session_id,
                "afterCursor": after_cursor,
                "authorizationScope": authorization_scope,
                "allChannels": bool(is_admin and not channels),
                "allSessions": bool(is_admin and not session_id),
            }))
            replay_cursor = after_cursor
            if retention_cursor > replay_cursor:
                await websocket.send_text(json.dumps({
                    "type": "log.gap",
                    "reason": "retention",
                    "lostFromCursor": replay_cursor + 1,
                    "lostToCursor": retention_cursor,
                    "oldestCursor": oldest_cursor,
                    "latestCursor": latest_cursor,
                }))
            replay_count = 0
            while replay_cursor < latest_cursor:
                replay = service.events.query(
                    channels=channels,
                    session_id=session_id,
                    after_cursor=replay_cursor,
                    until_cursor=latest_cursor,
                    limit=1000,
                )
                if not replay:
                    break
                for event in replay:
                    await websocket.send_text(json.dumps({
                        "type": "log.event",
                        "event": event,
                        "replay": True,
                    }))
                replay_count += len(replay)
                replay_cursor = int(replay[-1]["cursor"])
                if len(replay) < 1000:
                    break
            await websocket.send_text(json.dumps({
                "type": "log.replay_completed",
                "cursor": latest_cursor,
                "count": replay_count,
            }))
            scan_cursor = latest_cursor
            receive_task = asyncio.create_task(websocket.receive_text())
            event_task = None
            try:
                while True:
                    event_task = asyncio.create_task(live_queue.get())
                    done, _ = await asyncio.wait(
                        {receive_task, event_task},
                        timeout=LOG_STREAM_KEEPALIVE_SECONDS,
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    if not done:
                        event_task.cancel()
                        await asyncio.gather(
                            event_task,
                            return_exceptions=True,
                        )
                        event_task = None
                    if receive_task in done:
                        command = json.loads(receive_task.result())
                        if (
                            isinstance(command, dict)
                            and command.get("type") == "ping"
                        ):
                            await websocket.send_text(json.dumps({
                                "type": "log.pong",
                                "cursor": scan_cursor,
                                "serverTime": time.time(),
                            }))
                        else:
                            await websocket.send_text(json.dumps({
                                "type": "log.error",
                                "message": "Unbekannter Log-WebSocket-Befehl.",
                            }))
                        receive_task = asyncio.create_task(
                            websocket.receive_text()
                        )
                    if event_task is not None and event_task not in done:
                        event_task.cancel()
                        await asyncio.gather(
                            event_task,
                            return_exceptions=True,
                        )
                        event_task = None
                    elif event_task is not None:
                        control = event_task.result()
                        event_task = None
                        if control.get("_logControl") == "store_error":
                            await websocket.send_text(json.dumps({
                                "type": "log.error",
                                "code": "event_store_unavailable",
                                "message": (
                                    "Der kanonische SQLite-Eventstore ist "
                                    "nicht verfügbar."
                                ),
                            }))
                            await websocket.close(code=1011)
                            return

                    committed_cursor = service.events.latest_cursor()
                    live_retention_cursor = service.events.retention_cursor(
                        channels=channels,
                        session_id=session_id,
                    )
                    if live_retention_cursor > scan_cursor:
                        await websocket.send_text(json.dumps({
                            "type": "log.gap",
                            "reason": "retention",
                            "lostFromCursor": scan_cursor + 1,
                            "lostToCursor": live_retention_cursor,
                            "oldestCursor": service.events.oldest_cursor(),
                            "latestCursor": committed_cursor,
                        }))
                    live_count = 0
                    query_cursor = scan_cursor
                    while query_cursor < committed_cursor:
                        live_events = service.events.query(
                            channels=channels,
                            session_id=session_id,
                            after_cursor=query_cursor,
                            until_cursor=committed_cursor,
                            limit=1000,
                        )
                        if not live_events:
                            break
                        for event in live_events:
                            await websocket.send_text(json.dumps({
                                "type": "log.event",
                                "event": event,
                                "replay": False,
                            }))
                        live_count += len(live_events)
                        query_cursor = int(live_events[-1]["cursor"])
                        if len(live_events) < 1000:
                            break
                    scan_cursor = committed_cursor
                    if not done:
                        await websocket.send_text(json.dumps({
                            "type": "log.keepalive",
                            "cursor": scan_cursor,
                            "eventsSent": live_count,
                        }))
            finally:
                for task in (receive_task, event_task):
                    if task is not None and not task.done():
                        task.cancel()
                await asyncio.gather(
                    *(
                        task
                        for task in (receive_task, event_task)
                        if task is not None
                    ),
                    return_exceptions=True,
                )
        except (WebSocketDisconnect, asyncio.CancelledError):
            pass
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            await websocket.send_text(json.dumps({
                "type": "log.error",
                "code": "invalid_request",
                "message": str(exc),
            }))
            await websocket.close(code=1008)
        except Exception:
            LOGGER.exception("Log-WebSocket ist unerwartet fehlgeschlagen")
            try:
                await websocket.send_text(json.dumps({
                    "type": "log.error",
                    "code": "event_store_unavailable",
                    "message": (
                        "Der kanonische SQLite-Eventstore ist nicht verfügbar."
                    ),
                }))
                await websocket.close(code=1011)
            except (RuntimeError, WebSocketDisconnect):
                pass
        finally:
            if subscription_id is not None:
                service.events.unsubscribe(subscription_id)

    @app.post("/api/config/validate")
    async def validate_config(payload: dict, request: Request):
        auth_error = admin_auth_error(request)
        if auth_error is not None:
            return auth_error
        try:
            candidate = replace(settings)
            for name, value in payload.get("settings", payload).items():
                if not hasattr(candidate, name):
                    raise ValueError(f"Unbekannte Einstellung: {name}")
                if name in DERIVED_DATA_PATH_SETTINGS:
                    raise ValueError(
                        f"{name} wird aus data_root_path abgeleitet und darf nicht gesetzt werden"
                    )
                setattr(candidate, name, coerce_setting_value(name, value))
            candidate.__post_init__()
            enforce_cpu_model_policy(candidate)
            return JSONResponse({"valid": True, "settings": candidate.public_dict()})
        except ValueError as exc:
            return JSONResponse({"valid": False, "error": str(exc)}, status_code=400)

    @app.post("/api/config/reload")
    async def reload_config(request: Request):
        auth_error = admin_auth_error(request)
        if auth_error is not None:
            return auth_error
        try:
            persisted = service.config_store.load()
            model_updates = {
                name: value for name, value in persisted.items()
                if name in {"model", "realtime_model", "transcription_engine", "realtime_transcription_engine",
                            "use_main_model_for_realtime", "language", "transcription_engine_options",
                            "realtime_transcription_engine_options"}
            }
            runtime_updates = {
                name: value for name, value in persisted.items()
                if name in ACTIVE_RUNTIME_SETTINGS or name in NEW_SESSION_RUNTIME_SETTINGS
            }
            skipped = sorted(set(persisted) - set(model_updates) - set(runtime_updates))
            runtime_result = service.update_settings(runtime_updates)
            model_result = await asyncio.to_thread(service.switch_models, model_updates) if model_updates else None
            return JSONResponse({"runtime": runtime_result, "models": model_result, "skipped": skipped})
        except (OSError, ValueError, RuntimeError) as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)

    async def authenticate_openai(request):
        configured_key = settings.openai_api_key or os.getenv("VOICESTT_API_KEY")
        if not configured_key:
            return None
        if request.headers.get("authorization", "") != f"Bearer {configured_key}":
            supplied_client_id = request.headers.get("x-voicestt-client-id")
            service.audit.event(
                "authentication.failed",
                transport="http",
                clientId=(
                    normalized_client_id(supplied_client_id)
                    if supplied_client_id
                    else None
                ),
                path=request.url.path,
                reason="invalid_api_key",
            )
            return JSONResponse(
                openai_error("Der angegebene API-Schlüssel ist ungültig.", code="invalid_api_key"),
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )
        return None

    @app.get("/v1/models")
    async def openai_models(request: Request):
        auth_error = await authenticate_openai(request)
        if auth_error is not None:
            return auth_error
        models = []
        for entry in service.model_catalog():
            models.append({
                "id": entry["id"],
                "object": "model",
                "created": 0,
                "owned_by": "local",
                "engine": entry["engine"],
                "loaded": entry["loaded"],
                "lanes": entry["lanes"],
            })
        if not any(item["id"] == "whisper-1" for item in models):
            models.insert(0, {
                "id": "whisper-1", "object": "model", "created": 0,
                "owned_by": "voicestt", "engine": "routing_alias",
                "loaded": True, "lanes": ["final"],
            })
        return JSONResponse({"object": "list", "data": models})

    @app.post("/v1/audio/transcriptions")
    async def openai_transcriptions(request: Request):
        request_id = uuid.uuid4().hex
        supplied_client_id = request.headers.get("x-voicestt-client-id")
        client_id = (
            normalized_client_id(supplied_client_id)
            if supplied_client_id
            else None
        )
        request_started = time.monotonic()
        response_headers = {"X-Request-ID": request_id}
        resolution = None
        archived_audio = None

        def emit_http_transcription(event, severity="info", **fields):
            return service.events.emit(
                "transcription",
                event,
                severity=severity,
                transport="http",
                clientId=client_id,
                sessionId=request_id,
                requestId=request_id,
                transcriptionId=request_id,
                **fields,
            )
        if not settings.openai_api_enabled:
            emit_http_transcription(
                "transcription.rejected",
                severity="warning",
                reason="api_disabled",
            )
            return JSONResponse(
                openai_error("Die OpenAI-kompatible API ist deaktiviert."),
                status_code=404,
                headers=response_headers,
            )
        auth_error = await authenticate_openai(request)
        if auth_error is not None:
            emit_http_transcription(
                "transcription.rejected",
                severity="warning",
                reason="authentication_failed",
            )
            return auth_error
        try:
            form = await request.form()
            upload = form.get("file")
            if upload is None or not hasattr(upload, "read"):
                raise OpenAIRequestError("Das Feld 'file' ist erforderlich.", "file")
            validate_audio_filename(getattr(upload, "filename", ""))
            parameters = parse_transcription_form(form)
            form_override = str(
                form.get("voicestt_model") or form.get("model_override") or ""
            ).strip()
            header_override = str(request.headers.get("x-voicestt-model") or "").strip()
            override = form_override or header_override
            override_source = (
                "multipart.voicestt_model" if form_override
                else ("header.x-voicestt-model" if header_override else None)
            )
            resolution = service.resolve_openai_model(
                parameters.model,
                override=override,
                override_source=override_source,
            )
            lane = resolution["lane"]
            response_headers.update({
                "X-VoiceSTT-Requested-Model": resolution["requested"],
                "X-VoiceSTT-Resolved-Model": resolution["resolved"],
                "X-VoiceSTT-Route": resolution["lane"],
            })
            if resolution["override"]:
                response_headers["X-VoiceSTT-Override-Model"] = resolution["override"]
            if resolution["overrideSource"]:
                response_headers["X-VoiceSTT-Override-Source"] = resolution["overrideSource"]
            audio_bytes = await upload.read(settings.openai_max_file_bytes + 1)
            if len(audio_bytes) > settings.openai_max_file_bytes:
                raise OpenAIRequestError(
                    f"Die Audiodatei überschreitet das Serverlimit von {settings.openai_max_file_bytes} Byte.",
                    "file",
                    "file_too_large",
                    413,
                )
            archived_audio = service.audit.archive_audio(
                audio_bytes,
                getattr(upload, "filename", "audio"),
                request_id,
            )
            samples = await asyncio.to_thread(decode_audio_float32, audio_bytes)
            duration = len(samples) / float(SERVER_SAMPLE_RATE)
            selected_language = parameters.language or settings.language
            emit_http_transcription(
                "transcription.accepted",
                filename=getattr(upload, "filename", None),
                bytes=len(audio_bytes),
                requestedModel=resolution["requested"],
                resolvedModel=resolution["resolved"],
                lane=lane,
                stream=parameters.stream,
            )
            service.audit.event(
                "transcription.started",
                transport="http",
                clientId=client_id,
                sessionId=request_id,
                transcriptionId=request_id,
                requestId=request_id,
                filename=getattr(upload, "filename", None),
                bytes=len(audio_bytes),
                audioDurationSeconds=duration,
                requestedModel=resolution["requested"],
                overrideModel=resolution["override"],
                overrideSource=resolution["overrideSource"],
                resolvedModel=resolution["resolved"],
                lane=lane,
                language=selected_language,
                stream=parameters.stream,
                responseFormat=parameters.response_format,
                archivedAudio=archived_audio,
            )
            emit_http_transcription(
                "transcription.started",
                filename=getattr(upload, "filename", None),
                bytes=len(audio_bytes),
                audioDurationMs=round(duration * 1000.0, 3),
                requestedModel=resolution["requested"],
                resolvedModel=resolution["resolved"],
                lane=lane,
                language=selected_language,
                stream=parameters.stream,
                responseFormat=parameters.response_format,
            )
            request_options = {
                "prompt": parameters.prompt,
                "temperature": parameters.temperature,
                "threshold": parameters.threshold,
                "timestamp_granularities": parameters.timestamp_granularities,
            }

            if parameters.stream:
                queue = asyncio.Queue()
                event_loop = asyncio.get_running_loop()
                first_delta_lock = threading.Lock()
                first_delta_seen = False
                first_delta_at = None
                last_delta_at = None
                realtime_intervals_ms = []
                realtime_event_count = 0

                def record_http_first_text(text):
                    nonlocal first_delta_seen
                    if str(text or "").strip():
                        with first_delta_lock:
                            if not first_delta_seen:
                                first_delta_seen = True
                                service.performance.event(
                                    "http.first_text",
                                    transport="http",
                                    clientId=client_id,
                                    sessionId=request_id,
                                    transcriptionId=request_id,
                                    requestId=request_id,
                                    lane=lane,
                                    engine=service.active_models()[lane]["engine"],
                                    model=resolution["resolved"],
                                    timeToFirstTextMs=round(
                                        (time.monotonic() - request_started) * 1000.0,
                                        3,
                                    ),
                                    audioDurationSeconds=round(duration, 6),
                                    memory=process_memory_snapshot(),
                                )

                def stream_callback(text, _detail):
                    nonlocal first_delta_at, last_delta_at, realtime_event_count
                    record_http_first_text(text)
                    now = time.monotonic()
                    with first_delta_lock:
                        if first_delta_at is None:
                            first_delta_at = now
                        interval_ms = (
                            round((now - last_delta_at) * 1000.0, 3)
                            if last_delta_at is not None
                            else None
                        )
                        if interval_ms is not None:
                            realtime_intervals_ms.append(interval_ms)
                        last_delta_at = now
                        realtime_event_count += 1
                        sequence = realtime_event_count
                    if settings.realtime_log_detail == "events":
                        service.performance.event(
                            "transcription.realtime_emitted",
                            transport="http",
                            clientId=client_id,
                            sessionId=request_id,
                            transcriptionId=request_id,
                            requestId=request_id,
                            sequence=sequence,
                            sincePreviousMs=interval_ms,
                            sinceRequestStartMs=round(
                                (now - request_started) * 1000.0,
                                3,
                            ),
                            characterCount=len(str(text or "")),
                        )
                    event_loop.call_soon_threadsafe(
                        queue.put_nowait,
                        {"type": "transcript.text.delta", "delta": text},
                    )

                def emit_http_realtime_summary():
                    if settings.realtime_log_detail == "off":
                        return
                    with first_delta_lock:
                        intervals = sorted(realtime_intervals_ms)
                        count = realtime_event_count
                        first_realtime_at = first_delta_at

                    def selected_percentile(fraction):
                        if not intervals:
                            return None
                        index = max(
                            0,
                            min(
                                len(intervals) - 1,
                                math.ceil(len(intervals) * fraction) - 1,
                            ),
                        )
                        return round(intervals[index], 3)

                    service.performance.event(
                        "transcription.performance_summary",
                        transport="http",
                        clientId=client_id,
                        sessionId=request_id,
                        transcriptionId=request_id,
                        requestId=request_id,
                        realtimeEventCount=count,
                        averageRealtimeIntervalMs=(
                            round(sum(intervals) / len(intervals), 3)
                            if intervals
                            else None
                        ),
                        minRealtimeIntervalMs=(
                            min(intervals) if intervals else None
                        ),
                        maxRealtimeIntervalMs=(
                            max(intervals) if intervals else None
                        ),
                        p50RealtimeIntervalMs=selected_percentile(0.50),
                        p95RealtimeIntervalMs=selected_percentile(0.95),
                        timeToFirstRealtimeMs=(
                            round(
                                (first_realtime_at - request_started)
                                * 1000.0,
                                3,
                            )
                            if first_realtime_at is not None
                            else None
                        ),
                        timeToFinalMs=round(
                            (time.monotonic() - request_started) * 1000.0,
                            3,
                        ),
                    )

                request_options["stream_callback"] = stream_callback

                async def event_stream():
                    task = asyncio.create_task(asyncio.to_thread(
                        service.transcribe_openai,
                        lane,
                        samples,
                        selected_language,
                        request_options,
                        correlation_id=request_id,
                        client_id=client_id,
                    ))
                    while not task.done() or not queue.empty():
                        try:
                            yield sse_data(await asyncio.wait_for(queue.get(), timeout=0.1))
                        except asyncio.TimeoutError:
                            continue
                    try:
                        inference = await task
                    except Exception as exc:
                        service.audit.event(
                            "transcription.failed",
                            transport="http",
                            clientId=client_id,
                            sessionId=request_id,
                            transcriptionId=request_id,
                            requestId=request_id,
                            resolvedModel=resolution["resolved"],
                            lane=lane,
                            latencyMs=round((time.monotonic() - request_started) * 1000, 3),
                            error=str(exc),
                        )
                        emit_http_transcription(
                            "transcription.failed",
                            severity="error",
                            resolvedModel=resolution["resolved"],
                            lane=lane,
                            latencyMs=round(
                                (time.monotonic() - request_started) * 1000,
                                3,
                            ),
                            error=str(exc),
                        )
                        yield sse_data({"type": "error", "error": openai_error(str(exc))["error"]})
                        return
                    from VoiceSTT.transcription_engines import TranscriptionInfo, TranscriptionResult
                    result = TranscriptionResult(
                        text=inference.text,
                        info=TranscriptionInfo(language=selected_language),
                        details=inference.details or {},
                    )
                    payload = format_json_response(parameters, result, duration)
                    if parameters.response_format == "diarized_json":
                        for segment in payload["segments"]:
                            yield sse_data(segment)
                    done = {
                        "type": "transcript.text.done",
                        "text": inference.text,
                        "usage": payload.get("usage"),
                    }
                    if "logprobs" in parameters.include:
                        done["logprobs"] = payload.get("logprobs", [])
                    record_http_first_text(inference.text)
                    service.audit.event(
                        "transcription.completed",
                        transport="http",
                        clientId=client_id,
                        sessionId=request_id,
                        transcriptionId=request_id,
                        requestId=request_id,
                        resolvedModel=resolution["resolved"],
                        lane=lane,
                        language=selected_language,
                        audioDurationSeconds=duration,
                        queueDelayMs=round(inference.queue_delay * 1000, 3),
                        inferenceMs=round(inference.inference_duration * 1000, 3),
                        latencyMs=round((time.monotonic() - request_started) * 1000, 3),
                        text=inference.text,
                        archivedAudio=archived_audio,
                        stream=True,
                    )
                    emit_http_transcription(
                        "transcription.completed",
                        resolvedModel=resolution["resolved"],
                        lane=lane,
                        language=selected_language,
                        audioDurationMs=round(duration * 1000.0, 3),
                        queueDelayMs=round(inference.queue_delay * 1000, 3),
                        inferenceMs=round(
                            inference.inference_duration * 1000,
                            3,
                        ),
                        totalLatencyMs=round(
                            (time.monotonic() - request_started) * 1000,
                            3,
                        ),
                        text=inference.text,
                        stream=True,
                    )
                    service.performance.event(
                        "http.completed",
                        transport="http",
                        clientId=client_id,
                        sessionId=request_id,
                        transcriptionId=request_id,
                        requestId=request_id,
                        lane=lane,
                        engine=service.active_models()[lane]["engine"],
                        model=resolution["resolved"],
                        stream=True,
                        success=True,
                        audioDurationSeconds=round(duration, 6),
                        apiLatencyMs=round(
                            (time.monotonic() - request_started) * 1000.0, 3
                        ),
                        memory=process_memory_snapshot(),
                    )
                    emit_http_realtime_summary()
                    yield sse_data(done)

                return StreamingResponse(
                    event_stream(),
                    media_type="text/event-stream",
                    headers={
                        **response_headers,
                        "Cache-Control": "no-cache",
                        "X-Accel-Buffering": "no",
                    },
                )

            inference = await asyncio.to_thread(
                service.transcribe_openai,
                lane,
                samples,
                selected_language,
                request_options,
                correlation_id=request_id,
                client_id=client_id,
            )
            from VoiceSTT.transcription_engines import TranscriptionInfo, TranscriptionResult
            result = TranscriptionResult(
                text=inference.text,
                info=TranscriptionInfo(language=selected_language),
                details=inference.details or {},
            )
            service.audit.event(
                "transcription.completed",
                transport="http",
                clientId=client_id,
                sessionId=request_id,
                transcriptionId=request_id,
                requestId=request_id,
                resolvedModel=resolution["resolved"],
                lane=lane,
                language=selected_language,
                audioDurationSeconds=duration,
                queueDelayMs=round(inference.queue_delay * 1000, 3),
                inferenceMs=round(inference.inference_duration * 1000, 3),
                latencyMs=round((time.monotonic() - request_started) * 1000, 3),
                text=inference.text,
                archivedAudio=archived_audio,
                stream=False,
            )
            emit_http_transcription(
                "transcription.completed",
                resolvedModel=resolution["resolved"],
                lane=lane,
                language=selected_language,
                audioDurationMs=round(duration * 1000.0, 3),
                queueDelayMs=round(inference.queue_delay * 1000, 3),
                inferenceMs=round(inference.inference_duration * 1000, 3),
                totalLatencyMs=round(
                    (time.monotonic() - request_started) * 1000,
                    3,
                ),
                text=inference.text,
                stream=False,
            )
            service.performance.event(
                "http.completed",
                transport="http",
                clientId=client_id,
                sessionId=request_id,
                transcriptionId=request_id,
                requestId=request_id,
                lane=lane,
                engine=service.active_models()[lane]["engine"],
                model=resolution["resolved"],
                stream=False,
                success=True,
                audioDurationSeconds=round(duration, 6),
                apiLatencyMs=round(
                    (time.monotonic() - request_started) * 1000.0, 3
                ),
                memory=process_memory_snapshot(),
            )
            if settings.realtime_log_detail != "off":
                service.performance.event(
                    "transcription.performance_summary",
                    transport="http",
                    clientId=client_id,
                    sessionId=request_id,
                    transcriptionId=request_id,
                    requestId=request_id,
                    realtimeEventCount=0,
                    timeToFinalMs=round(
                        (time.monotonic() - request_started) * 1000.0,
                        3,
                    ),
                )
            if parameters.response_format in {"text", "srt", "vtt"}:
                body = format_caption_response(parameters, result, duration)
                media_type = "text/vtt" if parameters.response_format == "vtt" else "text/plain"
                return Response(content=body, media_type=media_type, headers=response_headers)
            return JSONResponse(
                format_json_response(parameters, result, duration),
                headers=response_headers,
            )
        except OpenAIRequestError as exc:
            service.audit.event(
                "transcription.rejected",
                transport="http",
                clientId=client_id,
                sessionId=request_id,
                transcriptionId=request_id,
                requestId=request_id,
                requestedModel=(resolution or {}).get("requested"),
                latencyMs=round((time.monotonic() - request_started) * 1000, 3),
                error=str(exc),
                param=exc.param,
                code=exc.code,
            )
            emit_http_transcription(
                "transcription.rejected",
                severity="warning",
                requestedModel=(resolution or {}).get("requested"),
                latencyMs=round(
                    (time.monotonic() - request_started) * 1000,
                    3,
                ),
                error=str(exc),
                param=exc.param,
                code=exc.code,
            )
            return JSONResponse(
                openai_error(exc, exc.param, exc.code),
                status_code=exc.status_code,
                headers=response_headers,
            )
        except Exception as exc:
            LOGGER.exception("OpenAI-kompatible Transkription fehlgeschlagen")
            service.audit.event(
                "transcription.failed",
                transport="http",
                clientId=client_id,
                sessionId=request_id,
                transcriptionId=request_id,
                requestId=request_id,
                requestedModel=(resolution or {}).get("requested"),
                resolvedModel=(resolution or {}).get("resolved"),
                latencyMs=round((time.monotonic() - request_started) * 1000, 3),
                error=str(exc),
            )
            emit_http_transcription(
                "transcription.failed",
                severity="error",
                requestedModel=(resolution or {}).get("requested"),
                resolvedModel=(resolution or {}).get("resolved"),
                latencyMs=round(
                    (time.monotonic() - request_started) * 1000,
                    3,
                ),
                error=str(exc),
            )
            return JSONResponse(
                openai_error(exc, error_type="server_error", code="transcription_failed"),
                status_code=500,
                headers=response_headers,
            )

    @app.websocket("/ws/transcribe")
    async def websocket_transcribe(websocket: WebSocket):
        client_id = normalized_client_id(
            websocket.query_params.get("clientId")
            or websocket.headers.get("x-voicestt-client-id")
        )
        try:
            wake_word_request = parse_session_wake_word_query(
                websocket.query_params
            )
            activation_request = parse_session_activation_query(
                websocket.query_params
            )
        except SessionConfigurationError as exc:
            await websocket.accept()
            await websocket.send_text(json.dumps(exc.payload()))
            await websocket.close(code=1008)
            service.audit.event(
                "session.rejected",
                transport="websocket",
                clientId=client_id,
                code=exc.code,
                reason="session_config",
            )
            return

        session_id = uuid.uuid4().hex
        try:
            session = service.admit_session(
                session_id,
                wake_word_request=wake_word_request,
                client_id=client_id,
                activation_request=activation_request,
            )
        except SessionConfigurationError as exc:
            await websocket.accept()
            await websocket.send_text(json.dumps(exc.payload()))
            await websocket.close(code=1008)
            service.audit.event(
                "session.rejected",
                sessionId=session_id,
                transport="websocket",
                clientId=client_id,
                code=exc.code,
                reason="session_config",
            )
            return
        except Exception:
            LOGGER.exception("WebSocket-Sitzung konnte nicht initialisiert werden")
            await websocket.accept()
            await websocket.send_text(json.dumps({
                "type": "error",
                "where": "session_config",
                "code": "session_initialization_failed",
                "message": "Die Sitzung konnte nicht initialisiert werden.",
            }))
            await websocket.close(code=1011)
            return
        if session is None:
            await websocket.accept()
            service.audit.event(
                "session.rejected",
                sessionId=session_id,
                transport="websocket",
                clientId=client_id,
                reason="session_limit",
            )
            await websocket.send_text(json.dumps({
                "type": "error",
                "where": "admission",
                "message": "Der Server hat das konfigurierte Sitzungslimit erreicht.",
                "limits": service.limits_dict(),
            }))
            await websocket.close(code=1013)
            return

        await manager.connect(session_id, websocket)
        service.audit.event(
            "session.accepted",
            sessionId=session_id,
            transport="websocket",
            clientId=client_id,
            requestedWakeWordEnabled=(
                session.session_config.requested_enabled
            ),
            effectiveWakeWordEnabled=(
                session.session_config.effective_enabled
            ),
        )
        log_access = service.create_log_access(session_id)
        await websocket.send_text(json.dumps({
            "type": "hello",
            "clientId": client_id,
            "sessionId": session_id,
            "settings": session.public_settings(),
            "sessionConfig": session.session_config_dict(),
            "activationConfig": session.activation_config_dict(),
            "sessionCapabilities": service.session_capabilities(),
            "limits": service.limits_dict(),
            "supportedEngines": get_supported_transcription_engines(),
            "runtimeSettings": service.runtime_settings_contract(),
            "logAccess": log_access,
        }))
        if service.ready.is_set():
            await websocket.send_text(json.dumps(
                service.ready_payload(session)
            ))
            for error in service.startup_errors:
                await websocket.send_text(json.dumps(error))

        try:
            while True:
                message = await websocket.receive()
                if "bytes" in message and message["bytes"] is not None:
                    try:
                        accepted, warning = session.ingest_audio_packet(
                            decode_audio_packet(message["bytes"])
                        )
                    except AudioPacketError as exc:
                        await websocket.send_text(json.dumps({
                            "type": "error",
                            "sessionId": session_id,
                            "message": str(exc),
                            "where": "audio_packet",
                        }))
                        continue
                    except Exception as exc:
                        LOGGER.exception("Audiopaket konnte nicht verarbeitet werden")
                        await websocket.send_text(json.dumps({
                            "type": "error",
                            "sessionId": session_id,
                            "message": str(exc),
                            "where": "audio",
                        }))
                        continue
                    if not accepted:
                        await websocket.send_text(json.dumps({
                            "type": "warning",
                            "sessionId": session_id,
                            "message": warning or "Der Audioabschnitt wurde abgelehnt.",
                        }))
                elif "text" in message and message["text"] is not None:
                    try:
                        data = json.loads(message["text"])
                    except json.JSONDecodeError as exc:
                        await websocket.send_text(json.dumps({
                            "type": "error",
                            "sessionId": session_id,
                            "message": f"Ungültiges Befehls-JSON: {exc.msg}",
                            "where": "command",
                        }))
                        continue

                    if not isinstance(data, dict):
                        await websocket.send_text(json.dumps({
                            "type": "error",
                            "sessionId": session_id,
                            "message": "WebSocket-Befehle müssen JSON-Objekte sein.",
                            "where": "command",
                        }))
                        continue

                    command = data.get("type")
                    if command == "start":
                        session.start_streaming()
                    elif command == "stop":
                        session.stop_streaming()
                    elif command == "clear":
                        session.clear()
                    elif command == "ping":
                        await websocket.send_text(json.dumps({
                            "type": "pong",
                            "sessionId": session_id,
                            "serverTime": time.time(),
                        }))
                    elif command == "metrics":
                        await websocket.send_text(json.dumps({
                            "type": "metrics",
                            "sessionId": session_id,
                            "metrics": session.snapshot(),
                        }))
                    elif command == "trigger":
                        ack = session.handle_trigger_command(data)
                        await websocket.send_text(json.dumps(ack))
                    elif command == "audio_availability":
                        ack = session.handle_audio_availability_command(data)
                        await websocket.send_text(json.dumps(ack))
                    else:
                        await websocket.send_text(json.dumps({
                            "type": "error",
                            "sessionId": session_id,
                            "message": f"Unbekannter Befehl: {command}",
                            "where": "command",
                        }))
        except WebSocketDisconnect:
            pass
        except RuntimeError as exc:
            if "disconnect" not in str(exc).lower():
                raise
        finally:
            service.remove_session(session_id)
            await manager.disconnect(session_id)
            service.audit.event(
                "session.closed",
                sessionId=session_id,
                clientId=client_id,
                transport="websocket",
            )

    @app.websocket("/ws/v2")
    async def websocket_protocol_v2(websocket: WebSocket):
        """The frozen protocol v2 endpoint (AP-SRV-040 K2).

        Deliberately separate from ``/ws/transcribe``: v1 admits a session
        from query parameters before the first message and sends a *server*
        ``hello``, while v2 admits nothing until the *client* ``hello`` has
        been validated. Mixing both into one route would need a protocol
        branch inside an already admitted session, which the frozen contract
        forbids. The legacy route stays untouched until AP-SRV-070.

        A v2 connection is deliberately not registered in the shared
        ``ConnectionManager``: everything a v2 client sees passes through the
        v2 projection, so no legacy payload can reach it.
        """
        await websocket.accept()
        client_id = normalized_client_id(
            websocket.query_params.get("clientId")
            or websocket.headers.get("x-voicestt-client-id")
        )
        connection = ProtocolV2Connection(service, client_id=client_id)
        loop = asyncio.get_running_loop()
        outbound = asyncio.Queue()

        def sink(payload):
            try:
                loop.call_soon_threadsafe(outbound.put_nowait, payload)
            except RuntimeError:
                # The loop is gone; the connection is being torn down anyway.
                pass

        connection.set_sink(sink)

        async def writer():
            while True:
                payload = await outbound.get()
                if payload is None:
                    return
                try:
                    await websocket.send_text(
                        json.dumps(payload, separators=(",", ":"))
                    )
                except Exception:
                    return

        writer_task = asyncio.create_task(writer())
        try:
            while True:
                if connection.accepted:
                    message = await websocket.receive()
                else:
                    try:
                        message = await asyncio.wait_for(
                            websocket.receive(),
                            timeout=connection.handshake_timeout,
                        )
                    except asyncio.TimeoutError:
                        connection.request_close(
                            protocol_v2_schema.CLOSE_HANDSHAKE_TIMEOUT
                        )
                        break
                if message.get("type") == "websocket.disconnect":
                    break
                if message.get("bytes") is not None:
                    connection.handle_binary(message["bytes"])
                elif message.get("text") is not None:
                    connection.handle_text(message["text"])
                if connection.closed:
                    break
        except WebSocketDisconnect:
            pass
        except RuntimeError as exc:
            if "disconnect" not in str(exc).lower():
                LOGGER.exception("v2-Verbindung ist unerwartet gescheitert")
                connection.request_close(
                    protocol_v2_schema.CLOSE_INTERNAL_ERROR
                )
        except Exception:
            LOGGER.exception("v2-Verbindung ist unerwartet gescheitert")
            connection.request_close(protocol_v2_schema.CLOSE_INTERNAL_ERROR)
        finally:
            close_code = connection.close_code
            connection.request_close(close_code or 1000)
            try:
                await asyncio.wait_for(writer_task, timeout=5.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                writer_task.cancel()
            session_id = (
                None if connection.session is None
                else connection.session.session_id
            )
            connection.close_session()
            if close_code is not None:
                try:
                    await websocket.close(code=close_code)
                except Exception:
                    pass
            if session_id is not None:
                service.audit.event(
                    "session.closed",
                    sessionId=session_id,
                    clientId=client_id,
                    transport="websocket_v2",
                )

    app.state.voicestt_service = service
    return app


def _env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


YAML_CONFIG_SECRET_KEYS = {"admin_api_key", "openai_api_key"}
YAML_CONFIG_DERIVED_KEYS = {"tuning_description"} | DERIVED_DATA_PATH_SETTINGS
YAML_CONFIG_TO_ARG_DEST = {
    "model_warmup": ("no_model_warmup", lambda value: not value),
    "openai_api_enabled": ("disable_openai_api", lambda value: not value),
    "performance_logging_enabled": ("performance_logging", bool),
    "performance_log_mirror_enabled": ("performance_log_mirror", bool),
    "system_event_logging_enabled": ("system_event_logging", bool),
    "transcription_logging_enabled": ("transcription_logging", bool),
    "realtime_transcription_use_syllable_boundaries": (
        "realtime_use_syllable_boundaries",
        bool,
    ),
    "request_logging_enabled": ("request_logging", bool),
    "model_idle_unload_enabled": ("model_idle_unload", bool),
    "model_memory_policy_enabled": ("model_memory_policy", bool),
    "transcription_engine_options": (
        "transcription_engine_options",
        lambda value: json.dumps(value, ensure_ascii=False) if value is not None else None,
    ),
    "realtime_transcription_engine_options": (
        "realtime_transcription_engine_options",
        lambda value: json.dumps(value, ensure_ascii=False) if value is not None else None,
    ),
    "openai_model_aliases": (
        "openai_model_aliases",
        lambda value: json.dumps(value, ensure_ascii=False) if value is not None else None,
    ),
    "vad_filter": ("no_vad_filter", lambda value: not value),
}


def load_yaml_config_defaults(path):
    """Load non-secret ServerSettings defaults from a versioned YAML file."""

    if not path:
        return {}
    config_path = Path(path).expanduser()
    if not config_path.is_file():
        raise SystemExit(f"Die YAML-Konfiguration wurde nicht gefunden: {config_path}")
    try:
        import yaml
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "PyYAML fehlt. Installiere die Serverabhängigkeiten erneut."
        ) from exc
    try:
        payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise SystemExit(f"Die YAML-Konfiguration ist ungültig: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit("Die YAML-Konfiguration muss ein Objekt enthalten.")
    version = payload.get("version", 1)
    if version != 1:
        raise SystemExit(f"Nicht unterstützte YAML-Konfigurationsversion: {version}")
    settings = payload.get("settings", payload)
    if not isinstance(settings, dict):
        raise SystemExit("Die YAML-Konfiguration muss ein settings-Objekt enthalten.")

    allowed = {item.name for item in fields(ServerSettings)}
    defaults = {}
    for raw_name, raw_value in settings.items():
        name = str(raw_name).strip().replace("-", "_")
        if name in {"version", "settings"}:
            continue
        if name in YAML_CONFIG_SECRET_KEYS:
            raise SystemExit(
                f"'{name}' darf nicht in der YAML-Konfiguration stehen. "
                "Verwende dafür ausschließlich die Env-Datei."
            )
        if name in YAML_CONFIG_DERIVED_KEYS:
            raise SystemExit(f"'{name}' wird automatisch abgeleitet und darf nicht gesetzt werden.")
        if name not in allowed:
            raise SystemExit(f"Unbekannter YAML-Konfigurationswert: {raw_name}")
        try:
            value = coerce_setting_value(name, raw_value)
        except (TypeError, ValueError) as exc:
            raise SystemExit(f"Ungültiger YAML-Wert für '{name}': {exc}") from exc
        if name == "device" and value != "cpu":
            raise SystemExit("In der YAML-Konfiguration ist ausschließlich device: cpu zulässig.")
        if name == "tuning_profile" and value not in TUNING_PROFILES:
            raise SystemExit(f"Unbekanntes Abstimmungsprofil in YAML: {value}")
        destination, transform = YAML_CONFIG_TO_ARG_DEST.get(
            name,
            (name, lambda item: item),
        )
        defaults[destination] = transform(value)
    return defaults


def parse_args(argv=None):
    config_parser = argparse.ArgumentParser(add_help=False)
    config_parser.add_argument(
        "--config",
        default=os.getenv("VOICESTT_CONFIG"),
    )
    config_args, _ = config_parser.parse_known_args(argv)
    yaml_defaults = load_yaml_config_defaults(config_args.config)

    parser = argparse.ArgumentParser(description="VoiceSTT FastAPI-Server für Browserstreaming")
    parser.add_argument(
        "--config",
        default=config_args.config,
        help="Versionierte YAML-Startkonfiguration. CLI-Parameter überschreiben deren Werte.",
    )
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8010)
    parser.add_argument(
        "--profile",
        "--tuning-profile",
        dest="tuning_profile",
        choices=sorted(TUNING_PROFILES),
        default="custom",
        help="Benanntes Abstimmungsprofil. Parakeet-Profile ändern Taktung, Stapel und VAD-Zeiten, nicht die Whisper-Beam-Suche.",
    )
    parser.add_argument("--model", default="small")
    parser.add_argument(
        "--realtime-model",
        default="Kroko-DE-Community-64-L-Streaming-001.data",
    )
    parser.add_argument("--language", default="de")
    parser.add_argument("--engine", "--transcription-engine", dest="transcription_engine", default="faster_whisper")
    parser.add_argument(
        "--realtime-engine",
        "--realtime-transcription-engine",
        dest="realtime_transcription_engine",
        default="kroko_onnx",
    )
    parser.add_argument("--engine-options", dest="transcription_engine_options")
    parser.add_argument("--realtime-engine-options", dest="realtime_transcription_engine_options")
    parser.add_argument("--download-root")
    parser.add_argument("--compute-type", default="int8")
    parser.add_argument("--device", default="cpu", choices=("cpu",))
    parser.add_argument("--beam-size", type=int)
    parser.add_argument("--beam-size-realtime", type=int)
    parser.add_argument("--batch-size", type=int)
    parser.add_argument("--realtime-batch-size", type=int)
    parser.add_argument("--no-vad-filter", action="store_true")
    parser.add_argument("--normalize-audio", action="store_true")
    parser.add_argument("--realtime-callback", choices=("update", "stabilized"), default="update")
    parser.add_argument("--min-length-of-recording", type=float)
    parser.add_argument("--min-gap-between-recordings", type=float, default=0.0)
    parser.add_argument("--post-speech-silence-duration", type=float)
    parser.add_argument("--silero-sensitivity", type=float, default=0.05)
    parser.add_argument("--webrtc-sensitivity", type=int, default=3)
    parser.add_argument("--realtime-processing-pause", type=float)
    parser.add_argument("--realtime-use-syllable-boundaries", action="store_true")
    parser.add_argument("--realtime-boundary-detector-sensitivity", type=float, default=0.6)
    parser.add_argument("--realtime-boundary-followup-delays", default="0.05,0.2")
    parser.add_argument("--early-transcription-on-silence", type=float)
    parser.add_argument("--initial-prompt")
    parser.add_argument("--initial-prompt-realtime")
    parser.add_argument("--wakeword-backend", default="")
    parser.add_argument("--openwakeword-model-paths")
    parser.add_argument("--openwakeword-inference-framework", default="onnx")
    parser.add_argument("--wake-words", default="")
    parser.add_argument("--wake-words-sensitivity", type=float, default=0.5)
    parser.add_argument("--wake-word-activation-delay", type=float, default=0.0)
    parser.add_argument("--wake-word-timeout", type=float, default=5.0)
    parser.add_argument("--wake-word-buffer-duration", type=float, default=0.1)
    parser.add_argument("--wake-word-followup-window", type=float, default=0.0)
    parser.add_argument("--use-main-model-for-realtime", action="store_true")
    parser.add_argument("--audio-queue-size", type=int, default=128)
    parser.add_argument("--max-audio-packet-bytes", type=int, default=512 * 1024)
    parser.add_argument("--max-sessions", type=int, default=4)
    parser.add_argument("--max-active-speakers", type=int, default=4)
    parser.add_argument("--max-audio-queue-seconds-per-session", type=float, default=30.0)
    parser.add_argument("--pre-recording-buffer-duration", type=float, default=0.75)
    parser.add_argument("--max-realtime-queue-age-ms", type=int, default=1500)
    parser.add_argument("--max-final-queue-depth-per-session", type=int, default=8)
    parser.add_argument("--max-global-inference-queue-depth", type=int, default=64)
    parser.add_argument("--realtime-degradation-threshold-ms", type=int, default=1500)
    parser.add_argument("--realtime-min-audio-seconds", type=float, default=0.25)
    parser.add_argument("--realtime-max-audio-seconds", type=float, default=20.0)
    parser.add_argument("--vad-energy-threshold", type=float, default=250.0)
    parser.add_argument("--no-model-warmup", action="store_true")
    parser.add_argument(
        "--model-idle-unload",
        action=argparse.BooleanOptionalAction,
        default=_env_bool("VOICESTT_MODEL_IDLE_UNLOAD", True),
        help="Transkriptions-Engines nach der konfigurierten Zeit ohne Transkriptionsaktivität entladen.",
    )
    parser.add_argument(
        "--model-idle-timeout-seconds",
        type=float,
        default=float(os.getenv("VOICESTT_MODEL_IDLE_TIMEOUT_SECONDS", "3600")),
    )
    parser.add_argument(
        "--model-memory-policy",
        action=argparse.BooleanOptionalAction,
        default=_env_bool("VOICESTT_MODEL_MEMORY_POLICY", True),
    )
    parser.add_argument(
        "--allow-two-medium-models",
        action=argparse.BooleanOptionalAction,
        default=_env_bool("VOICESTT_ALLOW_TWO_MEDIUM_MODELS", True),
    )
    parser.add_argument("--log-level", default="INFO")
    parser.add_argument("--disable-openai-api", action="store_true")
    parser.add_argument("--openai-api-key", default=None)
    parser.add_argument("--admin-api-key", default=os.getenv("VOICESTT_ADMIN_API_KEY"))
    parser.add_argument(
        "--openai-model-aliases",
        default='{"whisper-1":"final","fast":"realtime"}',
    )
    parser.add_argument("--openai-max-file-bytes", type=int, default=25 * 1024 * 1024)
    parser.add_argument(
        "--request-logging",
        action=argparse.BooleanOptionalAction,
        default=_env_bool("VOICESTT_REQUEST_LOGGING", True),
    )
    parser.add_argument(
        "--request-log-stdout",
        action=argparse.BooleanOptionalAction,
        default=_env_bool("VOICESTT_REQUEST_LOG_STDOUT", True),
    )
    parser.add_argument(
        "--data-root",
        dest="data_root_path",
        default=os.getenv("VOICESTT_DATA_ROOT"),
        help=(
            "Einziger Stammordner für erzeugte Laufzeitdaten. Logs, Audio, "
            "Event-Datenbank und runtime.json werden intern darunter abgelegt."
        ),
    )
    parser.add_argument(
        "--request-log-transcripts",
        action=argparse.BooleanOptionalAction,
        default=_env_bool("VOICESTT_REQUEST_LOG_TRANSCRIPTS", True),
    )
    parser.add_argument(
        "--transcript-mode",
        dest="transcript_log_mode",
        choices=("none", "final", "full"),
        default=os.getenv("VOICESTT_TRANSCRIPT_MODE"),
    )
    parser.add_argument("--request-log-max-bytes", type=int, default=10 * 1024 * 1024)
    parser.add_argument("--request-log-backup-count", type=int, default=12)
    parser.add_argument("--request-log-retention-days", type=int, default=0)
    parser.add_argument(
        "--performance-logging",
        action=argparse.BooleanOptionalAction,
        default=_env_bool("VOICESTT_PERFORMANCE_LOGGING", True),
    )
    parser.add_argument(
        "--performance-log-stdout",
        action=argparse.BooleanOptionalAction,
        default=_env_bool("VOICESTT_PERFORMANCE_LOG_STDOUT", True),
    )
    parser.add_argument(
        "--performance-log-mirror",
        action=argparse.BooleanOptionalAction,
        default=_env_bool("VOICESTT_PERFORMANCE_LOG_MIRROR", True),
    )
    parser.add_argument("--performance-log-max-bytes", type=int, default=10 * 1024 * 1024)
    parser.add_argument("--performance-log-backup-count", type=int, default=12)
    parser.add_argument("--performance-log-retention-days", type=int, default=0)
    parser.add_argument(
        "--transcription-logging",
        action=argparse.BooleanOptionalAction,
        default=_env_bool("VOICESTT_TRANSCRIPTION_LOGGING", True),
    )
    parser.add_argument(
        "--transcription-log-stdout",
        action=argparse.BooleanOptionalAction,
        default=_env_bool("VOICESTT_TRANSCRIPTION_LOG_STDOUT", False),
    )
    parser.add_argument(
        "--transcription-log-max-bytes",
        type=int,
        default=10 * 1024 * 1024,
    )
    parser.add_argument(
        "--transcription-log-backup-count",
        type=int,
        default=12,
    )
    parser.add_argument(
        "--transcription-log-retention-days",
        type=int,
        default=0,
    )
    parser.add_argument(
        "--system-event-logging",
        action=argparse.BooleanOptionalAction,
        default=_env_bool("VOICESTT_SYSTEM_EVENT_LOGGING", True),
    )
    parser.add_argument(
        "--system-event-log-stdout",
        action=argparse.BooleanOptionalAction,
        default=_env_bool("VOICESTT_SYSTEM_EVENT_LOG_STDOUT", False),
    )
    parser.add_argument(
        "--system-event-log-max-bytes",
        type=int,
        default=10 * 1024 * 1024,
    )
    parser.add_argument(
        "--system-event-log-backup-count",
        type=int,
        default=12,
    )
    parser.add_argument(
        "--system-event-log-retention-days",
        type=int,
        default=0,
    )
    parser.add_argument(
        "--log-calendar-timezone",
        default=os.getenv("VOICESTT_LOG_CALENDAR_TIMEZONE", "Europe/Berlin"),
    )
    parser.add_argument(
        "--realtime-log-detail",
        choices=("off", "summary", "events"),
        default=os.getenv("VOICESTT_REALTIME_LOG_DETAIL", "events"),
    )
    parser.add_argument(
        "--event-store",
        dest="event_store_enabled",
        action=argparse.BooleanOptionalAction,
        default=_env_bool("VOICESTT_EVENT_STORE", True),
    )
    parser.add_argument("--event-log-queue-size", type=int, default=10000)
    parser.add_argument(
        "--log-live",
        dest="log_live_enabled",
        action=argparse.BooleanOptionalAction,
        default=_env_bool("VOICESTT_LOG_LIVE", True),
    )
    parser.add_argument(
        "--save-audio-files",
        action=argparse.BooleanOptionalAction,
        default=_env_bool("VOICESTT_SAVE_AUDIO_FILES", False),
    )
    parser.set_defaults(**yaml_defaults)
    return parser.parse_args(argv)


def _tuning_defaults(profile):
    defaults = dict(BASE_TUNING_DEFAULTS)
    defaults.update(TUNING_PROFILES[profile]["settings"])
    return defaults


def _value_or_default(args, defaults, name):
    value = getattr(args, name)
    return defaults[name] if value is None else value


def parse_float_tuple(value, flag_name):
    if value is None:
        return ()
    if isinstance(value, (tuple, list)):
        return tuple(float(item) for item in value)

    parts = [part.strip() for part in str(value).split(",")]
    try:
        return tuple(float(part) for part in parts if part)
    except ValueError as exc:
        raise SystemExit(f"{flag_name} muss eine kommagetrennte Zahlenliste sein") from exc


def settings_from_args(args):
    tuning_profile = args.tuning_profile
    defaults = _tuning_defaults(tuning_profile)
    return ServerSettings(
        host=args.host,
        port=args.port,
        tuning_profile=tuning_profile,
        tuning_description=TUNING_PROFILES[tuning_profile]["description"],
        model=args.model,
        realtime_model=args.realtime_model,
        language=args.language,
        transcription_engine=normalize_engine_name(args.transcription_engine),
        realtime_transcription_engine=normalize_engine_name(args.realtime_transcription_engine),
        transcription_engine_options=parse_json_object(args.transcription_engine_options, "--engine-options"),
        realtime_transcription_engine_options=parse_json_object(
            args.realtime_transcription_engine_options,
            "--realtime-engine-options",
        ),
        download_root=args.download_root,
        compute_type=args.compute_type,
        device=args.device,
        beam_size=_value_or_default(args, defaults, "beam_size"),
        beam_size_realtime=_value_or_default(args, defaults, "beam_size_realtime"),
        batch_size=_value_or_default(args, defaults, "batch_size"),
        realtime_batch_size=_value_or_default(args, defaults, "realtime_batch_size"),
        vad_filter=not args.no_vad_filter,
        normalize_audio=args.normalize_audio,
        realtime_callback=args.realtime_callback,
        min_length_of_recording=_value_or_default(args, defaults, "min_length_of_recording"),
        min_gap_between_recordings=args.min_gap_between_recordings,
        post_speech_silence_duration=_value_or_default(args, defaults, "post_speech_silence_duration"),
        silero_sensitivity=args.silero_sensitivity,
        webrtc_sensitivity=args.webrtc_sensitivity,
        realtime_processing_pause=_value_or_default(args, defaults, "realtime_processing_pause"),
        realtime_transcription_use_syllable_boundaries=args.realtime_use_syllable_boundaries,
        realtime_boundary_detector_sensitivity=args.realtime_boundary_detector_sensitivity,
        realtime_boundary_followup_delays=parse_float_tuple(
            args.realtime_boundary_followup_delays,
            "--realtime-boundary-followup-delays",
        ),
        early_transcription_on_silence=_value_or_default(args, defaults, "early_transcription_on_silence"),
        initial_prompt=args.initial_prompt,
        initial_prompt_realtime=args.initial_prompt_realtime,
        wakeword_backend=(
            args.wakeword_backend
            or ("openwakeword" if args.wake_words else "")
        ),
        openwakeword_model_paths=args.openwakeword_model_paths,
        openwakeword_inference_framework=args.openwakeword_inference_framework,
        wake_words=args.wake_words,
        wake_words_sensitivity=args.wake_words_sensitivity,
        wake_word_activation_delay=args.wake_word_activation_delay,
        wake_word_timeout=args.wake_word_timeout,
        wake_word_buffer_duration=args.wake_word_buffer_duration,
        wake_word_followup_window=args.wake_word_followup_window,
        use_main_model_for_realtime=args.use_main_model_for_realtime,
        audio_queue_size=args.audio_queue_size,
        max_audio_packet_bytes=args.max_audio_packet_bytes,
        max_sessions=args.max_sessions,
        max_active_speakers=args.max_active_speakers,
        max_audio_queue_seconds_per_session=args.max_audio_queue_seconds_per_session,
        pre_recording_buffer_duration=args.pre_recording_buffer_duration,
        max_realtime_queue_age_ms=args.max_realtime_queue_age_ms,
        max_final_queue_depth_per_session=args.max_final_queue_depth_per_session,
        max_global_inference_queue_depth=args.max_global_inference_queue_depth,
        realtime_degradation_threshold_ms=args.realtime_degradation_threshold_ms,
        realtime_min_audio_seconds=args.realtime_min_audio_seconds,
        realtime_max_audio_seconds=args.realtime_max_audio_seconds,
        vad_energy_threshold=args.vad_energy_threshold,
        model_warmup=not args.no_model_warmup,
        model_idle_unload_enabled=args.model_idle_unload,
        model_idle_timeout_seconds=args.model_idle_timeout_seconds,
        model_memory_policy_enabled=args.model_memory_policy,
        allow_two_medium_models=args.allow_two_medium_models,
        log_level=coerce_setting_value("log_level", args.log_level),
        openai_api_enabled=not args.disable_openai_api,
        openai_api_key=args.openai_api_key,
        admin_api_key=args.admin_api_key,
        openai_model_aliases=parse_json_object(args.openai_model_aliases, "--openai-model-aliases"),
        openai_max_file_bytes=args.openai_max_file_bytes,
        data_root_path=args.data_root_path,
        request_logging_enabled=args.request_logging,
        request_log_stdout=args.request_log_stdout,
        request_log_transcripts=args.request_log_transcripts,
        transcript_log_mode=(
            args.transcript_log_mode
            or ("final" if args.request_log_transcripts else "none")
        ),
        request_log_max_bytes=args.request_log_max_bytes,
        request_log_backup_count=args.request_log_backup_count,
        request_log_retention_days=args.request_log_retention_days,
        performance_logging_enabled=args.performance_logging,
        performance_log_mirror_enabled=args.performance_log_mirror,
        performance_log_stdout=args.performance_log_stdout,
        performance_log_max_bytes=args.performance_log_max_bytes,
        performance_log_backup_count=args.performance_log_backup_count,
        performance_log_retention_days=args.performance_log_retention_days,
        transcription_logging_enabled=args.transcription_logging,
        transcription_log_stdout=args.transcription_log_stdout,
        transcription_log_max_bytes=args.transcription_log_max_bytes,
        transcription_log_backup_count=args.transcription_log_backup_count,
        transcription_log_retention_days=args.transcription_log_retention_days,
        system_event_logging_enabled=args.system_event_logging,
        system_event_log_stdout=args.system_event_log_stdout,
        system_event_log_max_bytes=args.system_event_log_max_bytes,
        system_event_log_backup_count=args.system_event_log_backup_count,
        system_event_log_retention_days=args.system_event_log_retention_days,
        log_calendar_timezone=coerce_setting_value(
            "log_calendar_timezone",
            args.log_calendar_timezone,
        ),
        realtime_log_detail=coerce_setting_value(
            "realtime_log_detail",
            args.realtime_log_detail,
        ),
        event_store_enabled=args.event_store_enabled,
        event_log_queue_size=args.event_log_queue_size,
        log_live_enabled=args.log_live_enabled,
        save_audio_files=args.save_audio_files,
    )


def main(argv=None):
    args = parse_args(argv)
    settings = settings_from_args(args)
    logging.basicConfig(
        level=resolve_log_level(settings.log_level),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    apply_process_log_level(settings.log_level)

    try:
        import uvicorn
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "uvicorn fehlt. Installiere die Serverabhängigkeiten mit "
            "'python -m pip install -r api_fastapi_server/requirements.txt'."
        ) from exc

    uvicorn.run(
        create_app(settings),
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
