"""Opt-in, model-scoped on-prem Kroko license probe.

This is NOT the hosted STT API. It does not activate a recognizer, infer
rights to other models or automatically change the running server. The
provider's websocket reporting/connection lifecycle still needs qualification
before wiring a short-lived probe into production model admission.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import quote
from uuid import UUID


@dataclass(frozen=True)
class LicenseCheckResult:
    status: str  # NOT_CHECKED | VALID | INVALID | CHECK_FAILED
    model_uuid: str = ""
    max_age_seconds: float = 0.0
    reason: str = ""

    @property
    def allowed(self) -> bool:
        return self.status == "VALID" and self.max_age_seconds > 0


def check_onprem_license(
    key: str,
    model_uuid: str,
    *,
    timeout: float = 5.0,
    connect: Callable[..., Any] | None = None,
) -> LicenseCheckResult:
    """Read one license-server response for *one* explicitly selected model.

    No exceptions, transport details, URLs or raw provider responses escape:
    websocket errors could otherwise embed the key in the path. Only a typed
    positive reply with a bounded freshness period can return VALID.
    Connection and reporting semantics are *not* a verified product contract.
    """
    if not isinstance(key, str) or not key.strip():
        return LicenseCheckResult("NOT_CHECKED", reason="no_key")
    try:
        model = str(UUID(str(model_uuid)))
        timeout = float(timeout)
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("bad timeout")
    except (ValueError, TypeError, AttributeError, OverflowError):
        return LicenseCheckResult("CHECK_FAILED", reason="invalid_request")
    socket = None
    try:
        if connect is None:
            from websocket import create_connection
            connect = create_connection
        url = "wss://license.kroko.ai/ws/v1/{}/{}".format(
            quote(key, safe=""), model
        )
        socket = connect(url, timeout=timeout)
        payload = socket.recv()
        reply = json.loads(payload)
        if not isinstance(reply, dict) or type(reply.get("allowed")) is not bool:
            return LicenseCheckResult("CHECK_FAILED", model, reason="invalid_reply")
        if reply["allowed"] is False:
            return LicenseCheckResult("INVALID", model, reason="license_rejected")
        # A superficially positive answer carrying a provider error is not proof.
        error = reply.get("error", "")
        if not isinstance(error, str) or error not in ("", "no"):
            return LicenseCheckResult("CHECK_FAILED", model, reason="invalid_reply")
        seconds = reply.get("remaining_seconds")
        offline = reply.get("offline_timeout")
        if (type(seconds) is not int or seconds <= 0
                or type(offline) is not int or offline <= 0):
            return LicenseCheckResult("CHECK_FAILED", model, reason="invalid_freshness")
        # A short-lived observation, not a renewable or transferable grant.
        age = float(min(seconds, offline, 60))
        return LicenseCheckResult("VALID", model, age, "ok")
    except Exception:
        return LicenseCheckResult("CHECK_FAILED", model, reason="transport_or_parse_error")
    finally:
        if socket is not None:
            try:
                socket.close()
            except Exception:
                pass


__all__ = ["LicenseCheckResult", "check_onprem_license"]
