"""Single facade for four independent VoiceSTT security mechanisms.

Keep protocol-specific choices separate: HTTP admin, OpenAI Bearer, scoped
log tokens and Kroko's external product license are NOT interchangeable.
"""

from .admin import AdminGate
from .kroko import KrokoLicenseGate
from .logs import LogGate, LogTokenAuthority
from .openai import OpenAIGate


class SecurityService:
    def __init__(self, settings):
        self.admin = AdminGate(settings)
        self.openai = OpenAIGate(settings)
        self.log_tokens = LogTokenAuthority()
        self.logs = LogGate(self.admin, self.log_tokens)
        self.kroko = KrokoLicenseGate()

    def admin_http_error(self, request):
        return self.admin.http_error(request)

    def admin_key_matches(self, supplied):
        return self.admin.key_matches(supplied)

    def openai_http_error(self, request, *, audit, normalize_client_id):
        return self.openai.http_error(
            request, audit=audit, normalize_client_id=normalize_client_id
        )

    def log_http_scope(self, request, requested_session_id=None):
        return self.logs.http_scope(request, requested_session_id)

    def log_websocket_scope(self, token, requested_session_id=None):
        return self.logs.websocket_scope(token, requested_session_id)
