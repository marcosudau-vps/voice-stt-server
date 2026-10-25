"""Volatile, model-scoped Kroko license state without native/process ownership.

Operator intent belongs to existing settings; this object never persists
proofs or receives native handles. Network checking is explicit, not triggered
by constructing the state. An API result for one model cannot unlock others.
"""

from __future__ import annotations

import hashlib
import hmac
import math
import secrets
import threading
import time
from typing import Any, Callable

from .license_api import LicenseCheckResult

_REVISION_SECRET = secrets.token_bytes(32)


def _key_revision(key: str) -> str:
    if not key:
        return "none"
    return hmac.new(_REVISION_SECRET, key.encode("utf-8"), hashlib.sha256).hexdigest()


class KrokoLicenseState:
    def __init__(self, *, clock: Callable[[], float] = time.monotonic):
        self._lock = threading.RLock()
        self._clock = clock
        self._generation = 0
        self._revision = "none"
        self._key_present = False
        self._force_community = False
        self._model_uuid = ""
        self._status = "NOT_CHECKED"
        self._expires = 0.0
        self._reason = "no_key"

    def bind(self, *, key: str = "", force_community: bool = False) -> bool:
        """Invalidate the previous proof on a key or mode change."""
        revision = _key_revision(str(key or ""))
        present = bool(str(key or "").strip())
        with self._lock:
            if (revision, present, bool(force_community)) == (
                self._revision, self._key_present, self._force_community
            ):
                return False
            self._revision = revision
            self._key_present = present
            self._force_community = bool(force_community)
            self._generation += 1
            self._status = "NOT_CHECKED"
            self._model_uuid = ""
            self._expires = 0.0
            self._reason = "force_community" if force_community else (
                "key_changed" if present else "no_key"
            )
            return True

    def begin(self, model_uuid: str) -> int | None:
        """Start a generation-bound check; return token for apply()."""
        with self._lock:
            if not self._key_present or self._force_community:
                return None
            self._generation += 1
            self._model_uuid = str(model_uuid)
            self._status = "CHECKING"
            self._reason = "check_in_progress"
            self._expires = 0.0
            return self._generation

    def apply(self, token: int, result: LicenseCheckResult) -> bool:
        """Accept only a current, model-identical result from the latest check."""
        with self._lock:
            if (token != self._generation or self._status != "CHECKING"
                    or not isinstance(result, LicenseCheckResult)
                    or result.model_uuid != self._model_uuid):
                return False
            if result.allowed and (math.isfinite(result.max_age_seconds)
                                   and 0 < result.max_age_seconds <= 60):
                self._expires = self._clock() + result.max_age_seconds
                self._status = "VALID"
                self._reason = "ok"
            else:
                self._expires = 0.0
                self._status = ("INVALID" if result.status == "INVALID"
                                else "CHECK_FAILED")
                self._reason = result.reason if result.reason in {
                    "license_rejected", "invalid_reply", "invalid_freshness",
                    "transport_or_parse_error", "invalid_request"
                } else "check_failed"
            return True

    def _expire_locked(self) -> None:
        if self._status == "VALID" and self._clock() >= self._expires:
            self._status = "CHECK_FAILED"
            self._expires = 0.0
            self._reason = "proof_expired"

    def pro_enabled_for(self, model_uuid: str) -> bool:
        with self._lock:
            self._expire_locked()
            return (self._status == "VALID" and self._key_present
                    and not self._force_community and self._model_uuid == str(model_uuid))

    def public_snapshot(self) -> dict[str, Any]:
        """No key, credential fingerprint, native payload or provider text."""
        with self._lock:
            self._expire_locked()
            return {
                "status": self._status,
                "generation": self._generation,
                "proEnabled": self._status == "VALID" and not self._force_community,
                "modelUuid": self._model_uuid,
                "keyPresent": self._key_present,
                "forceCommunity": self._force_community,
                "reasonCode": self._reason,
            }


__all__ = ["KrokoLicenseState"]
