"""OpenAI-compatible API key gate with unchanged HTTP/audit semantics."""

import os

from fastapi.responses import JSONResponse

from VoiceSTT_server.openai_compat import openai_error


class OpenAIGate:
    def __init__(self, settings):
        self.settings = settings

    def configured_key(self):
        return self.settings.openai_api_key or os.getenv("VOICESTT_API_KEY")

    def http_error(self, request, *, audit, normalize_client_id):
        configured = self.configured_key()
        if not configured:
            return None
        if request.headers.get("authorization", "") == f"Bearer {configured}":
            return None
        supplied_client_id = request.headers.get("x-voicestt-client-id")
        audit.event(
            "authentication.failed",
            transport="http",
            clientId=(normalize_client_id(supplied_client_id) if supplied_client_id else None),
            path=request.url.path,
            reason="invalid_api_key",
        )
        return JSONResponse(
            openai_error("Der angegebene API-Schlüssel ist ungültig.", code="invalid_api_key"),
            status_code=401,
            headers={"WWW-Authenticate": "Bearer"},
        )
