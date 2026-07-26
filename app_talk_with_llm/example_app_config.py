"""
Configuration helpers for the desktop example app.
"""

from dataclasses import dataclass
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from dotenv import dotenv_values
from logging.handlers import RotatingFileHandler


APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parent
PROJECT_CONFIG_PATH = PROJECT_ROOT / "config.yaml"
SECRETS_ENV_PATH = PROJECT_ROOT / ".env"


@dataclass(frozen=True)
class BackendConfig:
    name: str
    model: str
    options: Dict[str, Any]


@dataclass(frozen=True)
class ExampleAppConfig:
    app_dir: Path
    project_root: Path
    logs_dir: Path
    max_history_messages: int
    return_to_wakewords_after_silence: float
    start_with_wakeword: bool
    start_engine: str
    edge_voice_string: str
    final_backend: BackendConfig
    realtime_backend: BackendConfig
    download_root: Optional[str]
    device: str
    compute_type: str
    input_device_index: Optional[int]
    gpu_device_index: int
    use_microphone: bool
    spinner: bool
    batch_size: int
    realtime_batch_size: int
    beam_size: int
    beam_size_realtime: int
    initial_prompt: Optional[str]
    initial_prompt_realtime: Optional[str]
    suppress_tokens: Optional[List[int]]
    ensure_sentence_starting_uppercase: bool
    ensure_sentence_ends_with_period: bool
    print_transcription_time: bool
    early_transcription_on_silence: int
    no_log_file: bool
    log_level: int
    use_extended_logging: bool
    faster_whisper_vad_filter: bool
    normalize_audio: bool
    start_callback_in_new_thread: bool
    allowed_latency_limit: int
    sample_rate: int
    buffer_size: int
    handle_buffer_overflow: bool
    debug_mode: bool
    wakeword_backend: str
    openwakeword_model_paths: Optional[str]
    openwakeword_inference_framework: str
    wake_words: str
    wake_words_sensitivity: float
    wake_word_activation_delay: float
    wake_word_timeout: float
    wake_word_buffer_duration: float
    silero_sensitivity: float
    silero_use_onnx: Optional[bool]
    silero_deactivity_detection: bool
    silero_backend: str
    silero_onnx_model_path: Optional[str]
    silero_onnx_threads: int
    deactivity_silence_confirmation_duration: float
    webrtc_sensitivity: int
    warmup_vad: bool
    post_speech_silence_duration: float
    min_length_of_recording: float
    min_gap_between_recordings: float
    pre_recording_buffer_duration: float
    pre_recording_buffer_trim_config: Optional[Dict[str, Any]]
    use_main_model_for_realtime: bool
    realtime_processing_pause: float
    init_realtime_after_seconds: float
    enable_realtime_transcription: bool
    realtime_callback: str
    realtime_transcription_use_syllable_boundaries: bool
    realtime_boundary_detector_sensitivity: float
    realtime_boundary_followup_delays: Optional[Tuple[float, ...]]
    clear_text_delay_ms: int
    tts_minimum_sentence_length: int
    tts_buffer_threshold_seconds: float
    tts_log_characters: bool
    edge_rate: int
    edge_pitch: int
    language: str
    chat_model: str
    voice_system: str
    system_prompt: str
    user_font_size: int
    assistant_font_size: int
    user_color_rgb: Tuple[int, int, int]
    assistant_color_rgb: Tuple[int, int, int]
    max_window_width: int
    max_width_assistant: int
    max_width_user: int


def _config_value_to_env(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, (list, tuple)):
        return ",".join(str(item) for item in value)
    return str(value)


def _flatten_example_app_config(section: Dict[str, Any]) -> Dict[str, str]:
    flattened: Dict[str, str] = {}

    def visit(node: Dict[str, Any]) -> None:
        for raw_name, value in node.items():
            if isinstance(value, dict):
                visit(value)
                continue
            if value is None:
                continue
            name = str(raw_name).strip().replace("-", "_").upper()
            if name in flattened:
                raise ValueError(
                    f"Doppelter example_app-Konfigurationswert: {raw_name}"
                )
            flattened[name] = _config_value_to_env(value)

    visit(section)
    return flattened


def load_example_app_defaults(path: Path = PROJECT_CONFIG_PATH) -> Dict[str, str]:
    if not path.is_file():
        raise FileNotFoundError(f"Projektkonfiguration nicht gefunden: {path}")
    try:
        import yaml
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "PyYAML fehlt. Installiere die Projektabhängigkeiten erneut."
        ) from exc

    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError("config.yaml muss ein YAML-Objekt enthalten.")
    section = payload.get("example_app", {})
    if not isinstance(section, dict):
        raise ValueError("config.yaml: example_app muss ein Objekt sein.")
    return _flatten_example_app_config(section)


def load_example_app_env() -> None:
    """
    Loads config.yaml defaults and root secrets, preserving process overrides.
    """

    process_env = dict(os.environ)
    merged = load_example_app_defaults()
    if SECRETS_ENV_PATH.is_file():
        merged.update({
            key: value
            for key, value in dotenv_values(SECRETS_ENV_PATH).items()
            if value not in (None, "")
        })

    merged.update(process_env)
    for key, value in merged.items():
        os.environ[key] = str(value)


def configure_file_logging(logs_dir: Optional[Path] = None):
    logs_dir = logs_dir or PROJECT_ROOT / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / "ui_openai_voice_interface.log"
    formatter = logging.Formatter(
        "%(asctime)s.%(msecs)03d - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    app_log = logging.getLogger("example_app.openai_voice_interface")
    app_log.setLevel(logging.INFO)
    app_log.propagate = False

    realtime_log = logging.getLogger("realtimestt")
    realtime_log.setLevel(logging.DEBUG)
    realtime_log.propagate = False

    for target_logger in (app_log, realtime_log):
        if not any(
            isinstance(handler, RotatingFileHandler)
            and getattr(handler, "baseFilename", None) == str(log_path)
            for handler in target_logger.handlers
        ):
            handler = RotatingFileHandler(
                log_path,
                maxBytes=1_000_000,
                backupCount=3,
                encoding="utf-8",
            )
            handler.setLevel(logging.INFO)
            handler.setFormatter(formatter)
            target_logger.addHandler(handler)

    return app_log, str(log_path)


def asset_path(filename: str) -> str:
    return str(APP_DIR / filename)


def env_first(*names: str, default=None):
    for name in names:
        value = os.environ.get(name)
        if value not in (None, ""):
            return value
    return default


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value in (None, ""):
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def env_first_bool(names: Iterable[str], default: bool = False) -> bool:
    for name in names:
        value = os.environ.get(name)
        if value not in (None, ""):
            return value.strip().lower() in ("1", "true", "yes", "on")
    return default


def env_optional_bool(name: str, default: Optional[bool] = None) -> Optional[bool]:
    value = os.environ.get(name)
    if value in (None, ""):
        return default
    normalized = value.strip().lower()
    if normalized in ("none", "null", "auto"):
        return None
    return normalized in ("1", "true", "yes", "on")


def env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    return int(value) if value not in (None, "") else default


def env_first_int(names: Iterable[str], default: int) -> int:
    for name in names:
        value = os.environ.get(name)
        if value not in (None, ""):
            return int(value)
    return default


def env_optional_int(name: str, default: Optional[int] = None) -> Optional[int]:
    value = os.environ.get(name)
    return int(value) if value not in (None, "") else default


def env_float(name: str, default: float) -> float:
    value = os.environ.get(name)
    return float(value) if value not in (None, "") else default


def env_first_float(names: Iterable[str], default: float) -> float:
    for name in names:
        value = os.environ.get(name)
        if value not in (None, ""):
            return float(value)
    return default


def env_float_tuple(name: str, default: Optional[Tuple[float, ...]]) -> Optional[Tuple[float, ...]]:
    value = os.environ.get(name)
    if value in (None, ""):
        return default
    if value.strip().lower() in ("none", "null", "off", "false"):
        return None
    return tuple(float(part.strip()) for part in value.split(",") if part.strip())


def env_int_list(name: str, default: Optional[List[int]]) -> Optional[List[int]]:
    value = os.environ.get(name)
    if value in (None, ""):
        return default
    if value.strip().lower() in ("none", "null"):
        return None
    return [int(part.strip()) for part in value.split(",") if part.strip()]


def env_json_dict(name: str, default: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    value = os.environ.get(name)
    if value in (None, ""):
        return default
    if value.strip().lower() in ("none", "null"):
        return None
    data = json.loads(value)
    if not isinstance(data, dict):
        raise ValueError("%s must be a JSON object" % name)
    return data


def env_choice(name: str, default: str, choices: Iterable[str]) -> str:
    value = os.environ.get(name, default).strip().lower()
    allowed = set(choices)
    if value not in allowed:
        raise ValueError("%s must be one of: %s" % (name, ", ".join(sorted(allowed))))
    return value


def env_rgb(name: str, default: Tuple[int, int, int]) -> Tuple[int, int, int]:
    value = os.environ.get(name)
    if value in (None, ""):
        return default
    parts = [int(part.strip()) for part in value.split(",") if part.strip()]
    if len(parts) != 3:
        raise ValueError("%s must contain exactly three comma-separated RGB values" % name)
    return tuple(max(0, min(255, part)) for part in parts)


def env_log_level(name: str, default: int) -> int:
    value = os.environ.get(name)
    if value in (None, ""):
        return default
    normalized = value.strip().upper()
    if normalized.isdigit():
        return int(normalized)
    return int(getattr(logging, normalized))


def normalize_backend(name: str) -> str:
    return (name or "faster_whisper").strip().lower().replace("-", "_")


def custom_api_options(language: str) -> Dict[str, Any]:
    return {
        "base_url": env_first("CUSTOM_API_STT_BASE_URL", "CUSTOM_API_BASE_URL"),
        "api_key": os.environ.get("CUSTOM_API_STT_API_KEY"),
        "model": os.environ.get("CUSTOM_API_STT_MODEL", "stt/medium"),
        "response_format": os.environ.get("CUSTOM_API_STT_RESPONSE_FORMAT", "json"),
        "timeout": env_float("CUSTOM_API_STT_TIMEOUT", 90),
        "sample_rate": env_int("CUSTOM_API_STT_SAMPLE_RATE", 16000),
        "language": language,
        "warmup": env_bool("CUSTOM_API_STT_WARMUP", False),
        "max_retries": env_int("CUSTOM_API_STT_MAX_RETRIES", 1),
    }


def kroko_options(language: str, realtime: bool = False) -> Dict[str, Any]:
    options = {
        "language": env_first(
            "REALTIMESTT_KROKO_ONNX_LANGUAGE",
            "KROKO_ONNX_LANGUAGE",
            default=language,
        ),
        "provider": env_first(
            "REALTIMESTT_KROKO_ONNX_PROVIDER",
            "KROKO_ONNX_PROVIDER",
            default="cpu",
        ),
        "num_threads": env_first_int(
            ("REALTIMESTT_KROKO_ONNX_NUM_THREADS", "KROKO_ONNX_NUM_THREADS"),
            1,
        ),
        "suppress_native_output": env_bool("KROKO_ONNX_SUPPRESS_LICENSE_OUTPUT", True),
    }
    model_path = env_first(
        "REALTIMESTT_KROKO_ONNX_REALTIME_MODEL" if realtime else "REALTIMESTT_KROKO_ONNX_MODEL",
        "KROKO_ONNX_REALTIME_MODEL" if realtime else "KROKO_ONNX_MODEL",
    )
    if model_path:
        options["model_path"] = model_path
    return options


def model_for_backend(backend: str, realtime: bool = False) -> str:
    if backend == "custom_api":
        return os.environ.get("CUSTOM_API_STT_MODEL", "stt/medium")
    if backend in ("kroko", "kroko_onnx", "banafo_kroko"):
        return env_first(
            "REALTIMESTT_KROKO_ONNX_REALTIME_MODEL" if realtime else "REALTIMESTT_KROKO_ONNX_MODEL",
            "KROKO_ONNX_REALTIME_MODEL" if realtime else "KROKO_ONNX_MODEL",
            default="Kroko-DE-Community-128-L-Streaming-001",
        )
    if realtime:
        return env_first(
            "REALTIME_MODEL",
            "REALTIME_STT_MODEL",
            "FASTER_WHISPER_REALTIME_MODEL",
            "REALTIMESTT_FASTER_WHISPER_REALTIME_MODEL",
            default="tiny",
        )
    return env_first(
        "MODEL",
        "STT_MODEL",
        "FASTER_WHISPER_MODEL",
        "REALTIMESTT_FASTER_WHISPER_DEFAULT_MODEL",
        "FASTER_WHISPER_DEFAULT_MODEL",
        default="medium",
    )


def options_for_backend(backend: str, language: str, realtime: bool = False) -> Dict[str, Any]:
    if backend == "custom_api":
        return custom_api_options(language)
    if backend in ("kroko", "kroko_onnx", "banafo_kroko"):
        return kroko_options(language, realtime=realtime)
    return {}


def backend_config(backend: str, language: str, realtime: bool = False) -> BackendConfig:
    backend = normalize_backend(backend)
    return BackendConfig(
        name=backend,
        model=model_for_backend(backend, realtime=realtime),
        options=options_for_backend(backend, language, realtime=realtime),
    )


def build_config(load_env_files: bool = True) -> ExampleAppConfig:
    if load_env_files:
        load_example_app_env()

    language = env_first(
        "LANGUAGE",
        "STT_LANGUAGE",
        "CUSTOM_API_STT_LANGUAGE",
        "REALTIMESTT_KROKO_ONNX_LANGUAGE",
        "KROKO_ONNX_LANGUAGE",
        default="de",
    )
    final_backend_name = normalize_backend(
        env_first(
            "STT_BACKEND",
            "TRANSCRIPTION_ENGINE",
            "REALTIMESTT_TRANSCRIPTION_ENGINE",
            default="faster_whisper",
        )
    )
    realtime_backend_name = normalize_backend(
        env_first(
            "REALTIME_STT_BACKEND",
            "REALTIME_TRANSCRIPTION_ENGINE",
            "REALTIMESTT_REALTIME_TRANSCRIPTION_ENGINE",
            default=("faster_whisper" if final_backend_name == "custom_api" else final_backend_name),
        )
    )

    return ExampleAppConfig(
        app_dir=APP_DIR,
        project_root=PROJECT_ROOT,
        logs_dir=PROJECT_ROOT / "logs",
        max_history_messages=env_int("MAX_HISTORY_MESSAGES", 6),
        return_to_wakewords_after_silence=env_float("RETURN_TO_WAKEWORDS_AFTER_SILENCE", 18),
        start_with_wakeword=env_bool("START_WITH_WAKEWORD", True),
        start_engine=os.environ.get("START_ENGINE", "Edge").strip().strip('"'),
        edge_voice_string=os.environ.get("EDGE_VOICE_STRING", "de-DE-KatjaNeural"),
        final_backend=backend_config(final_backend_name, language, realtime=False),
        realtime_backend=backend_config(realtime_backend_name, language, realtime=True),
        download_root=env_first("DOWNLOAD_ROOT", "REALTIMESTT_DOWNLOAD_ROOT"),
        device=os.environ.get("DEVICE", "cpu"),
        compute_type=os.environ.get("COMPUTE_TYPE", "int8"),
        input_device_index=env_optional_int("INPUT_DEVICE_INDEX"),
        gpu_device_index=env_int("GPU_DEVICE_INDEX", 0),
        use_microphone=env_bool("USE_MICROPHONE", True),
        spinner=env_bool("SPINNER", True),
        batch_size=env_int("BATCH_SIZE", 16),
        realtime_batch_size=env_int("REALTIME_BATCH_SIZE", 16),
        beam_size=env_int("BEAM_SIZE", 5),
        beam_size_realtime=env_int("BEAM_SIZE_REALTIME", 3),
        initial_prompt=env_first("INITIAL_PROMPT", "REALTIMESTT_INITIAL_PROMPT"),
        initial_prompt_realtime=env_first(
            "INITIAL_PROMPT_REALTIME",
            "REALTIMESTT_INITIAL_PROMPT_REALTIME",
        ),
        suppress_tokens=env_int_list("SUPPRESS_TOKENS", [-1]),
        ensure_sentence_starting_uppercase=env_bool(
            "ENSURE_SENTENCE_STARTING_UPPERCASE",
            True,
        ),
        ensure_sentence_ends_with_period=env_bool(
            "ENSURE_SENTENCE_ENDS_WITH_PERIOD",
            True,
        ),
        print_transcription_time=env_bool("PRINT_TRANSCRIPTION_TIME", False),
        early_transcription_on_silence=env_int("EARLY_TRANSCRIPTION_ON_SILENCE", 0),
        no_log_file=env_bool("NO_LOG_FILE", True),
        log_level=env_log_level("LOG_LEVEL", logging.CRITICAL),
        use_extended_logging=env_bool("USE_EXTENDED_LOGGING", False),
        faster_whisper_vad_filter=env_bool("FASTER_WHISPER_VAD_FILTER", True),
        normalize_audio=env_bool("NORMALIZE_AUDIO", False),
        start_callback_in_new_thread=env_bool("START_CALLBACK_IN_NEW_THREAD", False),
        allowed_latency_limit=env_int("ALLOWED_LATENCY_LIMIT", 600),
        sample_rate=env_int("SAMPLE_RATE", 16000),
        buffer_size=env_int("BUFFER_SIZE", 512),
        handle_buffer_overflow=env_bool("HANDLE_BUFFER_OVERFLOW", True),
        debug_mode=env_bool("DEBUG_MODE", False),
        wakeword_backend=os.environ.get("WAKEWORD_BACKEND", ""),
        openwakeword_model_paths=env_first(
            "OPENWAKEWORD_MODEL_PATHS",
            "OPEN_WAKEWORD_MODEL_PATHS",
        ),
        openwakeword_inference_framework=os.environ.get(
            "OPENWAKEWORD_INFERENCE_FRAMEWORK",
            "onnx",
        ),
        wake_words=os.environ.get("WAKE_WORDS", "Jarvis"),
        wake_words_sensitivity=env_float("WAKE_WORDS_SENSITIVITY", 0.55),
        wake_word_activation_delay=env_float("WAKE_WORD_ACTIVATION_DELAY", 0.0),
        wake_word_timeout=env_float("WAKE_WORD_TIMEOUT", 10.0),
        wake_word_buffer_duration=env_float("WAKE_WORD_BUFFER_DURATION", 0.1),
        silero_sensitivity=env_float("SILERO_SENSITIVITY", 0.4),
        silero_use_onnx=env_optional_bool("SILERO_USE_ONNX", False),
        silero_deactivity_detection=env_bool("SILERO_DEACTIVITY_DETECTION", False),
        silero_backend=os.environ.get("SILERO_BACKEND", "auto"),
        silero_onnx_model_path=env_first("SILERO_ONNX_MODEL_PATH"),
        silero_onnx_threads=env_int("SILERO_ONNX_THREADS", 2),
        deactivity_silence_confirmation_duration=env_float(
            "DEACTIVITY_SILENCE_CONFIRMATION_DURATION",
            0.16,
        ),
        webrtc_sensitivity=env_int("WEBRTC_SENSITIVITY", 2),
        warmup_vad=env_bool("WARMUP_VAD", True),
        post_speech_silence_duration=env_first_float(
            ("POST_SPEECH_SILENCE_DURATION", "REALTIMESTT_POST_SPEECH_SILENCE_DURATION"),
            3.0,
        ),
        min_length_of_recording=env_first_float(
            ("MIN_LENGTH_OF_RECORDING", "REALTIMESTT_MIN_LENGTH_OF_RECORDING"),
            0.8,
        ),
        min_gap_between_recordings=env_first_float(
            ("MIN_GAP_BETWEEN_RECORDINGS", "REALTIMESTT_MIN_GAP_BETWEEN_RECORDINGS"),
            0.6,
        ),
        pre_recording_buffer_duration=env_first_float(
            ("PRE_RECORDING_BUFFER_DURATION", "REALTIMESTT_PRE_RECORDING_BUFFER_DURATION"),
            1.0,
        ),
        pre_recording_buffer_trim_config=env_json_dict(
            "PRE_RECORDING_BUFFER_TRIM_CONFIG",
        ),
        use_main_model_for_realtime=env_bool("USE_MAIN_MODEL_FOR_REALTIME", False),
        realtime_processing_pause=env_first_float(
            ("REALTIME_PROCESSING_PAUSE", "REALTIMESTT_REALTIME_PROCESSING_PAUSE"),
            0.35,
        ),
        init_realtime_after_seconds=env_first_float(
            ("INIT_REALTIME_AFTER_SECONDS", "REALTIMESTT_INIT_REALTIME_AFTER_SECONDS"),
            0.7,
        ),
        enable_realtime_transcription=env_first_bool(
            ("ENABLE_REALTIME_TRANSCRIPTION", "REALTIMESTT_ENABLE_REALTIME_TRANSCRIPTION"),
            True,
        ),
        realtime_callback=env_choice(
            "REALTIME_CALLBACK",
            "stabilized",
            ("update", "stabilized", "both"),
        ),
        realtime_transcription_use_syllable_boundaries=env_bool(
            "REALTIME_TRANSCRIPTION_USE_SYLLABLE_BOUNDARIES",
            False,
        ),
        realtime_boundary_detector_sensitivity=env_float(
            "REALTIME_BOUNDARY_DETECTOR_SENSITIVITY",
            0.6,
        ),
        realtime_boundary_followup_delays=env_float_tuple(
            "REALTIME_BOUNDARY_FOLLOWUP_DELAYS",
            (0.05, 0.2),
        ),
        clear_text_delay_ms=env_int("CLEAR_TEXT_DELAY_MS", 15000),
        tts_minimum_sentence_length=env_int("TTS_MINIMUM_SENTENCE_LENGTH", 8),
        tts_buffer_threshold_seconds=env_float("TTS_BUFFER_THRESHOLD_SECONDS", 2.5),
        tts_log_characters=env_bool("TTS_LOG_CHARACTERS", True),
        edge_rate=env_int("EDGE_RATE", 24),
        edge_pitch=env_int("EDGE_PITCH", 10),
        language=language,
        chat_model=os.environ.get("CUSTOM_API_CHAT_MODEL", "opencode-go/minimax-m3"),
        voice_system=os.environ.get("VOICE_SYSTEM", "Katja"),
        system_prompt=env_first(
            "CUSTOM_API_SYSTEM_PROMPT",
            "CUSTOM_API_CHAT_SYSTEM_PROMPT",
            "CUSTOM_API_STT_PROMPT",
            default=(
                "Sei präzise, höflich und locker. Antworte kurz und direkt, "
                "als ob wir gerade sprechen."
            ),
        ),
        user_font_size=env_int("USER_FONT_SIZE", 22),
        assistant_font_size=env_int("ASSISTANT_FONT_SIZE", 24),
        user_color_rgb=env_rgb("USER_COLOR_RGB", (0, 188, 242)),
        assistant_color_rgb=env_rgb("ASSISTANT_COLOR_RGB", (239, 98, 166)),
        max_window_width=env_int("MAX_WINDOW_WIDTH", 1600),
        max_width_assistant=env_int("MAX_WIDTH_ASSISTANT", 1200),
        max_width_user=env_int("MAX_WIDTH_USER", 1500),
    )
