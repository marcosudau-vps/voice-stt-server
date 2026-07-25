"""Backward-compatible launcher for :mod:`app_webserver.server`.

It intentionally performs no runtime package installation and uses the shared
CPU-only server, which supports independent clients and concurrent sessions.
"""

from app_webserver.server import main  # noqa: F401


if __name__ == "__main__":
    main()
