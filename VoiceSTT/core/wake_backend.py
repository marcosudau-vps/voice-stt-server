"""AP-SRV-060 C3 dual inference backend policy.

The server target is Linux/Ubuntu on a VPS; development currently runs on
Windows. Every wake-word model this build ships is meant to exist in both
artifact formats, so the product does not need one backend to be universally
available - it needs **one common backend per live engine**.

The rule this module owns, and the one it deliberately does not own
----------------------------------------------------------------------

It owns the *choice*: given a requested backend (``auto``/``onnx``/``tflite``),
the operating system and the set of backends that are healthy **for the whole
selection**, which backend does a session run on, and if none, why not.

It does not own health. Whether a backend is healthy for a wake word is the
catalog's answer (:mod:`VoiceSTT.core.wakeword_catalog`), because that is where
artifacts, manifests, integrity and the real loadability probe live.

There is no per-model mixture
-----------------------------

A live :class:`~VoiceSTT.core.openwakeword_engine.OpenWakeWordEngine` holds one
upstream ``openwakeword.Model`` and therefore exactly one inference framework.
"wake word A on ONNX, wake word B on TFLite" is not expressible and is not
wanted: the selection is admitted as a whole or not at all.

``auto`` prefers the backend the deployment platform is built around and falls
back to the other one **for the entire selection**. An explicitly requested
backend never falls back - a silent switch would make an operator's deployment
decision unobservable.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Any, Iterable, Optional, Tuple


BACKEND_AUTO = "auto"
BACKEND_ONNX = "onnx"
BACKEND_TFLITE = "tflite"

#: The inference backends a wake-word artifact may be declared in.
INFERENCE_BACKENDS = (BACKEND_ONNX, BACKEND_TFLITE)

#: The accepted values of ``wakeWord.inferenceBackend``.
BACKEND_SETTING_VALUES = (BACKEND_AUTO, BACKEND_ONNX, BACKEND_TFLITE)

PLATFORM_WINDOWS = "windows"
PLATFORM_LINUX = "linux"

#: An explicitly requested backend is not healthy for the whole selection.
REASON_BACKEND_UNAVAILABLE = "backend_unavailable"
#: No single backend is healthy for the whole selection.
REASON_NO_COMMON_BACKEND = "no_common_backend"


def current_platform() -> str:
    """The deployment platform family this process runs on."""
    return PLATFORM_WINDOWS if sys.platform.startswith("win") else PLATFORM_LINUX


def normalize_backend(value: Any) -> str:
    """One accepted ``wakeWord.inferenceBackend`` value, or ``auto``."""
    text = str(value or "").strip().lower()
    return text if text in BACKEND_SETTING_VALUES else BACKEND_AUTO


def backend_preference(
    requested: Any, *, platform: Optional[str] = None
) -> Tuple[str, ...]:
    """The ordered backends one request may use.

    ``auto`` prefers ONNX on Windows and TFLite/LiteRT on Linux and keeps the
    other one as the common fallback. An explicit value yields exactly itself,
    so there is nothing to fall back to.
    """
    backend = normalize_backend(requested)
    if backend != BACKEND_AUTO:
        return (backend,)
    family = str(platform or current_platform()).strip().lower()
    if family.startswith("win"):
        return (BACKEND_ONNX, BACKEND_TFLITE)
    return (BACKEND_TFLITE, BACKEND_ONNX)


@dataclass(frozen=True)
class BackendSelection:
    """The backend one wake selection runs on, or the reason it may not run."""

    requested: str
    preference: Tuple[str, ...]
    backend: Optional[str] = None
    fallback_used: bool = False
    reason: Optional[str] = None

    @property
    def admitted(self) -> bool:
        return self.backend is not None

    def to_dict(self) -> dict:
        payload = {
            "requestedBackend": self.requested,
            "backendPreference": list(self.preference),
            "backend": self.backend,
            "fallbackUsed": bool(self.fallback_used),
        }
        if self.reason:
            payload["reason"] = self.reason
        return payload


def select_common_backend(
    requested: Any,
    healthy_backends: Iterable[str],
    *,
    platform: Optional[str] = None,
) -> BackendSelection:
    """The one backend the whole selection runs on.

    ``healthy_backends`` are the backends under which **every** selected wake
    word and the shared pipeline models are loadable. The first entry of the
    preference order that is healthy wins; anything after the first entry is a
    fallback and is reported as one.
    """
    normalized = normalize_backend(requested)
    preference = backend_preference(normalized, platform=platform)
    healthy = {
        str(value).strip().lower() for value in healthy_backends or ()
    }
    for index, backend in enumerate(preference):
        if backend in healthy:
            return BackendSelection(
                requested=normalized,
                preference=preference,
                backend=backend,
                fallback_used=index > 0,
            )
    reason = (
        REASON_NO_COMMON_BACKEND if normalized == BACKEND_AUTO
        else REASON_BACKEND_UNAVAILABLE
    )
    return BackendSelection(
        requested=normalized, preference=preference, reason=reason
    )
