"""Compatibility entry point - the implementation lives in ``engineering/tools/compose.py``.

Kept so that ``python tools/compose.py ...`` and ``from tools import compose`` keep
working after the V2 engineering consolidation. Importing this file yields the
*same* module object as ``engineering.tools.compose`` (one identity, so patches
and module state are shared); no logic lives here.
"""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from engineering.tools import compose as _implementation  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(_implementation.main())

sys.modules[__name__] = _implementation
