"""Shared Kroko runtime-credential projection and diagnostic redaction."""

from __future__ import annotations

import os
import re
from typing import Any, Iterable, Mapping, Tuple


KROKO_CREDENTIAL_ENV_NAMES = (
    "KROKO_API_KEY",
    "KROKO_ONNX_KEY",
    "VOICESTT_KROKO_ONNX_KEY",
    "KROKO_KEY",
)

_CREDENTIAL_KEYS = {
    "apikey",
    "krokoapikey",
    "krokokey",
    "krokoonnxkey",
    "voicestttkrokoonnxkey",
}
_OPTION_CONTEXT_KEYS = {
    "engineoptions",
    "realtimeengineoptions",
    "transcriptionengineoptions",
    "realtimetranscriptionengineoptions",
    "sttenginesettings",
    "kroko",
    "krokoonnx",
    "banafokroko",
}
_LABELLED_SECRET = re.compile(
    r"(?i)\b(kroko[_-]?(?:onnx[_-]?)?(?:api[_-]?)?key|api[_-]?key|key)"
    r"\s*[:=]\s*[^\s,;]+"
)


def _normalized(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def _child_context(current: bool, key: Any) -> bool:
    normalized = _normalized(key)
    return (
        current
        or normalized in _OPTION_CONTEXT_KEYS
        or normalized.startswith("kroko")
    )


def _secret_key(key: Any, context: bool) -> bool:
    normalized = _normalized(key)
    return normalized in _CREDENTIAL_KEYS or (context and normalized == "key")


def redact_kroko_credentials(
    value: Any,
    *,
    drop: bool = False,
    replacement: str = "[REDACTED]",
    _context: bool = False,
):
    """Recursively remove or redact known Kroko credential fields."""
    if isinstance(value, Mapping):
        cleaned = {}
        for key, child in value.items():
            if _secret_key(key, _context):
                if not drop:
                    cleaned[key] = replacement
                continue
            cleaned[key] = redact_kroko_credentials(
                child,
                drop=drop,
                replacement=replacement,
                _context=_child_context(_context, key),
            )
        return cleaned
    if isinstance(value, list):
        return [
            redact_kroko_credentials(
                child,
                drop=drop,
                replacement=replacement,
                _context=_context,
            )
            for child in value
        ]
    if isinstance(value, tuple):
        return tuple(
            redact_kroko_credentials(
                child,
                drop=drop,
                replacement=replacement,
                _context=_context,
            )
            for child in value
        )
    return value


def kroko_credential_values(value: Any, *, _context: bool = False) -> Tuple[str, ...]:
    """Collect only secret values for in-memory exception redaction."""
    values = []
    if isinstance(value, Mapping):
        for key, child in value.items():
            if _secret_key(key, _context):
                if child:
                    values.append(str(child))
                continue
            values.extend(
                kroko_credential_values(
                    child,
                    _context=_child_context(_context, key),
                )
            )
    elif isinstance(value, (list, tuple)):
        for child in value:
            values.extend(kroko_credential_values(child, _context=_context))
    return tuple(dict.fromkeys(item for item in values if item))


def redact_secret_text(value: Any, extra_values: Iterable[Any] = ()) -> str:
    """Redact configured secret bytes and labelled credential fragments."""
    text = str(value)
    known = list(extra_values)
    known.extend(os.getenv(name) for name in KROKO_CREDENTIAL_ENV_NAMES)
    for secret in sorted(
        {str(item) for item in known if item},
        key=len,
        reverse=True,
    ):
        text = text.replace(secret, "[REDACTED]")
    return _LABELLED_SECRET.sub(
        lambda match: "{0}=[REDACTED]".format(match.group(1)),
        text,
    )


__all__ = [
    "KROKO_CREDENTIAL_ENV_NAMES",
    "kroko_credential_values",
    "redact_kroko_credentials",
    "redact_secret_text",
]
