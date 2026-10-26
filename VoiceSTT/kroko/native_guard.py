"""Process-wide guard for the native Kroko runtime (PR #15 Abschlusskorrektur).

The native Kroko-ONNX Pro runtime keeps a process-wide license singleton and
reporter. Measured behaviour of the tested 1.12.9 Pro build:

* Community models load without a key; Community -> Pro and Pro -> Community
  work inside one process; the *same* Pro model can be loaded again.
* A second, *different* Pro model in the same process hangs or crashes.
* A successful reload does not prove that the native license context was reset.

This module turns those findings into a fail-closed, pre-load decision. It
owns no native handle, performs no I/O beyond reading a model header, never
logs and never stores a key (only a process-local HMAC of it). The rules:

``concurrent_native_identity``
    At most one native Kroko recognizer instance exists at a time. A second
    instance - another model or a second copy of the same model - is refused;
    Final and Realtime must share one instance.
``pro_identity_change_requires_restart``
    After a Pro model was initialised natively, only that Pro model identity
    may be loaded again. Another Pro model needs a new OS process.
``key_context_change_requires_restart``
    A Pro native context bound to one key is never re-used for another key
    (rotation) or for a removed key: a new key needs a new process.
``pro_requires_key``
    A Pro model without any key would only stall in the native license wait.

Community models are never blocked by Pro state: Pro -> Community is a
qualified transition. It does not reset the native license context though,
which :meth:`KrokoNativeGuard.status` reports as ``nativeProContextActive``.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from .models import read_model_tier, read_model_uuid

CONCURRENT_IDENTITY = "concurrent_native_identity"
PRO_IDENTITY_CHANGE = "pro_identity_change_requires_restart"
KEY_CONTEXT_CHANGE = "key_context_change_requires_restart"
PRO_KEY_REQUIRED = "pro_requires_key"

#: Conflicts that only a new OS process can resolve.
RESTART_CODES = frozenset({PRO_IDENTITY_CHANGE, KEY_CONTEXT_CHANGE})

_MESSAGES = {
    CONCURRENT_IDENTITY: (
        "Ein Prozess darf nur eine native Kroko-Modellinstanz gleichzeitig "
        "betreiben; Final und Realtime muessen dasselbe Kroko-Modell ueber "
        "eine gemeinsame Instanz verwenden."
    ),
    PRO_IDENTITY_CHANGE: (
        "In diesem Prozess wurde bereits ein anderes Kroko-Pro-Modell nativ "
        "initialisiert. Ein Wechsel zwischen Pro-Modellen erfordert einen "
        "Neustart des Voice-STT-Prozesses."
    ),
    KEY_CONTEXT_CHANGE: (
        "Der native Kroko-Pro-Lizenzkontext dieses Prozesses ist an einen "
        "anderen Schluessel gebunden. Ein neuer oder entfernter Schluessel "
        "wird erst nach einem Neustart des Voice-STT-Prozesses wirksam."
    ),
    PRO_KEY_REQUIRED: (
        "Ein Kroko-Pro-Modell kann ohne Schluessel nicht geladen werden."
    ),
}


class KrokoNativeConflict(RuntimeError):
    """A native Kroko load was refused before any native code ran."""

    def __init__(self, code: str, detail: str = ""):
        self.code = code
        self.restart_required = code in RESTART_CODES
        message = _MESSAGES.get(code, code)
        super().__init__(f"{message} ({code})" + (f" {detail}" if detail else ""))


@dataclass(frozen=True)
class NativeIdentity:
    """Technical identity of one Kroko model file.

    ``tier`` is ``"community"`` / ``"pro"`` from the native header, or
    ``None`` for an unmanaged file without the flag. ``ident`` is the header
    UUID when present, otherwise the normalised absolute path.
    """

    tier: Optional[str]
    ident: str

    @property
    def is_pro(self) -> bool:
        return self.tier == "pro"


def identity_for_path(path: Any) -> NativeIdentity:
    uuid = read_model_uuid(path)
    tier = read_model_tier(path)
    if uuid:
        return NativeIdentity(tier, uuid.lower())
    try:
        resolved = str(Path(str(path)).expanduser().resolve())
    except (OSError, ValueError):
        resolved = str(path)
    return NativeIdentity(tier, os.path.normcase(resolved))


_KEY_SECRET = secrets.token_bytes(32)


def _key_revision(key: Any) -> str:
    text = str(key or "")
    if not text.strip():
        return ""
    return hmac.new(_KEY_SECRET, text.encode("utf-8"), hashlib.sha256).hexdigest()


class KrokoNativeGuard:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._leases: Dict[int, NativeIdentity] = {}
        self._next_lease = 1
        self._pro_identity: Optional[str] = None
        self._pro_key_revision: Optional[str] = None
        self._pro_confirmed = False

    # -- decisions ----------------------------------------------------------

    def evaluate(
        self, identity: NativeIdentity, key: Any = "", *, ignore_live: bool = False
    ) -> Optional[KrokoNativeConflict]:
        """Return the conflict a native load would hit, or ``None``.

        Pure: nothing is recorded. ``ignore_live`` is for callers that
        evaluate a *future* configuration while the current instance is
        about to be released (never for the load itself).
        """
        revision = _key_revision(key)
        with self._lock:
            if not ignore_live and self._leases:
                return KrokoNativeConflict(CONCURRENT_IDENTITY)
            if identity.is_pro:
                if self._pro_identity is not None and (
                    self._pro_identity != identity.ident
                ):
                    return KrokoNativeConflict(PRO_IDENTITY_CHANGE)
                if not revision:
                    return KrokoNativeConflict(PRO_KEY_REQUIRED)
                if (
                    self._pro_key_revision is not None
                    and self._pro_key_revision != revision
                ):
                    return KrokoNativeConflict(KEY_CONTEXT_CHANGE)
            return None

    def restart_conflict(
        self, identity: Optional[NativeIdentity], key: Any = ""
    ) -> Optional[KrokoNativeConflict]:
        """The restart-only conflict for a future Pro load, if any."""
        conflict = self.evaluate(
            identity or NativeIdentity(None, ""), key, ignore_live=True
        )
        if conflict is not None and conflict.restart_required:
            return conflict
        return None

    def key_context_conflict(self, key: Any) -> Optional[KrokoNativeConflict]:
        """Whether ``key`` differs from the key the native Pro context holds."""
        revision = _key_revision(key)
        with self._lock:
            if self._pro_key_revision is None:
                return None
            if revision != self._pro_key_revision:
                return KrokoNativeConflict(KEY_CONTEXT_CHANGE)
            return None

    # -- native lifecycle ---------------------------------------------------

    def acquire(self, identity: NativeIdentity, key: Any = "") -> int:
        """Admit one native instance and return its lease; raises on conflict."""
        with self._lock:
            conflict = self.evaluate(identity, key)
            if conflict is not None:
                raise conflict
            lease = self._next_lease
            self._next_lease += 1
            self._leases[lease] = identity
            if identity.is_pro:
                # Sticky for the life of the process: the native singleton is
                # initialised from here on, whatever happens to the load.
                self._pro_identity = identity.ident
                self._pro_key_revision = _key_revision(key)
            return lease

    def confirm_loaded(self, lease: Optional[int]) -> None:
        """The native load behind ``lease`` finished: the runtime accepted it.

        A Pro recognizer only comes up after the native runtime obtained its
        license, so a confirmed Pro load is the proof that the license of this
        exact model and key is valid for this process.
        """
        with self._lock:
            identity = self._leases.get(lease) if lease is not None else None
            if identity is not None and identity.is_pro:
                self._pro_confirmed = True

    def native_license_confirmed(self, model_ident: str, key: Any) -> bool:
        """Whether this process already holds a licensed Pro context for them.

        The provider rejects an additional external check for a key whose
        native reporter is alive in this process (observed with the tested
        runtime), so the confirmed native context is the only meaningful
        evidence for the *same* model and the *same* key. Any other model or
        key never matches.
        """
        revision = _key_revision(key)
        with self._lock:
            return bool(
                self._pro_confirmed
                and revision
                and self._pro_identity == str(model_ident or "").lower()
                and self._pro_key_revision == revision
            )

    def release(self, lease: Optional[int]) -> None:
        if lease is None:
            return
        with self._lock:
            self._leases.pop(lease, None)

    # -- projection -----------------------------------------------------------

    def live_identities(self) -> tuple:
        with self._lock:
            return tuple(self._leases.values())

    def status(self) -> Dict[str, Any]:
        """Secret-free projection (no key, no revision, no path)."""
        with self._lock:
            return {
                "liveNativeInstances": len(self._leases),
                "nativeProContextActive": self._pro_identity is not None,
                "nativeProLicenseConfirmed": self._pro_confirmed,
                "nativeProModelUuid": self._pro_identity,
            }

    def reset_for_tests(self) -> None:
        with self._lock:
            self._leases.clear()
            self._pro_identity = None
            self._pro_key_revision = None
            self._pro_confirmed = False


_PROCESS_GUARD = KrokoNativeGuard()


def process_guard() -> KrokoNativeGuard:
    return _PROCESS_GUARD


__all__ = [
    "CONCURRENT_IDENTITY",
    "KEY_CONTEXT_CHANGE",
    "PRO_IDENTITY_CHANGE",
    "PRO_KEY_REQUIRED",
    "RESTART_CODES",
    "KrokoNativeConflict",
    "KrokoNativeGuard",
    "NativeIdentity",
    "identity_for_path",
    "process_guard",
]
