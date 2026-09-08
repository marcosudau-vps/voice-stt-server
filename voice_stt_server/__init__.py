"""The canonical public VoiceSTT import package (AP-SRV-070 W5-R04).

Both public distributions - ``voice-stt-server`` (Kroko Free runtime) and
``voice-stt-server-pro`` (Kroko Pro runtime) - expose this one import name, so
application code never changes when an installation moves between Free and
Pro::

    from voice_stt_server import AudioToTextRecorder

The historical :mod:`VoiceSTT` package stays importable and stays the place the
implementation actually lives; this module is a thin, lazy re-export of the
same objects, so the two names are never two implementations. Adding a name
rather than renaming one is deliberate: it gives the public product a correct,
stable identity without breaking a single existing import.

The *installed distribution* - not a runtime license key - decides which native
Kroko runtime is present. :func:`embedded_kroko` reports what this
installation actually carries.
"""

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
