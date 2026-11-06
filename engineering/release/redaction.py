"""Secret redaction and detection for release state, RC manifests, and logs.

The resumable release state and the RC manifest (AP-SRV-070 W5, sections 7
and 12) must never carry a secret value - only non-secret identities
(commits, hashes, tags, image IDs) and boolean presence/auth-status flags.
This module gives the rest of ``release_tooling`` one place to check that
before anything is written to disk or printed.
"""

from __future__ import annotations

import re
from typing import Any

from .errors import SecretDetectedError

#: Substrings that mark a field name as secret-shaped. Matching is
#: case-insensitive and applies to the last path segment of a key, so
#: ``"hasApiKey"`` (a boolean status flag) still needs to be excluded
#: explicitly below rather than by accident.
_SECRET_KEY_MARKERS = ("key", "token", "secret", "password", "passwd", "credential")

#: Field names that are secret-*shaped* by the marker list above but are
#: documented, required, non-secret status flags (booleans or plain
#: identifiers only - never the underlying value).
_ALLOWED_SECRET_SHAPED_KEYS = {
    "apikeypresent",
    "haskey",
    "hasapikey",
    "haspypitoken",
    "hasghcrtoken",
    "hasdockerhubtoken",
    "krokoapikeypresent",
    "publickeyid",
}

#: Regexes for secret-*shaped values, independent of the field name, so a
#: secret pasted into the wrong field (e.g. a free-text "notes" field) is
#: still caught. Deliberately conservative: each pattern is a well-known
#: credential shape, not a generic "long string" heuristic that would flag
#: ordinary hashes/commits too.
_SECRET_VALUE_PATTERNS = (
    re.compile(r"pypi-[A-Za-z0-9_-]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"dckr_pat_[A-Za-z0-9_-]{20,}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)


def looks_like_secret_key_name(field_name: str) -> bool:
    """True if ``field_name`` (a dict key) is shaped like a secret field name."""
    normalized = str(field_name).strip().lower()
    if normalized in _ALLOWED_SECRET_SHAPED_KEYS:
        return False
    # A "...Present"/"...present" suffix is this codebase's one documented
    # naming convention for a boolean auth-status flag (see
    # ``release_tooling.config.credential_presence``); it is exempt by name
    # so callers can log/print it even before checking the value type.
    if normalized.endswith("present"):
        return False
    return any(marker in normalized for marker in _SECRET_KEY_MARKERS)


def looks_like_secret_value(value: Any) -> bool:
    """True if ``value`` matches a known credential shape."""
    if not isinstance(value, str):
        return False
    return any(pattern.search(value) for pattern in _SECRET_VALUE_PATTERNS)


def assert_no_secrets(data: Any, *, _path: str = "$") -> None:
    """Recursively raises :class:`SecretDetectedError` on the first secret-shaped
    field or value found in ``data`` (a JSON-shaped dict/list/scalar tree).

    A secret-shaped field name is only rejected when it carries a non-empty
    string value - a boolean/None presence flag such as ``"hasApiKey": true``
    is exactly the safely-checkable status the release state/manifest is
    allowed to carry (AP-SRV-070 W5, section 9: "credential presence/auth
    status where safely checkable without exposing values").
    """
    if isinstance(data, dict):
        for key, value in data.items():
            child_path = f"{_path}.{key}"
            if looks_like_secret_key_name(key) and isinstance(value, str) and value.strip():
                raise SecretDetectedError(
                    f"secret-shaped field {child_path!r} carries a non-empty string value"
                )
            assert_no_secrets(value, _path=child_path)
    elif isinstance(data, list):
        for index, item in enumerate(data):
            assert_no_secrets(item, _path=f"{_path}[{index}]")
    elif looks_like_secret_value(data):
        raise SecretDetectedError(f"value at {_path} matches a known credential shape")


def redact_text(text: str) -> str:
    """Replaces any known credential shape in free-form text with a placeholder.

    Used before writing subprocess output or exception text into evidence or
    normal logs, independent of whether that text ever reaches release
    state/manifest JSON.
    """
    redacted = text
    for pattern in _SECRET_VALUE_PATTERNS:
        redacted = pattern.sub("<redacted>", redacted)
    return redacted


__all__ = [
    "assert_no_secrets",
    "looks_like_secret_key_name",
    "looks_like_secret_value",
    "redact_text",
]
