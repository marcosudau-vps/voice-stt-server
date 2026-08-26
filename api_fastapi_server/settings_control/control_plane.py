"""Central settings control plane.

The control plane is the single authoritative owner of the monotonic
``settingsRevision``, the admin-managed server defaults, and the formatted
public schema/server surfaces. Sessions obtain their per-session state through
:meth:`SettingsControlPlane.create_session_state` and share the same revision
stream, so a confirmed change anywhere bumps the global counter exactly once.
"""

import threading
from typing import Any, Dict, Mapping, Optional

from .enums import (
    ApplyPolicy,
    RESULT_APPLIED,
    RESULT_NO_CHANGE,
    RESULT_REJECTED,
    RESULT_REVISION_CONFLICT,
)
from .model import FieldError, PatchResult
from .registry import SettingsRegistry, coerce_default_value
from .store import RuntimeSettingsStore
from .session import SessionSettingsState
from .validation import (
    validate_patch_envelope,
    validate_timing_bundle,
)


class SettingsControlPlane:
    """Server-authoritative settings root: registry, revision and defaults."""

    def __init__(
        self,
        registry: Optional[SettingsRegistry] = None,
        *,
        store: Optional[RuntimeSettingsStore] = None,
        overlay: Optional[Mapping[str, Any]] = None,
        revision: int = 0,
    ):
        self._registry = registry or SettingsRegistry()
        self._store = store
        self._lock = threading.RLock()
        self._revision = int(revision) if revision and revision > 0 else 0
        loaded = dict(overlay) if overlay else {}
        self._overlay: Dict[str, Any] = {}
        for key, value in self._registry.defaults_for_server_defaults().items():
            self._overlay[key] = (
                coerce_default_value(loaded[key])
                if key in loaded
                else value
            )
        # ``_server_effective`` holds what new sessions actually inherit.
        # ``server_restart`` keys keep their previously effective value here
        # until ``realize_after_restart``; after a real restart the loaded
        # overlay is effective again.
        self._server_effective: Dict[str, Any] = dict(self._overlay)

    @property
    def registry(self) -> SettingsRegistry:
        return self._registry

    @property
    def settings_revision(self) -> int:
        with self._lock:
            return self._revision

    # -- revision -----------------------------------------------------------

    def register_commit(self) -> int:
        """Bumps and (best-effort) persists the global revision exactly once."""
        with self._lock:
            self._revision += 1
            revision = self._revision
        if self._store is not None:
            self._store.save_overlay_and_revision(
                self._overlay, revision
            )
        return revision

    # -- server defaults ----------------------------------------------------

    def server_defaults(self) -> Mapping[str, Any]:
        with self._lock:
            return dict(self._overlay)

    def server_default(self, key: str) -> Optional[Any]:
        with self._lock:
            return self._overlay.get(key)

    def server_effective(self, key: str) -> Optional[Any]:
        with self._lock:
            return self._server_effective.get(key)

    def realize_after_restart(self) -> None:
        """Seam after a server restart: requested becomes effective again."""
        with self._lock:
            self._server_effective = dict(self._overlay)

    def create_session_state(
        self,
        *,
        requested: Optional[Mapping[str, Any]] = None,
    ) -> SessionSettingsState:
        """Builds a new session overlay from the current effective defaults.

        The session shares the control plane's revision stream: a confirmed
        session patch bumps the global ``settingsRevision`` exactly once.
        """
        with self._lock:
            base = dict(self._server_effective)
            revision = self._revision
        for key in self._registry.keys():
            if key in base:
                continue
            definition = self._registry.get(key)
            base[key] = coerce_default_value(definition.default_value)
        return SessionSettingsState(
            self._registry,
            requested=requested,
            revision=revision,
            register_commit=self.register_commit,
        )

    # -- public surfaces ----------------------------------------------------

    def schema_payload(
        self,
        *,
        server_version: str = "",
        server_commit: str = "unknown",
        protocol_version: int = 2,
    ) -> dict:
        return {
            "protocolVersion": protocol_version,
            "serverVersion": server_version,
            "serverCommit": server_commit,
            "secretsExposed": False,
            "settings": self._registry.schema_payload(),
        }

    def server_public(self, *, server_commit: str = "unknown") -> dict:
        """Non-secret requested/effective values of admin-managed defaults."""
        with self._lock:
            overlay = dict(self._overlay)
            effective = dict(self._server_effective)
            revision = self._revision
        entries = []
        for key in sorted(overlay):
            definition = self._registry.get(key)
            if definition is None or not definition.has_server_default:
                continue
            requested = overlay[key]
            if definition.secret:
                entries.append(
                    {
                        "key": key,
                        "scope": definition.scope,
                        "auth": definition.auth,
                        "type": definition.type,
                        "redacted": True,
                        "applyPolicy": definition.apply_policy,
                    }
                )
                continue
            entries.append(
                {
                    "key": key,
                    "scope": definition.scope,
                    "auth": definition.auth,
                    "type": definition.type,
                    "constraints": dict(definition.constraints),
                    "requestedValue": requested,
                    "effectiveValue": effective.get(key, requested),
                    "applyPolicy": definition.apply_policy,
                }
            )
        return {
            "protocolVersion": 2,
            "serverCommit": server_commit,
            "settingsRevision": revision,
            "settings": entries,
        }

    def patch_server(
        self,
        base_revision: Any,
        changes: Any,
        *,
        server_commit: str = "unknown",
    ) -> PatchResult:
        """Transactional admin patch of server-managed defaults."""
        revision, changes, envelope_error = validate_patch_envelope(
            base_revision, changes
        )
        if envelope_error is not None:
            return PatchResult(
                accepted=False,
                result=RESULT_REJECTED,
                settings_revision=self.settings_revision,
                errors=(envelope_error,),
            )
        with self._lock:
            if revision != self._revision:
                return PatchResult(
                    accepted=False,
                    result=RESULT_REVISION_CONFLICT,
                    settings_revision=self._revision,
                    errors=(
                        FieldError(
                            field="baseSettingsRevision",
                            code="stale_revision",
                            message=(
                                "baseSettingsRevision entspricht nicht der "
                                f"aktuellen Revision {self._revision}."
                            ),
                        ),
                    ),
                )

            coerced: Dict[str, Any] = {}
            errors: list = []
            for key, raw in changes.items():
                definition = self._registry.get(key)
                if definition is None:
                    errors.append(
                        FieldError(
                            field=key,
                            code="unknown_key",
                            message=f"{key} ist unbekannt.",
                        )
                    )
                    continue
                if not definition.has_server_default:
                    errors.append(
                        FieldError(
                            field=key,
                            code="wrong_scope",
                            message=(
                                f"{key} besitzt kein admin-managed "
                                "Serverdefault."
                            ),
                        )
                    )
                    continue
                candidate, error = _coerce_server_value(definition, raw)
                if error is not None:
                    errors.append(error)
                    continue
                coerced[key] = candidate

            if not errors:
                proposed = dict(self._overlay)
                proposed.update(coerced)
                errors = validate_timing_bundle(
                    self._registry, coerced, proposed
                )

            if errors:
                return PatchResult(
                    accepted=False,
                    result=RESULT_REJECTED,
                    settings_revision=self._revision,
                    errors=errors,
                )

            changed_keys = [
                key
                for key, value in coerced.items()
                if self._overlay.get(key) != value
            ]
            if not changed_keys:
                return PatchResult(
                    accepted=True,
                    result=RESULT_NO_CHANGE,
                    settings_revision=self._revision,
                    values=dict(self._overlay),
                    effective_values=dict(self._overlay),
                )

            for key, value in coerced.items():
                self._overlay[key] = value
                policy = self._registry.get(key).apply_policy
                if policy != ApplyPolicy.SERVER_RESTART.value:
                    self._server_effective[key] = value
            new_revision = self.register_commit()
            requires_restart = any(
                self._registry.get(key).apply_policy
                == ApplyPolicy.SERVER_RESTART.value
                for key in changed_keys
            )
            return PatchResult(
                accepted=True,
                result=RESULT_APPLIED,
                settings_revision=new_revision,
                changed_keys=tuple(changed_keys),
                values=dict(self._overlay),
                effective_values=dict(self._server_effective),
                apply_policies={
                    key: self._registry.get(key).apply_policy
                    for key in changed_keys
                },
                requires_restart=requires_restart,
            )


def _coerce_server_value(definition, raw):
    # Server defaults are stored as plain JSON-safe values. Type and range
    # rules are identical to the session facet.
    if isinstance(definition.constraints, dict) and definition.constraints.get(
        "unit"
    ):
        pass
    value_type = definition.type
    if value_type == "int":
        if isinstance(raw, bool) or not isinstance(raw, int):
            return None, FieldError(
                definition.key,
                "invalid_type",
                f"{definition.key} muss eine Ganzzahl sein.",
            )
    elif value_type == "float":
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            return None, FieldError(
                definition.key,
                "invalid_type",
                f"{definition.key} muss eine Zahl sein.",
            )
        raw = float(raw)
    elif value_type == "bool":
        if not isinstance(raw, bool):
            return None, FieldError(
                definition.key,
                "invalid_type",
                f"{definition.key} muss ein boolescher Wert sein.",
            )
    elif value_type == "string_list":
        if not isinstance(raw, (list, tuple)):
            return None, FieldError(
                definition.key,
                "invalid_type",
                f"{definition.key} muss eine Liste sein.",
            )
        for item in raw:
            if not isinstance(item, str) or not item:
                return None, FieldError(
                    definition.key,
                    "invalid_type",
                    f"{definition.key} darf nur nicht leere IDs enthalten.",
                )
        raw = list(raw)
    elif value_type == "string":
        if not isinstance(raw, str) or not raw:
            return None, FieldError(
                definition.key,
                "invalid_type",
                f"{definition.key} muss eine nicht leere Zeichenfolge sein.",
            )
    else:
        return None, FieldError(
            definition.key,
            "invalid_type",
            f"{definition.key} wird nicht unterstützt.",
        )
    constraints = definition.constraints or {}
    minimum = constraints.get("min")
    maximum = constraints.get("max")
    if minimum is not None and raw < minimum:
        return None, FieldError(
            definition.key,
            "out_of_range",
            f"{definition.key} muss mindestens {minimum} betragen.",
        )
    if maximum is not None and raw > maximum:
        return None, FieldError(
            definition.key,
            "out_of_range",
            f"{definition.key} darf höchstens {maximum} betragen.",
        )
    return raw, None