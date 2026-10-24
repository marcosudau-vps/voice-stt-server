"""Adapter for the versioned, redacted native status snapshot.

No protocol implementation and no activation. The snapshot comes from the
native singleton in the current serving owner after explicit model loading.
"""
import json
import math
import sys
from .license_runtime import LicenseVerifier, LicenseVerdict


class NativeStatusVerifier(LicenseVerifier):
    def __init__(self, snapshot, model_ids):
        self._snapshot = snapshot
        self._model_ids = dict(model_ids)  # native header UUID -> manifested id

    def verify(self, request):
        failed = LicenseVerdict(outcome="unreachable")
        if not request.key_present or not request.owner_generation:
            return failed
        try:
            data = self._snapshot()
            if isinstance(data, str):
                data = json.loads(data)
            if (type(data.get("schemaVersion")) is not int or data["schemaVersion"] != 1
                    or data.get("ownerGeneration") != request.owner_generation):
                return failed
            model_id = self._model_ids.get(data.get("modelId"))
            if not model_id or model_id not in request.candidate_model_ids:
                return failed
            if data.get("outcome") == "rejected":
                return LicenseVerdict(outcome="rejected", reason_code="license_rejected")
            if data.get("outcome") != "granted":
                return failed
            age = data["proofAgeSeconds"]
            ttl = data["maxProofAgeSeconds"]
            if (type(age) not in (int, float) or type(ttl) not in (int, float)
                    or not math.isfinite(age) or not math.isfinite(ttl)
                    or not 0 <= age < ttl <= 60):
                return failed
            # Reading the same snapshot cannot renew a proof's absolute deadline.
            return LicenseVerdict(outcome="granted", validated_model_ids=(model_id,),
                                  max_age_seconds=ttl-age, reason_code="ok")
        except Exception:
            return failed


def loaded_snapshot_reader():
    """Find only the already loaded native extension; never activate/import Pro."""
    module = sys.modules.get("_sherpa_onnx")
    reader = getattr(module, "voicestt_license_status_v1", None)
    return reader if callable(reader) else None


_binary_identity = None


def loaded_runtime_identity():
    """Bind the selected extension bytes, never a key or arbitrary module name."""
    global _binary_identity
    from importlib.machinery import EXTENSION_SUFFIXES
    from pathlib import Path
    import hashlib
    module = sys.modules.get("_sherpa_onnx")
    origin = str(getattr(module, "__file__", ""))
    if not any(origin.endswith(suffix) for suffix in EXTENSION_SUFFIXES):
        return None
    try:
        path = Path(origin).resolve()
        from .bootstrap import selection_status
        selected = selection_status()
        if selected and not path.is_relative_to(Path(selected["root"]).resolve()):
            return None
        stat = path.stat()
        signature = (str(path), stat.st_size, stat.st_mtime_ns)
        if _binary_identity is not None:
            previous, identity = _binary_identity
            return identity if previous == signature else None
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        identity = "native:sha256:" + digest.hexdigest()
        _binary_identity = signature, identity
        return identity
    except OSError:
        return None
