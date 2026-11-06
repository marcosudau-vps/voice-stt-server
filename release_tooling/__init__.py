"""Compatibility package - the release tooling lives in ``engineering/release/``.

``release_tooling.<module>`` resolves to the *same* module object as
``engineering.release.<module>``: one identity, so monkeypatching and module
state stay consistent for older callers. No release logic lives here; the
release state machine, gates and adapters are unchanged.
"""

import importlib
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

_SUBMODULES = (
    "adapters",
    "aliases",
    "candidate",
    "cli",
    "config",
    "engine",
    "errors",
    "gitinfo",
    "pipeline",
    "preflight",
    "rc_manifest",
    "redaction",
    "remote_checks",
    "state",
)

for _name in _SUBMODULES:
    _module = importlib.import_module(f"engineering.release.{_name}")
    sys.modules[f"{__name__}.{_name}"] = _module
    globals()[_name] = _module

__all__ = list(_SUBMODULES)
