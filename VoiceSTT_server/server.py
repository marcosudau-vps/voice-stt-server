"""CPU-only production server entry point.

The implementation lives in ``api_fastapi_server`` so the documented
example and the installed ``stt-server`` command exercise exactly the same
multi-user scheduler, WebSocket protocol, and OpenAI-compatible endpoint.
"""

from api_fastapi_server.server import (  # noqa: F401
    ServerSettings,
    create_app,
    main,
    parse_args,
    settings_from_args,
)

__all__ = [
    "ServerSettings",
    "create_app",
    "main",
    "parse_args",
    "settings_from_args",
]


if __name__ == "__main__":
    main()
