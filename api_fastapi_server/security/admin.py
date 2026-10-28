"""Administrative API gate; preserves the existing local-only no-key policy."""

import os
import secrets

from fastapi.responses import JSONResponse

LOCAL_ADMIN_HOSTS = frozenset({"127.0.0.1", "::1", "localhost", "testclient"})


class AdminGate:
    def __init__(self, settings):
        self.settings = settings

    def configured_key(self):
        return self.settings.admin_api_key or os.getenv("VOICESTT_ADMIN_API_KEY")

    def key_matches(self, supplied):
        configured = self.configured_key()
        if not configured or supplied is None:
            return False
        return secrets.compare_digest(str(supplied), str(configured))

    def http_error(self, request):
        configured = self.configured_key()
        supplied = request.headers.get("x-voicestt-admin-key")
        authorization = request.headers.get("authorization", "")
        if not supplied and authorization.startswith("Bearer "):
            supplied = authorization[7:]
        if not supplied:
            supplied = request.headers.get("x-admin-key")
        if configured:
            if not self.key_matches(supplied):
                return JSONResponse(
                    {"error": "Admin-Authentifizierung erforderlich."},
                    status_code=401,
                    headers={"WWW-Authenticate": "Bearer"},
                )
            return None
        client_host = getattr(getattr(request, "client", None), "host", "")
        if client_host not in LOCAL_ADMIN_HOSTS:
            return JSONResponse(
                {"error": "Die Remote-Verwaltung ist deaktiviert, bis VOICESTT_ADMIN_API_KEY gesetzt ist."},
                status_code=403,
            )
        return None
