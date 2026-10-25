"""Explicit adapter for Kroko On-Premise model license checks.

No calls are made on construction. In particular this is not an endpoint
authentication method, entitlement for unrelated model ids or model loader.
"""

from VoiceSTT.kroko.credentials import effective_recognizer_key
from VoiceSTT.kroko.license_api import LicenseCheckResult, check_onprem_license
from VoiceSTT.kroko.license_state import KrokoLicenseState


class KrokoLicenseGate:
    def __init__(self):
        self.state = KrokoLicenseState()

    def check_model(self, model_uuid, *, options=None, force_community=False,
                    connect=None):
        """Run an *explicit* model-scoped check, never a startup side effect."""
        key = effective_recognizer_key(options)
        self.state.bind(key=str(key or ""), force_community=force_community)
        token = self.state.begin(str(model_uuid))
        if token is None:
            return LicenseCheckResult("NOT_CHECKED", reason=(
                "force_community" if force_community else "no_key"
            ))
        result = check_onprem_license(
            str(key), str(model_uuid), connect=connect
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
