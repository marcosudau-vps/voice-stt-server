"""Provenance of the Kroko runtime embedded in voice-stt-server.

The single public V2 product embeds the qualified Pro-capable runtime. The
manifest binds native-wheel hash, fingerprint, upstream and platform identity.
Development checkouts have no embedded manifest. Keys do not select capability."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

#: The provenance file a merged distribution wheel carries.
EMBEDDED_MANIFEST_NAME = "_embedded_kroko.json"

#: Manifest schema version, so a future format change is detectable.
EMBEDDED_MANIFEST_SCHEMA = 1


def embedded_manifest_path() -> Path:
    """Where the provenance file lives inside an installed distribution."""
    return Path(__file__).resolve().parent / EMBEDDED_MANIFEST_NAME


def embedded_kroko() -> Optional[Dict[str, Any]]:
    """The embedded-runtime provenance, or ``None`` in a source checkout.

    Never raises for an absent file. A *corrupt* file is different: it is
    reported as ``None`` too, but only after the caller has had no chance to
    mistake it for a valid identity - callers that need a hard guarantee use
    :func:`VoiceSTT.kroko.artifacts.verify_installed_runtime`, which fails
    closed.
    """
    path = embedded_manifest_path()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def embedded_kroko_variant() -> Optional[str]:
    """``"free"``/``"pro"`` for an installed distribution, else ``None``."""
    payload = embedded_kroko()
    if not payload:
        return None
    variant = payload.get("variant")
    if variant in ("free", "pro"):
        return variant
    return None


__all__ = [
    "EMBEDDED_MANIFEST_NAME",
    "EMBEDDED_MANIFEST_SCHEMA",
    "embedded_manifest_path",
    "embedded_kroko",
    "embedded_kroko_variant",
]
