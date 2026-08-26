"""Session settings state and the ``session_settings.patch`` domain operation.

This is the service/domain-side port SRV-040 calls for
``session_settings.patch``. It is deliberately free of any WebSocket parser;
the structured :class:`PatchResult` is projected into ``command.ack`` by the
wire handler.
"""

import threading
from copy import deepcopy
from types import MappingProxyType
from typing import Any, Dict, Mapping, Optional

from .enums import (
    ApplyPolicy,
    RESULT_APPLIED,
    RESULT_NO_CHANGE,
    RESULT_REJECTED,
    RESULT_REVISION_CONFLICT,
)
from .model import FieldError, PatchResult
from .registry import SettingsRegistry
from .validation import (
    validate_patch_envelope,
    validate_timing_bundle,
)

#: Apply policies that govern the *next* activation snapshot.
NEXT_ACTIVATION_POLICIES = frozenset(
    {
        ApplyPolicy.NEXT_ACTIVATION.value,
        ApplyPolicy.LIVE.value,
    }
)


def _freeze(value):
    """Returns a recursively immutable value for activation snapshots."""
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return deepcopy(value)


def _thaw(value):
    if isinstance(value, MappingProxyType):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    return deepcopy(value)


class SessionSettingsState:
    """Server-authoritative per-session requested/effective setting overlay.

    ``requested`` holds the last confirmed request; ``effective`` holds what
    the next activation or rebuilt session will actually see. A running
    activation keeps the immutable snapshot that :meth:`freeze_activation`
    produced when it started - naming patches never mutate it.
    """

    def __init__(
        self,
        registry: SettingsRegistry,
        *,
        requested: Optional[Mapping[str, Any]] = None,
        revision: int = 0,
        register_commit=None,
    ):
        self._registry = registry
        self._lock = threading.RLock()
        self._register_commit = register_commit
        self._revision = int(revision) if revision >= 0 else 0
        base = registry.defaults()
        if requested is not None:
            self._requested = dict(base)
            self._requested.update(dict(requested))
        else:
            self._requested = dict(base)
        # ``effective`` starts identical; next_session/server_restart facets
        # keep the previously effective value until the rebuild seam runs.
        self._effective = dict(self._requested)
        self._tracked_next_session = {}

    @property
    def settings_revision(self) -> int:
        return self._revision

    def requested_values(self) -> Mapping[str, Any]:
        with self._lock:
            return dict(self._requested)

    def effective_values(self) -> Mapping[str, Any]:
        with self._lock:
            return self._effective

    def apply_patch(
        self,
        base_revision: Any,
        changes: Any,
        *,
        register_commit=None,
    ) -> PatchResult:
        """Transactional ``session_settings.patch``.

        ``register_commit`` is called exactly once per confirmed transaction
        and returns the new global revision number. When no callback is given
        (plain unit usage) the state bumps its own revision.
        """
        if register_commit is None:
            register_commit = self._register_commit
        with self._lock:
            revision, changes, envelope_error = validate_patch_envelope(
                base_revision, changes
            )
            if envelope_error is not None:
                return self._rejected(
                    RESULT_REJECTED,
                    self._revision,
                    envelope_error,
                )
            if revision != self._revision:
                return self._rejected(
                    RESULT_REVISION_CONFLICT,
                    self._revision,
                    FieldError(
                        field="baseSettingsRevision",
                        code="stale_revision",
                        message=(
                            "baseSettingsRevision entspricht nicht der "
                            f"aktuellen Revision {self._revision}."
                        ),
                    ),
                )

            coerced, errors = {}, []
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
                if definition.scope == "server":
                    errors.append(
                        FieldError(
                            field=key,
                            code="wrong_scope",
                            message=(
                                f"{key} ist eine Servereinstellung und kann "
                                "nicht über die Session gepatcht werden."
                            ),
                        )
                    )
                    continue
                candidate, error = _coerce_definition(definition, raw)
                if error is not None:
                    errors.append(error)
                    continue
                coerced[key] = candidate

            if not errors:
                # Cross-field rule against the values that would become
                # effective together with the patch.
                proposed = dict(self._effective)
                proposed.update(coerced)
                cross_errors = validate_timing_bundle(
                    self._registry, coerced, proposed
                )
                errors.extend(cross_errors)

            if errors:
                return self._rejected(RESULT_REJECTED, self._revision, *errors)

            if not coerced:
                # No key was applicable; the envelope was valid but empty.
                return self._rejected(RESULT_REJECTED, self._revision,
                                     FieldError(
                                         field="changes",
                                         code="no_changes",
                                         message="Es wurden keine Änderungen angegeben.",
                                     ))

            changed_keys = [
                key
                for key, value in coerced.items()
                if self._requested.get(key) != value
            ]
            if not changed_keys:
                return PatchResult(
                    accepted=True,
                    result=RESULT_NO_CHANGE,
                    settings_revision=self._revision,
                    values=dict(self._requested),
                    effective_values=dict(self._effective),
                    apply_policies={
                        key: self._registry.get(key).apply_policy
                        for key in self._requested
                    },
                )

            next_requested = dict(self._requested)
            next_requested.update(coerced)
            next_effective = dict(self._effective)
            for key, value in coerced.items():
                policy = self._registry.get(key).apply_policy
                if policy == ApplyPolicy.LIVE.value:
                    next_effective[key] = value
                elif policy == ApplyPolicy.NEXT_SESSION.value:
                    # Reconnect-pflichtig: erst der nächste Sessionaufbau
                    # (realize_next_session) macht den Wert wirksam.
                    continue
                elif policy == ApplyPolicy.SERVER_RESTART.value:
                    # Stays on the previously effective value until restart.
                    continue
                else:
                    # next_activation: effective for the next activation.
                    next_effective[key] = value

            if register_commit is not None:
                self._revision = register_commit()
                requires_restart = False
            else:
                self._revision += 1
                requires_restart = False

            self._requested = next_requested
            self._effective = next_effective

            policies = {
                key: self._registry.get(key).apply_policy
                for key in changed_keys
            }
            return PatchResult(
                accepted=True,
                result=RESULT_APPLIED,
                settings_revision=self._revision,
                changed_keys=tuple(changed_keys),
                values=dict(self._requested),
                effective_values=dict(self._effective),
                apply_policies=policies,
                requires_restart=requires_restart,
            )

    def realize_next_session(self):
        """Seam for rebuilt sessions: requested becomes effective again.

        ``next_session`` values that were patched while the old session ran
        become effective only here, never during the running session.
        """
        with self._lock:
            next_effective = dict(self._effective)
            for key, value in self._requested.items():
                definition = self._registry.get(key)
                if definition and definition.apply_policy == ApplyPolicy.NEXT_SESSION.value:
                    next_effective[key] = value
            self._effective = next_effective
            self._tracked_next_session = {}

    def freeze_activation(self) -> Mapping[str, Any]:
        """Immutable snapshot of the next-activation effective settings.

        A running activation keeps this snapshot; a later patch returns a
        *different* freeze for the next activation.
        """
        with self._lock:
            frozen = {}
            for key in self._requested:
                definition = self._registry.get(key)
                if definition is None:
                    continue
                if definition.apply_policy in NEXT_ACTIVATION_POLICIES:
                    frozen[key] = _freeze(self._effective[key])
            return _freeze(frozen)

    def public_effective_settings(self) -> Dict[str, Any]:
        return dict(self.effective_values())

    def _rejected(self, result, revision, *errors):
        return PatchResult(
            accepted=False,
            result=result,
            settings_revision=revision,
            errors=errors,
        )


def _coerce_definition(definition, raw):
    from .model import FieldError as _FE

    value_type = definition.type
    if value_type == "int":
        if isinstance(raw, bool) or not isinstance(raw, int):
            return None, _FE(
                definition.key,
                "invalid_type",
                f"{definition.key} muss eine Ganzzahl sein.",
            )
        value = int(raw)
    elif value_type == "float":
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            return None, _FE(
                definition.key,
                "invalid_type",
                f"{definition.key} muss eine Zahl sein.",
            )
        value = float(raw)
    elif value_type == "bool":
        if not isinstance(raw, bool):
            return None, _FE(
                definition.key,
                "invalid_type",
                f"{definition.key} muss ein boolescher Wert sein.",
            )
        value = bool(raw)
    elif value_type == "string_list":
        if not isinstance(raw, (list, tuple)):
            return None, _FE(
                definition.key,
                "invalid_type",
                f"{definition.key} muss eine Liste sein.",
            )
        value = list(raw)
    elif value_type == "string":
        if not isinstance(raw, str) or not raw:
            return None, _FE(
                definition.key,
                "invalid_type",
                f"{definition.key} muss eine nicht leere Zeichenfolge sein.",
            )
        value = raw
    else:
        return None, _FE(
            definition.key,
            "invalid_type",
            f"{definition.key} wird nicht unterstützt.",
        )
    constraints = definition.constraints or {}
    minimum = constraints.get("min")
    maximum = constraints.get("max")
    if minimum is not None and value < minimum:
        return None, _FE(
            definition.key,
            "out_of_range",
            f"{definition.key} muss mindestens {minimum} betragen.",
        )
    if maximum is not None and value > maximum:
        return None, _FE(
            definition.key,
            "out_of_range",
            f"{definition.key} darf höchstens {maximum} betragen.",
        )
    allowed = constraints.get("allowed")
    if allowed is not None and value not in allowed:
        return None, _FE(
            definition.key,
            "invalid_value",
            f"{definition.key} ist kein zulässiger Wert.",
        )
    min_items = constraints.get("minItems")
    if min_items is not None and len(value) < min_items:
        return None, _FE(
            definition.key,
            "too_few_items",
            f"{definition.key} muss mindestens {min_items} Einträge besitzen.",
        )
    return value, None