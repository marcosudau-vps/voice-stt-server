"""Provenance of the Kroko native runtime embedded in this installation.

AP-SRV-070 W5-R04. The two public distributions each embed exactly one
qualified Kroko native runtime:

.. code-block:: text

    voice-stt-server      -> Kroko Free native runtime
    voice-stt-server-pro  -> Kroko Pro native runtime

``tools/build_distribution.py`` writes :data:`EMBEDDED_MANIFEST_NAME` next to
this module when it merges the qualified Kroko wheel into the distribution
wheel. The file records which variant was embedded, the Kroko version, the
build fingerprint it was qualified under, and the SHA-256 of the exact Kroko
wheel whose bytes were merged - so an installed environment can prove its own
runtime identity offline, without a network call and without depending on a
separately installed ``kroko-onnx`` distribution.

A development checkout has no such file. That is not an error: it simply means
"this environment did not come from a published distribution wheel", and every
function here reports ``None`` rather than guessing.

**The license key never appears here and never selects a variant.** The
installed distribution decides which runtime exists; the Pro key is only a
runtime credential for a Pro runtime that is already installed.
"""

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
