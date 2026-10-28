"""Public import surface for the unified voice-stt-server V2 distribution.

The complete product embeds the Pro-capable native runtime. Community models
need no key; Pro model admission requires model-specific permission."""

from VoiceSTT._version import resolve_version as _resolve_version

from ._embedded import embedded_kroko, embedded_kroko_variant

__all__ = [
    "AudioToTextRecorder",
    "AudioToTextRecorderClient",
    "AudioInput",
    "RealtimeSpeechBoundaryDetector",
    "SpeechBoundaryEvent",
    "SpeechBoundaryResult",
    "embedded_kroko",
    "embedded_kroko_variant",
    "__version__",
    "get_version",
]


def get_version() -> str:
    """The one product version authority (see :mod:`VoiceSTT._version`)."""
    return _resolve_version()


def __getattr__(name):
    """Loads the re-exported public objects lazily.

    Mirrors :mod:`VoiceSTT`'s own lazy ``__getattr__`` on purpose: importing
    this package must not drag in torch, faster-whisper or PyAudio just to let
    a caller read ``__version__``.
    """
    if name == "__version__":
        return get_version()
    if name in {
        "AudioToTextRecorder",
        "AudioToTextRecorderClient",
        "AudioInput",
        "RealtimeSpeechBoundaryDetector",
        "SpeechBoundaryEvent",
        "SpeechBoundaryResult",
    }:
        import VoiceSTT

        return getattr(VoiceSTT, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(__all__)
