"""
Creates transcription engine instances by configured backend name.

V2 product boundary: exactly two transcription engines are supported,
``faster_whisper`` and ``kroko_onnx``. Former adapters were either removed or
moved to ``engineering/drafts/transcription_engines/`` as non-packaged drafts;
none of them is importable through this factory.
"""

from importlib import import_module

from .base import TranscriptionEngineConfig, UnsupportedTranscriptionEngineError


#: The only engines of the V2 product, keyed by their canonical identifier.
ENGINE_CLASS_PATHS = {
    "faster_whisper": (".faster_whisper_engine", "FasterWhisperEngine"),
    "kroko_onnx": (".kroko_onnx_engine", "KrokoOnnxEngine"),
}

#: Default engine when a caller passes no name.
DEFAULT_ENGINE = "faster_whisper"


def normalize_transcription_engine_name(name):
    """
    Returns the normalized spelling of an engine name (no alias mapping).
    """
    return (name or DEFAULT_ENGINE).strip().lower().replace("-", "_")


def is_supported_transcription_engine(name):
    """
    Whether ``name`` (after normalization) is a supported V2 engine.
    """
    return normalize_transcription_engine_name(name) in ENGINE_CLASS_PATHS


def unsupported_engine_message(name):
    """
    The one human-readable rejection text for an unsupported engine.
    """
    available_engines = ", ".join(sorted(ENGINE_CLASS_PATHS))
    return (
        f"Unsupported transcription engine '{name}'. "
        f"Supported engines: {available_engines}"
    )


def _load_engine_class(name):
    """
    Loads the engine class registered for a normalized name.
    """
    module_name, class_name = ENGINE_CLASS_PATHS[name]
    module = import_module(module_name, package=__package__)
    return getattr(module, class_name)


def create_transcription_engine(name, config: TranscriptionEngineConfig):
    """
    Creates a transcription engine for a configured backend name.
    """
    normalized_name = normalize_transcription_engine_name(name)
    config.device = "cpu"
    config.gpu_device_index = 0
    if normalized_name not in ENGINE_CLASS_PATHS:
        raise UnsupportedTranscriptionEngineError(unsupported_engine_message(name))
    engine_cls = _load_engine_class(normalized_name)
    return engine_cls(config)


def get_supported_transcription_engines():
    """
    Returns the sorted list of supported engine names.
    """
    return sorted(ENGINE_CLASS_PATHS)
