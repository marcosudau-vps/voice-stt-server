"""Backward-compatible launcher for :mod:`examples.app_webserver.server`.

It intentionally performs no runtime package installation and uses the shared
CPU-only server, which supports independent clients and concurrent sessions.
"""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from examples.app_webserver.server import main  # noqa: F401,E402


if __name__ == "__main__":
    main()
