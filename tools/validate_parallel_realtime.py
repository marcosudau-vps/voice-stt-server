"""Compatibility entry point - the implementation lives in ``engineering/tools/validate_parallel_realtime.py``.

Kept so that ``python tools/validate_parallel_realtime.py ...`` and ``from tools import validate_parallel_realtime`` keep
working after the V2 engineering consolidation. Importing this file yields the
*same* module object as ``engineering.tools.validate_parallel_realtime`` (one identity, so patches
and module state are shared); no logic lives here.
"""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from engineering.tools import validate_parallel_realtime as _implementation  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(_implementation.main())

sys.modules[__name__] = _implementation
