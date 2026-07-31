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
    "audio_log_dir",
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
    "request_log_path",
    "request_log_retention_days",
    "request_log_stdout",
    "request_log_transcripts",
    "request_logging_enabled",
    "performance_log_backup_count",
    "performance_log_max_bytes",
    "performance_log_path",
    "performance_log_retention_days",
    "performance_log_stdout",
    "performance_logging_enabled",
    "realtime_log_detail",
    "save_audio_files",
    "system_event_log_backup_count",
    "system_event_log_max_bytes",
    "system_event_log_path",
    "system_event_log_retention_days",
    "system_event_log_stdout",
    "system_event_logging_enabled",
    "transcription_log_backup_count",
    "transcription_log_max_bytes",
    "transcription_log_path",
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
    "runtime_config_path",
    "event_log_queue_size",
    "event_store_enabled",
    "event_store_path",
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
    "audio_log_dir",
    "download_root",
    "initial_prompt",
    "initial_prompt_realtime",
    "openwakeword_model_paths",
    "realtime_transcription_engine",
    "openai_api_key",
    "request_log_path",
    "performance_log_path",
    "system_event_log_path",
    "transcription_log_path",
    "event_store_path",
    "runtime_config_path",
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
    request_logging_enabled: bool = True
    request_log_stdout: bool = True
    request_log_path: Optional[str] = "logs/audit"
    request_log_transcripts: bool = True
    transcript_log_mode: Optional[str] = None
    request_log_max_bytes: int = 10 * 1024 * 1024
    request_log_backup_count: int = 12
    request_log_retention_days: int = 0
    performance_logging_enabled: bool = True
    performance_log_stdout: bool = True
    performance_log_path: Optional[str] = "logs/performance"
    performance_log_max_bytes: int = 10 * 1024 * 1024
    performance_log_backup_count: int = 12
    performance_log_retention_days: int = 0
    transcription_logging_enabled: bool = True
    transcription_log_stdout: bool = False
    transcription_log_path: Optional[str] = "logs/transcription"
    transcription_log_max_bytes: int = 10 * 1024 * 1024
    transcription_log_backup_count: int = 12
    transcription_log_retention_days: int = 0
    system_event_logging_enabled: bool = True
    system_event_log_stdout: bool = False
    system_event_log_path: Optional[str] = "logs/system"
    system_event_log_max_bytes: int = 10 * 1024 * 1024
    system_event_log_backup_count: int = 12
    system_event_log_retention_days: int = 0
    log_calendar_timezone: str = "Europe/Berlin"
    realtime_log_detail: str = "events"
    event_store_enabled: bool = True
    event_store_path: Optional[str] = "logs/voicestt-events.sqlite3"
    event_log_queue_size: int = 10000
    log_live_enabled: bool = True
    save_audio_files: bool = False
    audio_log_dir: str = "logs/audio"
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
    runtime_config_path: Optional[str] = None

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
    def __init__(self):
        self._lock = threading.Lock()
        self._segment_id = 1
        self._has_realtime = False

    def realtime(self):
        with self._lock:
            self._has_realtime = True
            return self._segment_id

    def final(self):
        with self._lock:
            segment_id = self._segment_id
            self._segment_id += 1
            self._has_realtime = False
            return segment_id

    def current(self):
        with self._lock:
            return self._segment_id

    def reset(self):
        with self._lock:
            self._segment_id += 1
            self._has_realtime = False
            return self._segment_id


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


@dataclass(frozen=True)
class QueueSubmitResult:
    accepted: bool
    reason: str = ""
    coalesced: bool = False


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
        return self.service.transcribe_for_recorder(
            self.session_id,
            self.kind,
            audio,
            language,
            use_prompt,
        )


class VoiceActivityDetector:
    def __init__(self, settings: ServerSettings):
        self.settings = settings
        self.vad = None
        try:
            import webrtcvad

            self.vad = webrtcvad.Vad()
            self.vad.set_mode(int(settings.webrtc_sensitivity))
        except Exception:
            self.vad = None

    def is_speech(self, samples):
        if samples is None or samples.size == 0:
            return False

        if self.vad is not None and samples.size >= 160:
            try:
                frame_samples = 320
                usable = samples.size - (samples.size % frame_samples)
                speech_frames = 0
                checked_frames = 0
                for start in range(0, usable, frame_samples):
                    frame = samples[start:start + frame_samples]
                    checked_frames += 1
                    if self.vad.is_speech(frame.astype(np.int16).tobytes(), SERVER_SAMPLE_RATE):
                        speech_frames += 1
                if checked_frames:
                    return speech_frames / checked_frames >= 0.25
            except Exception:
                LOGGER.debug("WebRTC-VAD fehlgeschlagen; Energie-VAD wird verwendet", exc_info=True)

        rms = float(np.sqrt(np.mean(samples.astype(np.float32) ** 2)))
        return rms >= float(self.settings.vad_energy_threshold)


class RealtimeSession:
    def __init__(self, service, session_id):
        self.service = service
        self.settings = replace(service.settings)
        self.session_id = session_id
        self.segment_state = SegmentState()
        self.timeline = SegmentTimelineTracker(self.settings)
        self.vad = VoiceActivityDetector(self.settings)
        self.lock = threading.RLock()
        self.streaming = False
        self.recording = False
        self.status = "idle"
        self.generation = 0
        self.active_segment_id = None
        self.latest_realtime_sequence = 0
        self.last_realtime_submit_at = 0.0
        self.last_speech_at = 0.0
        self.recording_started_at = 0.0
        self.recording_frames: List[Any] = []
        self.recording_sample_count = 0
        self.prebuffer = collections.deque()
        self.prebuffer_sample_count = 0
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
        self.final_queue_full = 0
        self.queue_delay = {"realtime": RunningStats(), "final": RunningStats()}
        self.inference_duration = {"realtime": RunningStats(), "final": RunningStats()}
        self.total_latency = {"realtime": RunningStats(), "final": RunningStats()}

    def start_streaming(self):
        with self.lock:
            self.streaming = True
            self.status = (
                "wakeword_wait"
                if self.settings.wake_word_enabled()
                and self.settings.wake_word_activation_delay <= 0
                else "listening"
            )
        self.publish_status(self.status)

    def stop_streaming(self):
        jobs = []
        with self.lock:
            self.streaming = False
            final_job = self._finish_recording_locked("stop")
            if final_job is not None:
                jobs.append(final_job)
            self.status = "idle"
        for job in jobs:
            self.service.submit_inference_job(job)
        self.service.deactivate_speaker(self.session_id)
        self.publish_status("idle")

    def close(self):
        with self.lock:
            self.generation += 1
            self.streaming = False
            self.recording = False
            self.recording_frames = []
            self.recording_sample_count = 0
            self.prebuffer.clear()
            self.prebuffer_sample_count = 0
            self.timeline.reset()
        self.service.cancel_scheduler_session(self.session_id)
        self.service.deactivate_speaker(self.session_id)

    def clear(self):
        with self.lock:
            self.generation += 1
            self.recording = False
            self.recording_frames = []
            self.recording_sample_count = 0
            self.prebuffer.clear()
            self.prebuffer_sample_count = 0
            self.active_segment_id = None
            self.latest_realtime_sequence = 0
            next_segment = self.segment_state.reset()
            self.timeline.reset()
            self.status = self._waiting_state_locked()
        self.service.cancel_scheduler_session(self.session_id)
        self.service.deactivate_speaker(self.session_id)
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
        now = time.monotonic()
        jobs = []
        warnings = []

        with self.lock:
            self.streaming = True
            speech = self.vad.is_speech(samples)

            if not self.recording:
                if not speech:
                    self._append_prebuffer_locked(samples)
                    return True, None
                if not self.service.try_activate_speaker(self.session_id):
                    self.rejected_audio_chunks += 1
                    return False, "Die maximale Anzahl gleichzeitig sprechender Personen ist erreicht; der Audioabschnitt wurde ignoriert."
                self._start_recording_locked(now)
                self.recording_frames.append(samples.copy())
                self.recording_sample_count += int(samples.size)
                self.last_speech_at = now
                self.status = "recording"
                warnings.append(None)
            else:
                self.recording_frames.append(samples.copy())
                self.recording_sample_count += int(samples.size)
                if speech:
                    self.last_speech_at = now

            if self.recording:
                realtime_job = self._maybe_create_realtime_job_locked(now)
                if realtime_job is not None:
                    jobs.append(realtime_job)

                recording_seconds = self.recording_sample_count / float(SERVER_SAMPLE_RATE)
                silence_seconds = now - self.last_speech_at if self.last_speech_at else 0.0
                if (
                    recording_seconds >= self.settings.min_length_of_recording
                    and silence_seconds >= self.settings.post_speech_silence_duration
                ):
                    final_job = self._finish_recording_locked("silence")
                    if final_job is not None:
                        jobs.append(final_job)
                elif recording_seconds >= self.settings.max_audio_queue_seconds_per_session:
                    final_job = self._finish_recording_locked("max_duration")
                    if final_job is not None:
                        jobs.append(final_job)
                    warnings.append("Maximaler Audiopuffer der Sitzung erreicht; das aktuelle Segment wurde finalisiert.")

        for job in jobs:
            self.service.submit_inference_job(job)
        for warning in warnings:
            if warning:
                self.service.manager.publish_session(
                    self.session_id,
                    {"type": "warning", "sessionId": self.session_id, "message": warning},
                )
        self.publish_status(self.status)
        return True, None

    def handle_inference_result(self, result: InferenceResult):
        with self.lock:
            if result.generation != self.generation:
                if result.kind == "realtime":
                    self.stale_realtime_discarded += 1
                return

            if result.kind == "realtime":
                if (
                    not self.recording
                    or result.segment_id != self.active_segment_id
                    or result.sequence < self.latest_realtime_sequence
                ):
                    self.stale_realtime_discarded += 1
                    return
                self.realtime_completed += 1
            else:
                self.final_completed += 1

            self.queue_delay[result.kind].record(result.queue_delay)
            self.inference_duration[result.kind].record(result.inference_duration)
            self.total_latency[result.kind].record(result.total_latency)

        if result.error:
            self.service.manager.publish_session(
                self.session_id,
                {
                    "type": "error",
                    "sessionId": self.session_id,
                    "message": result.error,
                    "where": result.kind,
                    "requestId": result.request_id,
                },
            )
            return

        if not result.text:
            return

        event_timestamp = time.time()
        event = {
            "type": result.kind,
            "sessionId": self.session_id,
            "segmentId": result.segment_id,
            "text": result.text,
            "timestamp": event_timestamp,
            "timestampIso": timestamp_iso(event_timestamp),
            "requestId": result.request_id,
            "queueDelayMs": result.queue_delay * 1000.0,
            "inferenceMs": result.inference_duration * 1000.0,
            "latencyMs": result.total_latency * 1000.0,
        }
        segment = self.timeline.snapshot(result.segment_id)
        if segment is not None:
            event["segment"] = segment
            event.update(segment_text_fields(segment))
        self.service.manager.publish_session(self.session_id, event)
        if result.kind == "final":
            self.publish_status("listening" if self.streaming else "idle")

    def on_job_dropped(self, job: InferenceJob, reason: str):
        with self.lock:
            if reason == "coalesced" and job.kind == "realtime":
                self.coalesced_realtime += 1
            elif reason == "stale" and job.kind == "realtime":
                self.stale_realtime_discarded += 1
            elif reason == "cancelled":
                self.cancelled_jobs += 1

    def on_submit_result(self, job: InferenceJob, result: QueueSubmitResult):
        with self.lock:
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
                if "final queue" in result.reason:
                    self.final_queue_full += 1

        message = (
            "Die Realtime-Transkription ist überlastet; das Zwischenergebnis wurde verworfen."
            if job.kind == "realtime"
            else f"Finale Transkription wurde abgelehnt: {result.reason}"
        )
        self.service.manager.publish_session(
            self.session_id,
            {
                "type": "warning" if job.kind == "realtime" else "error",
                "sessionId": self.session_id,
                "message": message,
                "where": "scheduler",
            },
        )

    def publish_status(self, state=None):
        with self.lock:
            state = state or self.status
            queue_depth = self.recording_sample_count / float(SERVER_SAMPLE_RATE)
            message = {
                "type": "status",
                "sessionId": self.session_id,
                "state": state,
                "activeClientId": self.session_id if self.streaming else None,
                "queueDepth": round(queue_depth, 3),
                "droppedChunks": self.dropped_audio_chunks,
                "coalescedRealtime": self.coalesced_realtime,
                "staleRealtimeDiscarded": self.stale_realtime_discarded,
                "activeSessions": self.service.session_count(),
                "activeSpeakers": self.service.active_speaker_count(),
                "wakeWordEnabled": self.settings.wake_word_enabled(),
            }
        self.service.manager.publish_session(self.session_id, message)

    def snapshot(self):
        with self.lock:
            return {
                "sessionId": self.session_id,
                "streaming": self.streaming,
                "recording": self.recording,
                "state": self.status,
                "currentSegmentId": self.segment_state.current(),
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
                "finalQueueFull": self.final_queue_full,
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

    def _start_recording_locked(self, now):
        self.recording = True
        self.active_segment_id = self.segment_state.realtime()
        self.recording_started_at = now
        self.last_speech_at = now
        self.last_realtime_submit_at = 0.0
        self.recording_frames = [frame.copy() for frame in self.prebuffer]
        self.recording_sample_count = sum(int(frame.size) for frame in self.recording_frames)
        self.timeline.mark_recording_started(
            self.active_segment_id,
            actual_preroll_seconds=self.prebuffer_sample_count / float(SERVER_SAMPLE_RATE),
            timestamp=time.time(),
        )
        self.prebuffer.clear()
        self.prebuffer_sample_count = 0

    def _finish_recording_locked(self, reason):
        if not self.recording and not self.recording_frames:
            return None
        audio = self._recording_audio_float32_locked()
        recording_seconds = audio.size / float(SERVER_SAMPLE_RATE) if audio is not None else 0.0
        segment_id = self.active_segment_id
        self.timeline.mark_recording_ended(
            reason,
            segment_id=segment_id,
            actual_duration_seconds=recording_seconds,
            timestamp=time.time(),
        )
        self.recording = False
        self.recording_frames = []
        self.recording_sample_count = 0
        self.active_segment_id = None
        self.last_realtime_submit_at = 0.0
        self.status = self._waiting_state_locked()
        self.service.deactivate_speaker(self.session_id)
        if audio is None or recording_seconds < self.settings.min_length_of_recording:
            return None
        segment_id = self.segment_state.final()
        return InferenceJob(
            request_id=uuid.uuid4().hex,
            session_id=self.session_id,
            kind="final",
            audio=audio,
            language=self.settings.language,
            use_prompt=True,
            segment_id=segment_id,
            sequence=0,
            generation=self.generation,
            created_at=time.monotonic(),
        )

    def _maybe_create_realtime_job_locked(self, now):
        pause = max(0.0, float(self.settings.realtime_processing_pause))
        if pause > 0 and now - self.last_realtime_submit_at < pause:
            return None
        if self.recording_sample_count < int(self.settings.realtime_min_audio_seconds * SERVER_SAMPLE_RATE):
            return None
        audio = self._recording_audio_float32_locked(max_seconds=self.settings.realtime_max_audio_seconds)
        if audio is None or audio.size == 0:
            return None
        self.latest_realtime_sequence += 1
        self.last_realtime_submit_at = now
        return InferenceJob(
            request_id=uuid.uuid4().hex,
            session_id=self.session_id,
            kind="realtime",
            audio=audio,
            language=self.settings.language,
            use_prompt=True,
            segment_id=self.active_segment_id or self.segment_state.realtime(),
            sequence=self.latest_realtime_sequence,
            generation=self.generation,
            created_at=time.monotonic(),
            deadline_at=time.monotonic() + (self.settings.max_realtime_queue_age_ms / 1000.0),
        )

    def _append_prebuffer_locked(self, samples):
        if samples is None or samples.size == 0:
            return
        self.prebuffer.append(samples.copy())
        self.prebuffer_sample_count += int(samples.size)
        max_samples = int(self.settings.pre_recording_buffer_duration * SERVER_SAMPLE_RATE)
        while max_samples >= 0 and self.prebuffer_sample_count > max_samples and self.prebuffer:
            dropped = self.prebuffer.popleft()
            self.prebuffer_sample_count -= int(dropped.size)

    def _recording_audio_float32_locked(self, max_seconds=None):
        if not self.recording_frames:
            return None
        frames = self.recording_frames
        if max_seconds is not None and max_seconds > 0:
            max_samples = int(max_seconds * SERVER_SAMPLE_RATE)
            total = 0
            selected = []
            for frame in reversed(frames):
                selected.append(frame)
                total += int(frame.size)
                if total >= max_samples:
                    break
            frames = list(reversed(selected))
        audio_int16 = np.concatenate(frames).astype(np.int16)
        if max_seconds is not None and max_seconds > 0:
            max_samples = int(max_seconds * SERVER_SAMPLE_RATE)
            if audio_int16.size > max_samples:
                audio_int16 = audio_int16[-max_samples:]
        return audio_int16.astype(np.float32) / INT16_MAX_ABS_VALUE

    def _waiting_state_locked(self, streaming=None):
        if streaming is None:
            streaming = self.streaming
        if not streaming:
            return "idle"
        if self.settings.wake_word_enabled():
            return "wakeword_wait"
        return "listening"


class RecorderBackedRealtimeSession:
    def __init__(
        self,
        service,
        session_id,
        client_id=None,
        settings=None,
        session_config=None,
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
        self.session_id = session_id
        self.client_id = normalized_client_id(client_id)
        self.segment_state = SegmentState()
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
        self._performance_first_text_segments = set()
        self._realtime_event_stats = {}
        self._recorder_wake_word_timeout_before_followup = None
        self._recorder_start_recording_before_followup = None
        self._recorder_stop_recording_before_followup = None
        self.queue_delay = {"realtime": RunningStats(), "final": RunningStats()}
        self.inference_duration = {"realtime": RunningStats(), "final": RunningStats()}
        self.total_latency = {"realtime": RunningStats(), "final": RunningStats()}
        self.recorder = self._create_recorder()
        self.text_thread = threading.Thread(
            target=self._text_worker,
            name=f"VoiceSTTSessionText-{session_id}",
            daemon=True,
        )
        self.text_thread.start()

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
            self.streaming = False
            self.status = "idle"
        try:
            self.recorder.flush_buffered_audio()
            self._trim_recorded_audio_queue()
        except Exception:
            LOGGER.debug("Gepuffertes Audio für %s konnte nicht geleert werden", self.session_id, exc_info=True)
        finally:
            self.service.deactivate_speaker(self.session_id)
        self.publish_status("idle")

    def close(self):
        with self.lock:
            cancelled_generation = self.generation
            cancelled_segment = self.segment_state.current()
            should_cancel = self.status in {"recording", "transcribing"}
            self.generation += 1
            self.streaming = False
            self.status = "closed"
            self.timeline.reset()
            self._performance_first_text_segments.clear()
            self._realtime_event_stats.clear()
            self._wakeword_voice_window = False
            self._wakeword_followup_generation += 1
            self._clear_recorder_followup_gate_locked()
        if should_cancel:
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
            self.status = self._waiting_state_locked()
        if should_cancel:
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
        with self.lock:
            state = state or self.status
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
            with self.lock:
                text_generation = self.generation
            try:
                text = self.recorder.text()
            except Exception as exc:
                if getattr(self.recorder, "is_shut_down", False):
                    break
                LOGGER.exception("Textschleife des Sitzungs-Recorders fehlgeschlagen")
                segment_id = self.segment_state.current()
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
            text = (text or "").strip()
            if not text:
                continue
            self._publish_final_text(text, text_generation)

    def _publish_final_text(self, text, text_generation):
        with self.lock:
            if text_generation != self.generation:
                return False
            segment_id = self.segment_state.final()
            streaming = self.streaming
            segment = self._timeline_snapshot(segment_id)
        timestamp = time.time()
        payload = {
            "type": "final",
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
            "final_transcript",
            timestamp=timestamp,
            segment_id=segment_id,
            segment=segment,
            text=text,
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
            language=self.settings.language,
            engine=self.settings.transcription_engine,
            model=self.settings.model,
            audioDurationMs=(
                round(float(segment.get("durationSeconds")) * 1000.0, 3)
                if segment and segment.get("durationSeconds") is not None
                else None
            ),
        )
        self.publish_status(self._waiting_state_locked(streaming))
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
        with self.lock:
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
                self.reject_current_recording = False
                self.recording_sample_count = 0
                self._force_finalize_in_progress = False
                self._wakeword_voice_window = False
                segment_id = self.segment_state.current()
                segment = self.timeline.mark_recording_started(segment_id)
        if segment is not None:
            self._publish_timeline_event(
                "recording_started",
                timestamp=segment.get("recordingStartedAt"),
                segment_id=segment_id,
                segment=segment,
                preRecordingBuffer=segment.get("preRecordingBuffer"),
            )
        self.publish_status("recording")

    def _on_recording_stop(self):
        self._trim_recorded_audio_queue()
        segment = None
        segment_id = None
        with self.lock:
            segment_id = self.segment_state.current()
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
        self._start_wakeword_followup_window()
        self.publish_status(self._waiting_state_locked())

    def _on_transcription_start(self, *_):
        segment_id = self.segment_state.current()
        with self.lock:
            rejected = self.reject_current_recording
        if not rejected:
            self._emit_structured_event(
                "transcription",
                "transcription.accepted",
                segment_id=segment_id,
            )
        self._publish_timeline_event(
            "transcription_started",
            segment_id=segment_id,
            segment=self._timeline_snapshot(segment_id),
        )
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
        with self.lock:
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

    def _on_wakeword_detected(self):
        with self.lock:
            self._wakeword_voice_window = True
            self._wakeword_followup_generation += 1
        event = self.timeline.mark_wakeword_detected()
        self._publish_timeline_event(
            "wakeword_detected",
            wakeWord=event.get("wakeWord"),
        )
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
        for key, value in fields.items():
            if value is not None:
                payload[key] = value
        self.service.manager.publish_session(self.session_id, payload)
        structured_events = {
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
                queue_obj.get_nowait()
                dropped += 1
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
        self._sessions: Dict[str, RealtimeSession] = {}
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
        self._log_access_tokens = {}
        self._log_access_lock = threading.RLock()
        self.ready_thread = None
        self.idle_thread = None

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
        }

    def create_log_access(self, session_id):
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
            "websocketPath": "/ws/logs",
            "historyPath": "/api/logs/events",
            "accessToken": token,
            "sessionId": session_id,
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
                "audio_log_dir",
                "log_calendar_timezone",
                "log_live_enabled",
                "realtime_log_detail",
                "transcript_log_mode",
                "request_log_backup_count",
                "request_log_max_bytes",
                "request_log_path",
                "request_log_retention_days",
                "request_log_stdout",
                "request_log_transcripts",
                "request_logging_enabled",
                "save_audio_files",
                "performance_log_backup_count",
                "performance_log_max_bytes",
                "performance_log_path",
                "performance_log_retention_days",
                "performance_log_stdout",
                "performance_logging_enabled",
                "system_event_log_backup_count",
                "system_event_log_max_bytes",
                "system_event_log_path",
                "system_event_log_retention_days",
                "system_event_log_stdout",
                "system_event_logging_enabled",
                "transcription_log_backup_count",
                "transcription_log_max_bytes",
                "transcription_log_path",
                "transcription_log_retention_days",
                "transcription_log_stdout",
                "transcription_logging_enabled",
            }
            if any(name in logging_names for name in applied):
                self.events.configure(self.settings)
                self.audit.configure(self.settings, configure_hub=False)
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
            "admin_api_key", "openai_api_key", "runtime_config_path",
            "device", "host", "port",
        }
        return self.config_store.save(self.settings, allowed)

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
        if self.session_count() or self.active_speaker_count():
            raise RuntimeError("Für einen Modellwechsel dürfen keine WebSocket-Sitzungen aktiv sein.")

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

    def transcribe_for_recorder(self, session_id, kind, audio, language, use_prompt):
        from VoiceSTT.transcription_engines import TranscriptionResult

        session = self.sessions.get(session_id)
        if session is None:
            return TranscriptionResult(text="")

        generation = getattr(session, "generation", 0)
        request_id = uuid.uuid4().hex
        holder = {
            "event": threading.Event(),
            "result": None,
            "error": None,
            "sessionId": session_id,
            "generation": generation,
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
            segment_id=session.segment_state.current(),
            sequence=0,
            generation=generation,
            created_at=time.monotonic(),
            deadline_at=(
                time.monotonic() + (self.settings.max_realtime_queue_age_ms / 1000.0)
                if kind == "realtime"
                else None
            ),
            client_id=getattr(session, "client_id", None),
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
            raise RuntimeError(holder["error"])

        result = holder["result"]
        if result is None:
            return TranscriptionResult(text="")
        if result.error:
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
            if hasattr(settings, name) and name not in {"admin_api_key", "openai_api_key"}:
                setattr(settings, name, coerce_setting_value(name, value))
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
        return JSONResponse({
            "ok": metrics["ok"],
            "ready": metrics["ready"],
            "activeSessions": metrics["activeSessions"],
            "activeSpeakers": metrics["activeSpeakers"],
            "rejectedSessions": metrics["rejectedSessions"],
            "scheduler": metrics["scheduler"],
            "models": metrics["models"],
            "startupErrors": metrics["startupErrors"],
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

    def admin_auth_error(request):
        configured_key = settings.admin_api_key or os.getenv("VOICESTT_ADMIN_API_KEY")
        supplied = request.headers.get("x-voicestt-admin-key")
        authorization = request.headers.get("authorization", "")
        if not supplied and authorization.startswith("Bearer "):
            supplied = authorization[7:]
        if configured_key:
            if supplied != configured_key:
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

    @app.get("/api/logging")
    async def get_logging_config(request: Request):
        auth_error = admin_auth_error(request)
        if auth_error is not None:
            return auth_error
        return JSONResponse({
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
            "eventStore": {
                "enabled": settings.event_store_enabled,
                "path": settings.event_store_path,
            },
        })

    @app.put("/api/logging")
    async def set_logging_config(payload: dict, request: Request):
        auth_error = admin_auth_error(request)
        if auth_error is not None:
            return auth_error
        mapping = {
            "enabled": "request_logging_enabled", "stdout": "request_log_stdout",
            "file": "request_log_path", "transcripts": "request_log_transcripts",
            "transcriptMode": "transcript_log_mode",
            "saveAudio": "save_audio_files", "audioDirectory": "audio_log_dir",
            "maxBytes": "request_log_max_bytes", "backupCount": "request_log_backup_count",
            "retentionDays": "request_log_retention_days",
            "performanceEnabled": "performance_logging_enabled",
            "performanceStdout": "performance_log_stdout",
            "performanceFile": "performance_log_path",
            "performanceMaxBytes": "performance_log_max_bytes",
            "performanceBackupCount": "performance_log_backup_count",
            "performanceRetentionDays": "performance_log_retention_days",
            "transcriptionEnabled": "transcription_logging_enabled",
            "transcriptionStdout": "transcription_log_stdout",
            "transcriptionDirectory": "transcription_log_path",
            "transcriptionMaxBytes": "transcription_log_max_bytes",
            "transcriptionBackupCount": "transcription_log_backup_count",
            "transcriptionRetentionDays": "transcription_log_retention_days",
            "systemEnabled": "system_event_logging_enabled",
            "systemStdout": "system_event_log_stdout",
            "systemDirectory": "system_event_log_path",
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
        if configured_key and supplied == configured_key:
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
        except (TypeError, ValueError) as exc:
            return JSONResponse({"error": str(exc)}, status_code=400)
        return JSONResponse({
            "object": "list",
            "data": events,
            "nextCursor": events[-1]["cursor"] if events else None,
            "latestCursor": service.events.latest_cursor(),
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
                "message": "Der Live-Logzugriff ist deaktiviert.",
            }))
            await websocket.close(code=1008)
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
            is_admin = bool(configured_key and token == configured_key)
            access = (
                None
                if is_admin
                else service.validate_log_access(token, requested_session_id)
            )
            if not is_admin and access is None:
                await websocket.send_text(json.dumps({
                    "type": "log.error",
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
            after_cursor = max(
                0,
                int(request_payload.get("afterCursor") or 0),
            )
            latest_cursor = service.events.latest_cursor()
            live_queue = asyncio.Queue(maxsize=1000)
            subscription_id = service.events.subscribe_async(
                asyncio.get_running_loop(),
                live_queue,
                channels=channels,
                session_id=session_id,
            )
            await websocket.send_text(json.dumps({
                "type": "log.hello",
                "schemaVersion": 1,
                "serverInstanceId": service.events.server_instance_id,
                "latestCursor": latest_cursor,
            }))
            await websocket.send_text(json.dumps({
                "type": "log.subscribed",
                "channels": sorted(channels),
                "sessionId": session_id,
                "afterCursor": after_cursor,
            }))
            replay_cursor = after_cursor
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
            last_sent_cursor = latest_cursor
            receive_task = asyncio.create_task(websocket.receive_text())
            event_task = None
            try:
                while True:
                    event_task = asyncio.create_task(live_queue.get())
                    done, _ = await asyncio.wait(
                        {receive_task, event_task},
                        timeout=30.0,
                        return_when=asyncio.FIRST_COMPLETED,
                    )
                    if not done:
                        event_task.cancel()
                        await asyncio.gather(
                            event_task,
                            return_exceptions=True,
                        )
                        event_task = None
                        await websocket.send_text(json.dumps({
                            "type": "log.keepalive",
                            "cursor": last_sent_cursor,
                        }))
                        continue
                    if receive_task in done:
                        command = json.loads(receive_task.result())
                        if (
                            isinstance(command, dict)
                            and command.get("type") == "ping"
                        ):
                            await websocket.send_text(json.dumps({
                                "type": "log.pong",
                                "cursor": last_sent_cursor,
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
                    if event_task not in done:
                        event_task.cancel()
                        await asyncio.gather(
                            event_task,
                            return_exceptions=True,
                        )
                        event_task = None
                        continue
                    event = event_task.result()
                    event_task = None
                    if event.get("_logControl") == "gap":
                        last_sent_cursor = max(
                            last_sent_cursor,
                            int(event.get("cursor") or 0),
                        )
                        await websocket.send_text(json.dumps({
                            "type": "log.gap",
                            "scope": event.get("scope"),
                            "sink": event.get("sink"),
                            "dropped": event["dropped"],
                            "droppedTotal": event.get("droppedTotal"),
                            "cursor": event.get("cursor"),
                        }))
                        continue
                    if int(event.get("cursor") or 0) <= latest_cursor:
                        continue
                    last_sent_cursor = int(
                        event.get("cursor") or last_sent_cursor
                    )
                    await websocket.send_text(json.dumps({
                        "type": "log.event",
                        "event": event,
                        "replay": False,
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
        except WebSocketDisconnect:
            pass
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            await websocket.send_text(json.dumps({
                "type": "log.error",
                "message": str(exc),
            }))
            await websocket.close(code=1008)
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
                setattr(candidate, name, coerce_setting_value(name, value))
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

    app.state.voicestt_service = service
    return app


def _env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


YAML_CONFIG_SECRET_KEYS = {"admin_api_key", "openai_api_key"}
YAML_CONFIG_DERIVED_KEYS = {"tuning_description"}
YAML_CONFIG_TO_ARG_DEST = {
    "model_warmup": ("no_model_warmup", lambda value: not value),
    "openai_api_enabled": ("disable_openai_api", lambda value: not value),
    "performance_logging_enabled": ("performance_logging", bool),
    "system_event_logging_enabled": ("system_event_logging", bool),
    "transcription_logging_enabled": ("transcription_logging", bool),
    "realtime_transcription_use_syllable_boundaries": (
        "realtime_use_syllable_boundaries",
        bool,
    ),
    "request_logging_enabled": ("request_logging", bool),
    "model_idle_unload_enabled": ("model_idle_unload", bool),
    "model_memory_policy_enabled": ("model_memory_policy", bool),
    "runtime_config_path": ("runtime_config_path", lambda value: value),
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
        "--request-log-path",
        default=os.getenv("VOICESTT_REQUEST_LOG_PATH", "logs/audit"),
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
        "--performance-log-path",
        default=os.getenv(
            "VOICESTT_PERFORMANCE_LOG_PATH",
            "logs/performance",
        ),
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
        "--transcription-log-path",
        default=os.getenv(
            "VOICESTT_TRANSCRIPTION_LOG_PATH",
            "logs/transcription",
        ),
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
        "--system-event-log-path",
        default=os.getenv("VOICESTT_SYSTEM_EVENT_LOG_PATH", "logs/system"),
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
    parser.add_argument(
        "--event-store-path",
        default=os.getenv(
            "VOICESTT_EVENT_STORE_PATH",
            "logs/voicestt-events.sqlite3",
        ),
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
    parser.add_argument(
        "--audio-log-dir",
        default=os.getenv("VOICESTT_AUDIO_LOG_DIR", "logs/audio"),
    )
    parser.add_argument(
        "--runtime-config",
        dest="runtime_config_path",
        default=os.getenv("VOICESTT_RUNTIME_CONFIG"),
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
        request_logging_enabled=args.request_logging,
        request_log_stdout=args.request_log_stdout,
        request_log_path=args.request_log_path,
        request_log_transcripts=args.request_log_transcripts,
        transcript_log_mode=(
            args.transcript_log_mode
            or ("final" if args.request_log_transcripts else "none")
        ),
        request_log_max_bytes=args.request_log_max_bytes,
        request_log_backup_count=args.request_log_backup_count,
        request_log_retention_days=args.request_log_retention_days,
        performance_logging_enabled=args.performance_logging,
        performance_log_stdout=args.performance_log_stdout,
        performance_log_path=args.performance_log_path,
        performance_log_max_bytes=args.performance_log_max_bytes,
        performance_log_backup_count=args.performance_log_backup_count,
        performance_log_retention_days=args.performance_log_retention_days,
        transcription_logging_enabled=args.transcription_logging,
        transcription_log_stdout=args.transcription_log_stdout,
        transcription_log_path=args.transcription_log_path,
        transcription_log_max_bytes=args.transcription_log_max_bytes,
        transcription_log_backup_count=args.transcription_log_backup_count,
        transcription_log_retention_days=args.transcription_log_retention_days,
        system_event_logging_enabled=args.system_event_logging,
        system_event_log_stdout=args.system_event_log_stdout,
        system_event_log_path=args.system_event_log_path,
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
        event_store_path=args.event_store_path,
        event_log_queue_size=args.event_log_queue_size,
        log_live_enabled=args.log_live_enabled,
        save_audio_files=args.save_audio_files,
        audio_log_dir=args.audio_log_dir,
        runtime_config_path=args.runtime_config_path,
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
