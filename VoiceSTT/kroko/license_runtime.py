"""Unified Kroko license/runtime authority (AP-KR-020 continuation).

This module owns the volatile, server-wide license and runtime state for the
shared Community/Pro runtime. It deliberately implements **no network access,
no native imports and no persistence**:

* The license *decision* (``pro_enabled``) is derived, never stored.
* Only the operator *intent* (``force_community`` and the requested models)
  is persisted, by the existing settings plane - never the active runtime,
  never a ``VALID`` proof.
* A ``VALID`` proof binds the configuration *generation*, an opaque credential
  revision, the installed payload identity and the explicitly confirmed model
  rights. It expires after a short, conservative bound (fail-closed).

Nothing in this module ever receives Kroko key material: callers pass only an
opaque, one-way credential fingerprint plus a presence flag. The secret itself
stays in the process environment and the engine options, exactly as before.

The product ships with :class:`UnqualifiedLicenseVerifier` only, which never
grants anything. Any future qualified verification backend (AP-KR-020
follow-up ``A``: versioned native status дополнение) plugs into
:meth:`LicenseRuntimeAuthority.run_check` behind the :class:`LicenseVerifier`
interface. Synthetic scripted verifiers exist exclusively in the test suite and
must never act as productive proof.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, Mapping, Optional, Tuple


class LicenseStatus(str, Enum):
    """The volatile license states of the unified Kroko runtime."""

    #: Cold start, no key, or community enforced: no check was ever attempted.
    NOT_CHECKED = "NOT_CHECKED"
    #: A check was requested and is running in this generation.
    CHECKING = "CHECKING"
    #: Current, generation-bound positive proof for explicit model rights.
    VALID = "VALID"
    #: Technical inconclusive outcome: unreachable, timeout, unqualified
    #: backend, expired proof. Never silently treated as permission.
    CHECK_FAILED = "CHECK_FAILED"
    #: Authoritative negative for this generation: rejected, revoked, expired
    #: license. Sticks until the intent (key/mode/identity) changes.
    INVALID = "INVALID"


#: Fixed, redacted-safe reason vocabulary. No free-form provider text, no key
#: material and no raw license responses ever enter snapshots or logs.
REASON_OK = "ok"
REASON_NO_KEY = "no_key"
REASON_FORCE_COMMUNITY = "force_community"
REASON_NO_QUALIFIED_VERIFIER = "no_qualified_verifier"
REASON_CHECK_IN_PROGRESS = "check_in_progress"
REASON_LICENSE_REJECTED = "license_rejected"
REASON_LICENSE_UNREACHABLE = "license_unreachable"
REASON_PROOF_EXPIRED = "proof_expired"
REASON_INTENT_CHANGED = "intent_changed"
REASON_UNQUALIFIED_MODEL = "unqualified_model"
REASON_STALE_GENERATION = "stale_generation"

#: Conservative upper bound for a positive license proof, in seconds.
#:
#: This is an explicit, conservative *interpretation* of the observed native
#: license semantics (``offline_timeout: 60`` in the 22.10.2026 probe result):
#: the provider itself stops trusting an offline client after 60 s, so a local
#: snapshot must never outlive that window without fresh confirmation. It is
#: NOT a provider-guaranteed freshness contract. Callers may pass a shorter
#: bound per verification; longer bounds are rejected.
DEFAULT_MAX_PROOF_AGE_SECONDS = 60.0

#: Kroko lane engine names that resolve models through the Kroko stack.
KROKO_ENGINE_NAMES = frozenset({"kroko", "kroko_onnx", "banafo_kroko"})


def normalize_engine_name(name: Any) -> str:
    """Normalizes an engine name for Kroko-lane detection (no imports)."""
    return str(name or "").strip().lower()


def is_kroko_lane(engine: Any) -> bool:
    """Whether an engine name selects the Kroko native stack."""
    return normalize_engine_name(engine) in KROKO_ENGINE_NAMES


def derive_credential_revision(key_value: Any) -> str:
    """Derives the opaque credential revision for key material.

    One-way SHA-256 fingerprint (``k:<hex16>``) or ``"none"`` when no key is
    configured. The digest changes on every key rotation, reveals nothing
    reversible, and is the only key-derived value that ever enters the
    authority, snapshots or logs. Callers must compute it at the secret
    boundary (settings plane) and never persist the key itself.
    """
    text = str(key_value or "")
    if not text.strip():
        return "none"
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    return "k:" + digest


def config_fingerprint(config: Mapping[str, Any]) -> str:
    """Stable fingerprint over non-secret runtime configuration.

    The mapping must be free of secret material (presence flags, opaque
    revisions and model ids only). Used to detect runtime-, key- and
    entitlement-relevant changes that require a new owner generation.
    """
    canonical = json.dumps(config, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _manifest_language(value: str) -> str:
    """Best-effort language token from a Kroko model filename (``Kroko-DE-…``)."""
    parts = str(value or "").split("-")
    if len(parts) >= 2 and parts[0].lower() == "kroko":
        token = "".join(ch for ch in parts[1] if ch.isalpha()).upper()
        if 2 <= len(token) <= 5:
            return token
    return ""


def community_fallback_model(manifest: Any, requested: Any):
    """Deterministic manifested community fallback for one request.

    Never reaches the network and never invents license rights: prefers a
    ``free`` entry matching the requested filename, then a ``free`` entry for
    the requested language, then the first ``free`` entry. Returns ``None``
    when the manifest holds no usable community model. Works on the real
    :class:`VoiceSTT.kroko.models.KrokoModelManifest` and on duck-typed
    fakes exposing ``get(value)`` and ``entries`` (test seam).
    """
    if manifest is None:
        return None
    get = getattr(manifest, "get", None)
    entries = getattr(manifest, "entries", None) or ()
    free = [entry for entry in entries
            if str(getattr(entry, "requires_runtime_variant", "") or "")
            .strip().lower() == "free"]
    if not free:
        return None
    if get is not None:
        try:
            direct = get(requested)
        except Exception:
            direct = None
        if direct is not None and direct in free:
            return direct
    language = _manifest_language(
        getattr(requested, "filename", requested)
        if not isinstance(requested, str) else requested)
    if language:
        for entry in free:
            if _manifest_language(
                    getattr(entry, "filename", "")) == language:
                return entry
    return free[0]


@dataclass(frozen=True)
class LicenseProof:
    """A generation-bound positive license proof (volatile only)."""

    generation: int
    credential_revision: str
    runtime_identity: str
    validated_model_ids: Tuple[str, ...]
    verified_at_monotonic: float
    max_age_seconds: float = DEFAULT_MAX_PROOF_AGE_SECONDS

    def is_current(self, *, now_monotonic: float, generation: int,
                   credential_revision: str,
                   runtime_identity: str) -> bool:
        """Pure freshness/binding check. Expired or rebound proofs are dead."""
        if self.generation != generation:
            return False
        if self.credential_revision != credential_revision:
            return False
        if self.runtime_identity != runtime_identity:
            return False
        age = now_monotonic - self.verified_at_monotonic
        if age < 0:
            return False
        return age <= self.max_age_seconds

    def age_seconds(self, now_monotonic: float) -> Optional[float]:
        """Age of the proof in seconds, or ``None`` for clock skew."""
        age = now_monotonic - self.verified_at_monotonic
        return age if age >= 0 else None


@dataclass(frozen=True)
class LicenseCheckRequest:
    """Input for a license verification backend (no key material)."""

    generation: int
    key_present: bool
    credential_revision: str
    runtime_identity: str
    candidate_model_ids: Tuple[str, ...] = ()


@dataclass(frozen=True)
class LicenseVerdict:
    """Structured outcome of one verification attempt."""

    outcome: str  # "granted" | "rejected" | "unreachable"
    validated_model_ids: Tuple[str, ...] = ()
    max_age_seconds: Optional[float] = None
    reason_code: str = REASON_LICENSE_UNREACHABLE

    def __post_init__(self):
        if self.outcome not in ("granted", "rejected", "unreachable"):
            raise ValueError(
                "LicenseVerdict.outcome must be granted, rejected or unreachable"
            )


class LicenseVerifier(ABC):
    """Interface for license verification backends (testable seam)."""

    @abstractmethod
    def verify(self, request: LicenseCheckRequest) -> LicenseVerdict:
        """Performs one model-bound verification for the request generation."""
        raise NotImplementedError


class UnqualifiedLicenseVerifier(LicenseVerifier):
    """Product default: no qualified verification backend exists (yet).

    Always answers ``unreachable`` with ``no_qualified_verifier`` so the
    authority stays fail-closed (``CHECK_FAILED`` -> Community). Granting
    anything here would be an unqualified license release.
    """

    def verify(self, request: LicenseCheckRequest) -> LicenseVerdict:
        return LicenseVerdict(
            outcome="unreachable",
            reason_code=REASON_NO_QUALIFIED_VERIFIER,
        )


class LicenseRuntimeAuthority:
    """Central, volatile license/runtime authority (thread-safe).

    Holds only derived state: status, configuration generation, opaque
    credential revision, payload identity, confirmed model rights and proof
    age. Key presence/force flags arrive per intent update; key material
    never enters this object.
    """

    def __init__(
        self,
        *,
        max_proof_age_seconds: float = DEFAULT_MAX_PROOF_AGE_SECONDS,
        time_fn: Callable[[], float] = time.monotonic,
    ):
        if not max_proof_age_seconds > 0:
            raise ValueError("max_proof_age_seconds must be positive")
        self._max_age = float(max_proof_age_seconds)
        self._time_fn = time_fn
        self._lock = threading.RLock()
        self._generation = 0
        self._status = LicenseStatus.NOT_CHECKED
        self._reason = REASON_OK
        self._key_present = False
        self._force_community = False
        self._credential_revision = "none"
        self._runtime_identity = "unmanaged-global-runtime"
        self._proof: Optional[LicenseProof] = None

    # -- intent -----------------------------------------------------------

    def note_intent(self, *, key_present: bool, force_community: bool,
                    credential_revision: str,
                    runtime_identity: str) -> bool:
        """Records operator intent; bumps the generation on any change.

        Any change atomically discards the previous proof: old
        statuses, readiness messages and job results bound to the previous
        generation must never authorize the new one. Returns whether the
        generation changed.
        """
        credential_revision = str(credential_revision or "none")
        runtime_identity = str(runtime_identity or "unmanaged-global-runtime")
        with self._lock:
            changed = (
                bool(key_present) != self._key_present
                or bool(force_community) != self._force_community
                or credential_revision != self._credential_revision
                or runtime_identity != self._runtime_identity
            )
            self._key_present = bool(key_present)
            self._force_community = bool(force_community)
            self._credential_revision = credential_revision
            self._runtime_identity = runtime_identity
            if changed:
                self._generation += 1
                self._proof = None
                self._status = LicenseStatus.NOT_CHECKED
                self._reason = REASON_INTENT_CHANGED
            return changed

    @property
    def generation(self) -> int:
        """Current configuration generation (monotonic, volatile)."""
        with self._lock:
            return self._generation

    # -- checks -----------------------------------------------------------

    def begin_check(self) -> Tuple[bool, str]:
        """Requests a verification for the current generation.

        ``INVALID`` (authoritative negative) sticks until the intent changes;
        blind retries without an intent change are refused. Returns
        ``(accepted, reason_code)``.
        """
        with self._lock:
            if self._status == LicenseStatus.VALID:
                return True, REASON_OK
            if not self._key_present:
                self._status = LicenseStatus.NOT_CHECKED
                self._reason = REASON_NO_KEY
                return False, REASON_NO_KEY
            if self._force_community:
                self._status = LicenseStatus.NOT_CHECKED
                self._reason = REASON_FORCE_COMMUNITY
                return False, REASON_FORCE_COMMUNITY
            if self._status == LicenseStatus.INVALID:
                return False, REASON_LICENSE_REJECTED
            self._status = LicenseStatus.CHECKING
            self._reason = REASON_CHECK_IN_PROGRESS
            return True, REASON_CHECK_IN_PROGRESS

    def record_success(self, validated_model_ids,
                       max_age_seconds: Optional[float] = None) -> bool:
        """Records a positive proof; only accepted while ``CHECKING``."""
        ids = tuple(str(item) for item in (validated_model_ids or ()))
        if not ids:
            return False
        bound = self._max_age if max_age_seconds is None else float(
            max_age_seconds)
        if bound <= 0 or bound > self._max_age:
            return False
        with self._lock:
            if self._status != LicenseStatus.CHECKING:
                return False
            self._proof = LicenseProof(
                generation=self._generation,
                credential_revision=self._credential_revision,
                runtime_identity=self._runtime_identity,
                validated_model_ids=ids,
                verified_at_monotonic=self._time_fn(),
                max_age_seconds=bound,
            )
            self._status = LicenseStatus.VALID
            self._reason = REASON_OK
            return True

    def record_rejection(self,
                         reason_code: str = REASON_LICENSE_REJECTED) -> bool:
        """Records an authoritative negative for this generation."""
        with self._lock:
            if self._status != LicenseStatus.CHECKING:
                return False
            self._proof = None
            self._status = LicenseStatus.INVALID
            self._reason = str(reason_code or REASON_LICENSE_REJECTED)
            return True

    def record_failure(self,
                       reason_code: str = REASON_LICENSE_UNREACHABLE) -> bool:
        """Records an inconclusive outcome (fail-closed, retryable)."""
        with self._lock:
            if self._status not in (LicenseStatus.CHECKING,
                                    LicenseStatus.VALID):
                return False
            self._proof = None
            self._status = LicenseStatus.CHECK_FAILED
            self._reason = str(reason_code or REASON_LICENSE_UNREACHABLE)
            return True

    def run_check(self, verifier: LicenseVerifier,
                  candidate_model_ids=()) -> LicenseStatus:
        """Runs one full check through a verifier backend.

        The verifier call happens outside the lock; a verdict for a
        superseded generation is discarded (stale-generation guard).
        """
        accepted, _ = self.begin_check()
        if not accepted:
            return self.status
        with self._lock:
            request = LicenseCheckRequest(
                generation=self._generation,
                key_present=self._key_present,
                credential_revision=self._credential_revision,
                runtime_identity=self._runtime_identity,
                candidate_model_ids=tuple(
                    str(item) for item in (candidate_model_ids or ())),
            )
        verdict = verifier.verify(request)
        with self._lock:
            if request.generation != self._generation:
                self._reason = REASON_STALE_GENERATION
                return self._status
            if self._status != LicenseStatus.CHECKING:
                return self._status
        if verdict.outcome == "granted":
            self.record_success(verdict.validated_model_ids,
                                verdict.max_age_seconds)
        elif verdict.outcome == "rejected":
            self.record_rejection(verdict.reason_code)
        else:
            self.record_failure(verdict.reason_code)
        return self.status

    def refresh(self) -> LicenseStatus:
        """Expires stale proofs (fail-closed). Call before any decision."""
        with self._lock:
            if self._status == LicenseStatus.VALID:
                proof = self._proof
                if proof is None or not proof.is_current(
                        now_monotonic=self._time_fn(),
                        generation=self._generation,
                        credential_revision=self._credential_revision,
                        runtime_identity=self._runtime_identity):
                    self._proof = None
                    self._status = LicenseStatus.CHECK_FAILED
                    self._reason = REASON_PROOF_EXPIRED
            return self._status

    # -- decisions --------------------------------------------------------

    @property
    def status(self) -> LicenseStatus:
        """Current volatile status (no implicit refresh)."""
        with self._lock:
            return self._status

    def pro_enabled_for(self, model_id: Any) -> bool:
        """Whether Pro may serve exactly this model id right now.

        ``pro_enabled = key_present AND NOT force_community
        AND license_validation_successful`` with ``license_validation_
        successful`` additionally scoped to the concrete confirmed model id.
        Unknown or unconfirmed ids are never enabled.
        """
        wanted = str(model_id or "").strip()
        if not wanted:
            return False
        self.refresh()
        with self._lock:
            if (self._status != LicenseStatus.VALID
                    or not self._key_present
                    or self._force_community
                    or self._proof is None):
                return False
            return wanted in self._proof.validated_model_ids

    def pro_enabled_global(self) -> bool:
        """Whether any Pro entitlement is currently active (derived)."""
        self.refresh()
        with self._lock:
            return (
                self._status == LicenseStatus.VALID
                and self._key_present
                and not self._force_community
                and self._proof is not None
                and bool(self._proof.validated_model_ids)
            )

    # -- redacted projection ----------------------------------------------

    def public_snapshot(self) -> Dict[str, Any]:
        """Redacted status projection: no secrets, no raw license data."""
        self.refresh()
        now = self._time_fn()
        with self._lock:
            proof = self._proof
            age = proof.age_seconds(now) if proof is not None else None
            current = (
                proof is not None
                and proof.is_current(
                    now_monotonic=now,
                    generation=self._generation,
                    credential_revision=self._credential_revision,
                    runtime_identity=self._runtime_identity)
            )
            pro_enabled = (
                self._status == LicenseStatus.VALID
                and self._key_present
                and not self._force_community
                and current
                and bool(proof.validated_model_ids)
            )
            return {
                "status": self._status.value,
                "generation": self._generation,
                "proEnabled": pro_enabled,
                "validatedModelIds": sorted(proof.validated_model_ids)
                if proof is not None else [],
                "keyPresent": self._key_present,
                "forceCommunity": self._force_community,
                "credentialRevision": self._credential_revision,
                "runtimeIdentity": self._runtime_identity,
                "reasonCode": self._reason,
                "proofAgeSeconds": round(age, 3) if age is not None else None,
                "maxProofAgeSeconds": round(
                    proof.max_age_seconds if proof is not None else self._max_age,
                    3),
            }


__all__ = [
    "LicenseStatus",
    "LicenseProof",
    "LicenseCheckRequest",
    "LicenseVerdict",
    "LicenseVerifier",
    "UnqualifiedLicenseVerifier",
    "LicenseRuntimeAuthority",
    "KROKO_ENGINE_NAMES",
    "DEFAULT_MAX_PROOF_AGE_SECONDS",
    "REASON_OK",
    "REASON_NO_KEY",
    "REASON_FORCE_COMMUNITY",
    "REASON_NO_QUALIFIED_VERIFIER",
    "REASON_CHECK_IN_PROGRESS",
    "REASON_LICENSE_REJECTED",
    "REASON_LICENSE_UNREACHABLE",
    "REASON_PROOF_EXPIRED",
    "REASON_INTENT_CHANGED",
    "REASON_UNQUALIFIED_MODEL",
    "REASON_STALE_GENERATION",
    "normalize_engine_name",
    "is_kroko_lane",
    "derive_credential_revision",
    "config_fingerprint",
    "community_fallback_model",
]
