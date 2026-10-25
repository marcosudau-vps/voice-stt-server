"""Session-scoped log tokens and separate HTTP/WebSocket authorization policies."""

import threading
import time
import uuid

LOCAL_ADMIN_HOSTS = frozenset({"127.0.0.1", "::1", "localhost", "testclient"})
TOKEN_LIFETIME_SECONDS = 24 * 60 * 60


class LogTokenAuthority:
    """Volatile, per-server tokens; no filesystem/DB persistence."""

    def __init__(self, *, clock=None):
        self._lock = threading.RLock()
        self._tokens = {}
        self._clock = clock if clock is not None else lambda: time.time()

    def issue(self, session_id):
        token = uuid.uuid4().hex + uuid.uuid4().hex
        expires_at = self._clock() + TOKEN_LIFETIME_SECONDS
        with self._lock:
            now = self._clock()
            self._tokens = {
                existing: record
                for existing, record in self._tokens.items()
                if record["expiresAt"] > now
            }
            self._tokens[token] = {
                "sessionId": session_id,
                "expiresAt": expires_at,
            }
        return token, expires_at

    def validate(self, token, session_id=None):
        if not token:
            return None
        with self._lock:
            value = str(token)
            record = self._tokens.get(value)
            if record is None or record["expiresAt"] <= self._clock():
                self._tokens.pop(value, None)
                return None
            if session_id and record["sessionId"] != session_id:
                return None
            return dict(record)


class LogGate:
    def __init__(self, admin, tokens):
        self.admin = admin
        self.tokens = tokens

    def http_scope(self, request, requested_session_id=None):
        authorization = request.headers.get("authorization", "")
        supplied = request.headers.get("x-voicestt-admin-key")
        bearer = authorization[7:] if authorization.startswith("Bearer ") else ""
        supplied = supplied or bearer
        if self.admin.configured_key() and self.admin.key_matches(supplied):
            return {"admin": True, "sessionId": requested_session_id}
        client_host = getattr(getattr(request, "client", None), "host", "")
        if not self.admin.configured_key() and client_host in LOCAL_ADMIN_HOSTS:
            return {"admin": True, "sessionId": requested_session_id}
        token = request.headers.get("x-voicestt-log-token") or bearer
        access = self.tokens.validate(token, requested_session_id)
        if access is None:
            return None
        return {"admin": False, "sessionId": access["sessionId"]}

    def websocket_scope(self, token, requested_session_id=None):
        # Unlike HTTP log history, the existing WebSocket contract does NOT
        # give loopback clients implicit admin scope when no admin key exists.
        is_admin = bool(self.admin.configured_key() and self.admin.key_matches(token))
        access = None if is_admin else self.tokens.validate(token, requested_session_id)
        if not is_admin and access is None:
            return None
        return {
            "admin": is_admin,
            "sessionId": requested_session_id if is_admin else access["sessionId"],
        }
