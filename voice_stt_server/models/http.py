"""Additive HTTP projections of the one service/model authority.

Registration imports FastAPI lazily. This module never constructs an app,
scheduler, settings store, license verifier or model manager.
"""
import asyncio

from .downloads import ModelManagementError
from .inventory import project_inventory


def register_model_routes(app, service, admin_auth_error, identity):
    from fastapi import Request
    from fastapi.responses import JSONResponse

    def error(exc):
        return JSONResponse({"error": {"code": exc.code}}, status_code=exc.status)

    @app.get("/api/v2/stt/models")
    async def models(request: Request):
        return JSONResponse(project_inventory(service.stt_model_manager,
                                               admin=admin_auth_error(request) is None))

    @app.post("/api/v2/stt/models/refresh")
    async def refresh(request: Request):
        refused = admin_auth_error(request)
        if refused is not None:
            return refused
        try:
            await asyncio.to_thread(service.refresh_stt_inventory)
            return JSONResponse(project_inventory(service.stt_model_manager, admin=True))
        except ModelManagementError as exc:
            return error(exc)

    @app.post("/api/v2/stt/models/{model_id}/download")
    async def download(model_id: str, request: Request):
        refused = admin_auth_error(request)
        if refused is not None:
            return refused
        try:
            payload, created = service.stt_model_manager.downloads.enqueue(model_id)
            return JSONResponse(payload, status_code=202 if created else 200)
        except ModelManagementError as exc:
            return error(exc)

    @app.get("/api/v2/stt/downloads")
    async def downloads(request: Request):
        refused = admin_auth_error(request)
        if refused is not None:
            return refused
        return JSONResponse({"jobs": service.stt_model_manager.downloads.snapshot()})

    @app.get("/api/v2/stt/downloads/{job_id}")
    async def download_status(job_id: str, request: Request):
        refused = admin_auth_error(request)
        if refused is not None:
            return refused
        try:
            return JSONResponse(service.stt_model_manager.downloads.snapshot(job_id))
        except ModelManagementError as exc:
            return error(exc)

    @app.post("/api/v2/stt/downloads/{job_id}/cancel")
    async def cancel(job_id: str, request: Request):
        refused = admin_auth_error(request)
        if refused is not None:
            return refused
        try:
            return JSONResponse(service.stt_model_manager.downloads.cancel(job_id))
        except ModelManagementError as exc:
            return error(exc)

    @app.delete("/api/v2/stt/installations/{installation_id}")
    async def delete(installation_id: str, request: Request):
        refused = admin_auth_error(request)
        if refused is not None:
            return refused
        try:
            result = await asyncio.to_thread(service.delete_stt_installation, installation_id)
            return JSONResponse(result)
        except ModelManagementError as exc:
            return error(exc)

    @app.get("/api/v2/server/status")
    async def status(request: Request):
        return JSONResponse(await asyncio.to_thread(service.server_status, identity,
                             admin=admin_auth_error(request) is None),
                             headers={"Cache-Control": "no-store"})
