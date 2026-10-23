"""Cold bootstrap for the unified Kroko native payload (AP-KR-020).

Selects exactly one private native payload root **before the first native
import** and pins it at the front of the import path. Any foreign or already
loaded incompatible native runtime is treated as a conflict, never silently
shadowed.

This module performs no native imports itself: conflict detection uses only
``sys.modules`` membership and :func:`importlib.util.find_spec` (which does
not import the target). The selected root is the single authority the later
owner-process generation (``supervisor.py``) and the official AP-030 packaging
must agree on.
"""

from __future__ import annotations

import importlib.util
import os
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence, Tuple


#: Native top-level module names that must come exclusively from the selected
#: private payload root. A second copy (global install, stale wheel, developer
#: checkout on the path) is a hard conflict.
NATIVE_MODULE_NAMES = ("kroko_onnx", "_sherpa_onnx", "sherpa_onnx")

#: Marker files, relative to the payload root, proving a complete private
#: installation view (mirrors the AP-030 component layout contract).
DEFAULT_MARKER_RELPATHS = ("kroko_onnx/__init__.py",)

#: Environment variable pointing at the private payload root. Absent means
#: "unmanaged global runtime" (current single-runtime installs): bootstrap is
#: a verified no-op instead of a silent path rewrite.
PAYLOAD_ROOT_ENV = "VOICESTT_KROKO_PAYLOAD_ROOT"


class BootstrapConflictError(RuntimeError):
    """A foreign or already loaded incompatible native runtime was found."""


@dataclass(frozen=True)
class BootstrapRecord:
    """The single cold-selected payload root of this process."""

    root: str
    markers_verified: Tuple[str, ...]
    native_module_names: Tuple[str, ...] = NATIVE_MODULE_NAMES
    selected_at_monotonic: float = field(default_factory=time.monotonic)


_lock = threading.RLock()
_selected: Optional[BootstrapRecord] = None


def _check_native_conflicts(
    modules: Mapping[str, Any],
    find_spec,
) -> Tuple[Tuple[str, ...], Tuple[str, ...]]:
    """Returns ``(loaded, foreign)`` conflicting native module names."""
    loaded = tuple(
        name for name in NATIVE_MODULE_NAMES if name in modules)
    foreign = []
    for name in NATIVE_MODULE_NAMES:
        if name in modules:
            continue
        try:
            spec = find_spec(name)
        except (ImportError, ValueError, AttributeError):
            continue
        if spec is not None:
            foreign.append(name)
    return loaded, tuple(foreign)


def cold_select(
    payload_root: Any,
    *,
    marker_relpaths: Sequence[str] = DEFAULT_MARKER_RELPATHS,
    _modules: Optional[Mapping[str, Any]] = None,
    _path: Optional[list] = None,
    _find_spec=None,
) -> BootstrapRecord:
    """Cold-selects exactly one private native payload root.

    Must run before the first native import in the owner process. Raises
    :class:`BootstrapConflictError` when a native module is already loaded
    or a foreign global provider shadows the private root, and
    :class:`FileNotFoundError` when a marker file is missing. Selecting the
    same root twice is idempotent; selecting a different root afterwards is
    refused (a runtime/key/model change requires a new owner process, never
    a second in-process ``sys.path`` switch).
    """
    global _selected
    root = Path(str(payload_root or "").strip()).expanduser()
    if not str(root):
        raise ValueError("payload_root must not be empty")
    root = root.resolve()
    modules = sys.modules if _modules is None else _modules
    path = sys.path if _path is None else _path
    find_spec = importlib.util.find_spec if _find_spec is None else _find_spec
    with _lock:
        if _selected is not None:
            if Path(_selected.root) == root:
                return _selected
            raise BootstrapConflictError(
                "a different Kroko payload root is already selected for this "
                f"process ({_selected.root}); start a new owner process instead"
            )
        loaded, foreign = _check_native_conflicts(modules, find_spec)
        if loaded:
            raise BootstrapConflictError(
                "incompatible native runtime already loaded: "
                + ", ".join(loaded)
            )
        if foreign:
            raise BootstrapConflictError(
                "foreign global Kroko provider shadows the private payload: "
                + ", ".join(foreign)
            )
        markers = tuple(str(item) for item in marker_relpaths)
        missing = [item for item in markers if not (root / item).is_file()]
        if missing:
            raise FileNotFoundError(
                f"incomplete Kroko payload root {root}: missing "
                + ", ".join(missing)
            )
        entry = str(root)
        if entry not in path:
            path.insert(0, entry)
        elif path[0] != entry:
            path.remove(entry)
            path.insert(0, entry)
        if os.name == "nt" and hasattr(os, "add_dll_directory"):
            try:
                os.add_dll_directory(entry)
            except (OSError, ValueError):
                pass
        _selected = BootstrapRecord(
            root=entry,
            markers_verified=markers,
        )
        return _selected


def ensure_bootstrap_from_env(
    *,
    _environ: Optional[Mapping[str, str]] = None,
    **kwargs,
) -> Optional[BootstrapRecord]:
    """Selects the payload root from the environment, if configured.

    Returns ``None`` without touching ``sys.path`` when
    ``VOICESTT_KROKO_PAYLOAD_ROOT`` is absent (unmanaged global runtime).
    Never invents a root, never scans the working directory.
    """
    environ = os.environ if _environ is None else _environ
    configured = str(environ.get(PAYLOAD_ROOT_ENV) or "").strip()
    if not configured:
        return None
    return cold_select(configured, **kwargs)


def selection_status() -> Optional[Dict[str, Any]]:
    """Redacted report of the process payload selection (or ``None``)."""
    with _lock:
        if _selected is None:
            return None
        return {
            "root": _selected.root,
            "markersVerified": list(_selected.markers_verified),
            "nativeModuleNames": list(_selected.native_module_names),
        }


def reset_selection_for_tests() -> None:
    """Clears the process selection. Test infrastructure only.

    The product never calls this: one owner process generation owns exactly
    one selection for its whole lifetime.
    """
    global _selected
    with _lock:
        _selected = None


__all__ = [
    "NATIVE_MODULE_NAMES",
    "DEFAULT_MARKER_RELPATHS",
    "PAYLOAD_ROOT_ENV",
    "BootstrapConflictError",
    "BootstrapRecord",
    "cold_select",
    "ensure_bootstrap_from_env",
    "selection_status",
    "reset_selection_for_tests",
]
