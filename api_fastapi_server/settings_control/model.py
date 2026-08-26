"""Plain data structures of the settings control plane.

These classes carry no behaviour. The registry publishes one
:class:`SettingDefinition` per server-managed key; the control plane talks in
:class:`FieldError` and result payloads that a later SRV-040 wire handler can
project directly.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class SettingDefinition:
    """Central metadata of one server-managed settings key.

    ``constraints`` is a JSON-safe dict. Known keys:

    * ``min`` / ``max`` – inclusive numeric range for ``int`` / ``float``;
    * ``allowed`` – list of permitted values for ``string``;
    * ``minItems`` – minimum length for ``string_list``;
    * ``lessThanKeys`` – list of keys whose current effective value must be
      strictly greater (cross-field rule; used by the watchdog warning).

    ``has_server_default`` marks keys that are session settable *and* carry an
    admin-managed server default. Such keys appear both in the session facet
    and in the ``/api/v2/settings/server`` server facet.
    """

    key: str
    scope: str
    auth: str
    type: str
    constraints: Dict[str, Any]
    default_value: Any
    apply_policy: str
    description: str = ""
    has_server_default: bool = False
    secret: bool = False

    def to_schema_dict(self):
        payload = {
            "key": self.key,
            "scope": self.scope,
            "auth": self.auth,
            "type": self.type,
            "constraints": dict(self.constraints),
            "defaultValue": self.default_value,
            "applyPolicy": self.apply_policy,
        }
        if self.description:
            payload["description"] = self.description
        return payload


@dataclass(frozen=True)
class FieldError:
    """Machine-readable field error of a rejected patch."""

    field: str
    code: str
    message: str

    def to_dict(self):
        return {
            "field": self.field,
            "code": self.code,
            "message": self.message,
        }


@dataclass(frozen=True)
class PatchResult:
    """Common result shape of a confirmed or rejected settings change.

    ``to_command_ack_parts`` is the SRV-040 seam: the wire handler projects
    these fields into a ``command.ack`` without re-interpreting the result.
    ``accepted`` is only true for ``applied`` and ``no_change``.
    """

    accepted: bool
    result: str
    settings_revision: int
    changed_keys: Tuple[str, ...] = field(default_factory=tuple)
    errors: Tuple[FieldError, ...] = field(default_factory=tuple)
    values: Dict[str, Any] = field(default_factory=dict)
    effective_values: Dict[str, Any] = field(default_factory=dict)
    apply_policies: Dict[str, str] = field(default_factory=dict)
    requires_restart: bool = False

    def to_dict(self):
        payload = {
            "accepted": self.accepted,
            "result": self.result,
            "settingsRevision": self.settings_revision,
            "changedKeys": list(self.changed_keys),
            "values": dict(self.values),
            "effectiveValues": dict(self.effective_values),
            "applyPolicies": dict(self.apply_policies),
        }
        if self.requires_restart:
            payload["requiresRestart"] = True
        if self.errors:
            payload["errors"] = [error.to_dict() for error in self.errors]
        return payload

    def to_command_ack_parts(self):
        return {
            "accepted": self.accepted,
            "result": self.result,
            "settingsRevision": self.settings_revision,
            "changedKeys": list(self.changed_keys),
            "effectiveSettings": dict(self.effective_values),
            "errors": [error.to_dict() for error in self.errors],
        }