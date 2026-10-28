"""Explicit adapter for Kroko On-Premise model license checks.

No calls are made on construction. In particular this is not an endpoint
authentication method, entitlement for unrelated model ids or model loader.

Lifecycle use (``evaluate``/``refresh``) keeps the same rule: no network
without a key or while community is forced, stale generations never restore a
grant, and synchronous network I/O must stay out of the ASGI event loop -
callers choose ``background=True`` there.

Operator intent (effective key, force-community) is bound **only** by the
caller that currently owns it, synchronously, when a decision is requested.
A network worker never binds anything: it carries the generation token it was
started with and can only apply to exactly that generation. A late answer
therefore can neither resurrect an old key/force value nor grant a model after
a newer intent superseded the check.
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
        # Serialises "bind current intent + decide + start check" so two
        # callers cannot interleave their bind/begin pair.
        self._decision_lock = threading.Lock()
        self._background_lock = threading.Lock()
        self._background_inflight = set()

    # -- explicit, model-scoped network check ---------------------------------

    def check_model(self, model_uuid, *, options=None, force_community=False,
                    connect=None, timeout=DEFAULT_CHECK_TIMEOUT):
        """Run an *explicit* model-scoped check, never a startup side effect."""
        key = effective_recognizer_key(options)
        with self._decision_lock:
            self.state.bind(key=str(key or ""), force_community=force_community)
            token = self.state.begin(str(model_uuid))
        if token is None:
            return LicenseCheckResult("NOT_CHECKED", reason=(
                "force_community" if force_community else "no_key"
            ))
        return self._execute(token, str(model_uuid), str(key), connect, timeout)

    def _execute(self, token, model_uuid, key, connect, timeout):
        """Network round trip + generation-bound apply. Never binds intent."""
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

    # -- decisions -------------------------------------------------------------

    def current_decision(self, model_uuid):
        """Read-only projection of the *current* state for one model UUID.

        Binds nothing. Used after asynchronous work, where the arguments the
        work was started with are by definition not authoritative any more.
        """
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
        if not snapshot["keyPresent"]:
            return {
                "tier": "community",
                "model_uuid": uuid_text,
                "reason": "no_key",
                "check_required": False,
                "snapshot": snapshot,
            }
        if snapshot["forceCommunity"]:
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

    def decide(self, model_uuid, *, options=None, force_community=False):
        """Synchronous, network-free policy decision for one model UUID.

        Binds the effective key/mode first (invalidating superseded proofs),
        then reports ``pro`` only for a fresh, model-bound VALID proof,
        ``checking`` while this model's check is in flight, otherwise
        ``community`` with the reason (``no_key``, ``force_community`` or the
        last check outcome, plus ``check_required`` when a check makes sense).
        """
        key = effective_recognizer_key(options)
        with self._decision_lock:
            self.state.bind(
                key=str(key or ""), force_community=bool(force_community)
            )
            return self.current_decision(model_uuid)

    def bind_intent(self, *, options=None, force_community=False):
        """Bind the effective key/mode without a model (instant lockout)."""
        key = effective_recognizer_key(options)
        with self._decision_lock:
            return self.state.bind(
                key=str(key or ""), force_community=bool(force_community)
            )

    def prepare(self, model_uuid, *, options=None, force_community=False):
        """Bind the current intent and start the generation - no network.

        Returns ``(decision, plan)``. ``plan`` is ``None`` when nothing has to
        be asked of the license server (already entitled, in flight, no key,
        forced Community). Callers that derive key/force from mutable
        settings hold their own lock around this call, so that reading the
        intent and binding it cannot interleave with a newer intent.
        """
        uuid_text = str(model_uuid or "")
        key = effective_recognizer_key(options)
        key_text = str(key or "")
        with self._decision_lock:
            self.state.bind(key=key_text, force_community=bool(force_community))
            decision = self.current_decision(uuid_text)
            if decision["tier"] != "community" or not decision["check_required"]:
                return decision, None
            token = self.state.begin(uuid_text)
        if token is None:
            return self.current_decision(uuid_text), None
        return decision, (token, uuid_text, key_text)

    def run(self, decision, plan, *, connect=None, timeout=DEFAULT_CHECK_TIMEOUT,
            background=False, on_result=None):
        """Execute a plan from :meth:`prepare`; ``(decision, started)``."""
        if plan is None:
            return decision, False
        token, uuid_text, key_text = plan
        if background:
            with self._background_lock:
                self._background_inflight.add(token)
            worker = threading.Thread(
                target=self._background_check,
                args=(token, uuid_text, key_text, connect, timeout, on_result),
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
            result = self._execute(token, uuid_text, key_text, connect, timeout)
        finally:
            if on_result is not None:
                try:
                    on_result(self.current_decision(uuid_text))
                except Exception:
                    pass
        final = self.current_decision(uuid_text)
        final["result"] = result.status
        final["result_reason"] = result.reason
        return final, True

    def refresh(self, model_uuid, *, options=None, force_community=False,
                connect=None, timeout=DEFAULT_CHECK_TIMEOUT,
                background=False, on_result=None):
        """Ensure a fresh check unless already entitled, barred or in flight.

        Returns ``(decision, started)`` where ``started`` tells whether a
        network check was launched. The bind of the current intent and the
        start of the generation (``begin``) happen synchronously in the
        calling thread; with ``background=True`` only the network round trip
        runs on a daemon thread and ``on_result(decision)`` is invoked
        afterwards with the **current** state (callback errors never
        propagate). Otherwise the call blocks for at most one bounded round
        trip. Overlapping refreshes never confirm each other: only the latest
        generation can apply, older answers are discarded as
        ``stale_generation``.
        """
        decision, plan = self.prepare(
            model_uuid, options=options, force_community=force_community
        )
        return self.run(
            decision, plan, connect=connect, timeout=timeout,
            background=background, on_result=on_result,
        )

    def _background_check(self, token, model_uuid, key, connect, timeout,
                          on_result):
        try:
            self._execute(token, model_uuid, key, connect, timeout)
        except Exception:
            pass
        finally:
            with self._background_lock:
                self._background_inflight.discard(token)
        if on_result is not None:
            try:
                on_result(self.current_decision(model_uuid))
            except Exception:
                pass
