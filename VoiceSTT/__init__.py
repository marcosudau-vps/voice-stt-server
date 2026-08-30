"""
Exposes the public VoiceSTT package objects through lazy imports.
"""

from ._version import resolve_version as _resolve_version

__all__ = [
    "AudioToTextRecorder",
    "AudioToTextRecorderClient",
    "AudioInput",
    "RealtimeSpeechBoundaryDetector",
    "SpeechBoundaryEvent",
    "SpeechBoundaryResult",
    "__version__",
    "get_version",
]


def get_version() -> str:
    """The one product version authority (see :mod:`VoiceSTT._version`)."""
    return _resolve_version()


def __getattr__(name):
    """
    Loads exported package attributes lazily.
    """

    if name == "__version__":
        return get_version()
    if name == "AudioToTextRecorder":
        from .audio_recorder import AudioToTextRecorder

        return AudioToTextRecorder
    if name == "AudioToTextRecorderClient":
        from .audio_recorder_client import AudioToTextRecorderClient

        return AudioToTextRecorderClient
    if name == "AudioInput":
        from .audio_input import AudioInput

        return AudioInput
    if name == "RealtimeSpeechBoundaryDetector":
        from .core.realtime_boundary_detector import RealtimeSpeechBoundaryDetector

        return RealtimeSpeechBoundaryDetector
    if name == "SpeechBoundaryEvent":
        from .core.realtime_boundary_detector import SpeechBoundaryEvent

        return SpeechBoundaryEvent
    if name == "SpeechBoundaryResult":
        from .core.realtime_boundary_detector import SpeechBoundaryResult

        return SpeechBoundaryResult
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
