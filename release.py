#!/usr/bin/env python3
"""AP-SRV-070 release orchestrator - the one canonical release entry point.

This script is intentionally thin: it only delegates to
``engineering.release.cli`` (formerly ``release_tooling.cli``; that package
remains as a compatibility alias), which is the actual implementation
(preflight/dry-run/status/manifest/prepare-next-version/publish). There is
no second, competing release authority anywhere else in this repository -
``engineering/tools/build_production.py`` remains the (unrelated) Docker image build
orchestrator it always was; this script is the release-process authority
that sits on top of its output.

Usage::

    python release.py --help
    python release.py preflight
    python release.py dry-run
    python release.py status
    python release.py manifest validate <path>
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from engineering.release.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
