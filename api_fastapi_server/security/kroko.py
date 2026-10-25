"""Explicit adapter for Kroko On-Premise model license checks.

No calls are made on construction. In particular this is not an endpoint
authentication method, entitlement for unrelated model ids or model loader.

Lifecycle use (``evaluate``/``refresh``) keeps the same rule: no network
without a key or while community is forced, stale generations never restore a
grant, and synchronous network I/O must stay out of the ASGI event loop -
callers choose ``background=True`` there.
"""

import threading

from VoiceSTT.kroko.credentials import effective_recognizer_key
from VoiceSTT.kroko.license_api import LicenseCheckResult, check_onprem_license
from VoiceSTT.kroko.license_state import KrokoLicenseState

#: Bounded default for one license-server round trip. Callers may override
#: per call; there is no endless retry inside the gate.
DEFAULT_CHECK_TIMEOUT = 5.0


class KrokoLicenseGate:
    def __init__(self):
        self.state = KrokoLicenseState()
        self._background_lock = threading.Lock()
        self._background_inflight = set()

    def check_model(self, model_uuid, *, options=None, force_community=False,
                    connect=None, timeout=DEFAULT_CHECK_TIMEOUT):
        """Run an *explicit* model-scoped check, never a startup side effect."""
        key = effective_recognizer_key(options)
        self.state.bind(key=str(key or ""), force_community=force_community)
        token = self.state.begin(str(model_uuid))
        if token is None:
            return LicenseCheckResult("NOT_CHECKED", reason=(
                "force_community" if force_community else "no_key"
            ))
        result = check_onprem_license(
            str(key), str(model_uuid), timeout=timeout, connect=connect
        )
        if result.model_uuid != str(model_uuid):
            # Never publish (or return as valid) a check for another model.
            result = LicenseCheckResult(
                "CHECK_FAILED", str(model_uuid), reason="model_scope_mismatch"
            )
        if not self.state.apply(token, result):
            # A concurrent key/mode/check invalidated the pending generation.
            return LicenseCheckResult(
                "CHECK_FAILED", str(model_uuid), reason="stale_generation"
            )
        return result

    def decide(self, model_uuid, *, options=None, force_community=False):
        """Synchronous, network-free policy decision for one model UUID.

        Binds the effective key/mode first (invalidating superseded proofs),
        then reports ``pro`` only for a fresh, model-bound VALID proof,
        ``checking`` while this model's check is in flight, otherwise
        ``community`` with the reason (``no_key``, ``force_community`` or the
        last check outcome, plus ``check_required`` when a check makes sense).
        """
        key = effective_recognizer_key(options)
        key_text = str(key or "")
        self.state.bind(key=key_text, force_community=force_community)
        uuid_text = str(model_uuid or "")
        snapshot = self.state.public_snapshot()
        if self.state.pro_enabled_for(uuid_text):
            return {
                "tier": "pro",
                "model_uuid": uuid_text,
                "reason": "license_valid",
                "check_required": False,
                "snapshot": self.state.public_snapshot(),
            }
        if (snapshot["status"] == "CHECKING"
                and snapshot["modelUuid"] == uuid_text):
            return {
                "tier": "checking",
                "model_uuid": uuid_text,
                "reason": "check_in_progress",
                "check_required": False,
                "snapshot": snapshot,
            }
        if not key_text.strip():
            return {
                "tier": "community",
                "model_uuid": uuid_text,
                "reason": "no_key",
                "check_required": False,
                "snapshot": snapshot,
            }
        if force_community:
            return {
                "tier": "community",
                "model_uuid": uuid_text,
                "reason": "force_community",
                "check_required": False,
                "snapshot": snapshot,
            }
        return {
            "tier": "community",
            "model_uuid": uuid_text,
            "reason": snapshot["reasonCode"],
            "check_required": True,
            "snapshot": snapshot,
        }

    def refresh(self, model_uuid, *, options=None, force_community=False,
                connect=None, timeout=DEFAULT_CHECK_TIMEOUT,
                background=False, on_result=None):
        """Ensure a fresh check unless already entitled, barred or in flight.

        Returns ``(decision, started)`` where ``started`` tells whether a
        network check was launched. With ``background=True`` the check runs on
        a daemon thread and ``on_result(decision)`` is invoked afterwards
        (callback errors never propagate); otherwise the call blocks for at
        most one bounded round trip. Overlapping refreshes never confirm each
        other: only the latest generation can apply, older answers are
        discarded as ``stale_generation``.
        """
        decision = self.decide(
            model_uuid, options=options, force_community=force_community
        )
        if decision["tier"] != "community" or not decision["check_required"]:
            return decision, False
        uuid_text = str(model_uuid or "")
        request_options = dict(options or {})
        if background:
            with self._background_lock:
                if uuid_text in self._background_inflight:
                    inflight = dict(decision)
                    inflight["tier"] = "checking"
                    inflight["reason"] = "check_in_progress"
                    inflight["check_required"] = False
                    return inflight, False
                self._background_inflight.add(uuid_text)
            worker = threading.Thread(
                target=self._background_check,
                args=(uuid_text, request_options, bool(force_community),
                      connect, timeout, on_result),
                name="KrokoLicenseCheck",
                daemon=True,
            )
            worker.start()
            started = dict(decision)
            started["tier"] = "checking"
            started["reason"] = "check_in_progress"
            started["check_required"] = False
            return started, True
        try:
            result = self.check_model(
                uuid_text, options=request_options,
                force_community=bool(force_community), connect=connect,
                timeout=timeout,
            )
        finally:
            if on_result is not None:
                try:
                    on_result(self.decide(
                        uuid_text, options=request_options,
                        force_community=bool(force_community),
                    ))
                except Exception:
                    pass
        final = self.decide(
            uuid_text, options=request_options,
            force_community=bool(force_community),
        )
        final["result"] = result.status
        final["result_reason"] = result.reason
        return final, True

    def _background_check(self, model_uuid, options, force_community,
                          connect, timeout, on_result):
        try:
            self.check_model(
                model_uuid, options=options,
                force_community=force_community, connect=connect,
                timeout=timeout,
            )
        except Exception:
            pass
        finally:
            with self._background_lock:
                self._background_inflight.discard(model_uuid)
        if on_result is not None:
            try:
                on_result(self.decide(
                    model_uuid, options=options,
                    force_community=force_community,
                ))
            except Exception:
                pass
