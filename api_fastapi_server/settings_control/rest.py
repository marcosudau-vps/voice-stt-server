"""Thin REST-v2 surface of the settings control plane.

``create_settings_v2_router`` wires three endpoints:

* ``GET /api/v2/settings/schema``       - public, no secrets;
* ``GET /api/v2/settings/server``       - public, non-secret values;
* ``PATCH /api/v2/settings/server``     - existing admin-key auth, atomic.

No WebSocket parser lives here; the structured :class:`PatchResult` is what a
later SRV-040 handler projects into ``command.ack``.
"""

from typing import Optional

from .control_plane import SettingsControlPlane
from .metadata import APP_VERSION
from .model import PatchResult


def create_settings_v2_router(
    control_plane: SettingsControlPlane,
    admin_auth_error,
    *,
    server_version: str = APP_VERSION,
    server_commit: Optional[str] = None,
):
    """Returns an `APIRouter`; FastAPI imports stay lazy for pure unit runs."""

    from fastapi import APIRouter, Request
    from fastapi.responses import JSONResponse

    if server_commit is None:
        from .metadata import resolve_server_commit

        server_commit = resolve_server_commit()

    router = APIRouter(prefix="/api/v2/settings")

    @router.get("/schema")
    async def settings_schema():
        return JSONResponse(
            control_plane.schema_payload(
                server_version=server_version,
                server_commit=server_commit,
            )
        )

    @router.get("/server")
    async def server_settings():
        return JSONResponse(
            control_plane.server_public(server_commit=server_commit)
        )

    @router.patch("/server")
    async def patch_server_settings(payload: dict, request: Request):
        auth_error = admin_auth_error(request)
        if auth_error is not None:
            return auth_error
        if not isinstance(payload, dict):
            return JSONResponse(
                {
                    "accepted": False,
                    "result": "settings_rejected",
                    "errors": [
                        {
                            "field": "body",
                            "code": "invalid_payload",
                            "message": "Der Patch muss ein JSON-Objekt sein.",
                        }
                    ],
                },
                status_code=400,
            )
        result: PatchResult = control_plane.patch_server(
            payload.get("baseSettingsRevision"),
            payload.get("changes"),
            server_commit=server_commit,
        )
        return JSONResponse(
            _redacted_for(control_plane.registry, result.to_dict()),
            status_code=_status_for(result),
        )

    return router


def _redacted_for(registry, payload):
    """Removes secret runtime values from every response section."""
    result = dict(payload)
    for section in ("values", "effectiveValues"):
        values = result.get(section)
        if not isinstance(values, dict):
            continue
        result[section] = {
            key: value
            for key, value in values.items()
            if not registry.is_secret(key)
        }
        redacted = [
            key for key in values if registry.is_secret(key)
        ]
        if redacted:
            result.setdefault("redactedKeys", [])
            result["redactedKeys"].extend(sorted(redacted))
    return result


def _status_for(result: PatchResult) -> int:
    if result.result == "settings_revision_conflict":
        return 409
    if result.result == "settings_rejected":
        return 422
    return 200