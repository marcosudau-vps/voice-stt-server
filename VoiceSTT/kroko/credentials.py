"""Single source for the key actually passed to the native Kroko recognizer.

No persistence, network access, logging or native imports. In particular,
`recognizer.key` overrides the top-level key exactly like the existing
`kwargs.update(recognizer)` in the engine.
"""

from __future__ import annotations

import os
from typing import Any, Mapping

KROKO_KEY_ENV_NAMES = (
    "KROKO_API_KEY",
    "KROKO_ONNX_KEY",
    "VOICESTT_KROKO_ONNX_KEY",
    "KROKO_KEY",
)


def effective_recognizer_key(
    options: Mapping[str, Any] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> Any:
    """Return the exact key value the recognizer will receive.

    The nested recognizer dictionary is the final native-kwargs override;
    unlike ordinary fallback expressions, an explicit empty nested key
    suppresses an otherwise populated environment key. Other invalid nested
    settings remain the responsibility of the engine's existing validator.
    """
    options = options or {}
    nested = options.get("recognizer")
    if isinstance(nested, dict) and "key" in nested:
        return nested["key"]

    explicit = options.get("key")
    if explicit:
        return explicit

    source = os.environ if environ is None else environ
    for name in KROKO_KEY_ENV_NAMES:
        value = source.get(name)
        if value:
            return value
    return ""


__all__ = ["KROKO_KEY_ENV_NAMES", "effective_recognizer_key"]
