"""AP-SRV-050 settings control plane - the one server-authoritative settings domain.

This module owns the trigger-relevant settings contract and nothing else:

* the registry (key / scope / auth / type / constraints / default / apply policy);
* the admin-managed server default overlay and the *server* ``settingsRevision``;
* one :class:`SessionSettingsState` per v2 session - the per-session domain
  authority with its own monotonic ``settingsRevision``;
* atomic patch validation and requested/effective resolution per apply policy;
* the cross-field watchdog-warning rule against the *final* candidate.

It is deliberately free of any second protocol layer, second replay cache,
second event sequence or second suppression authority:

* ``session_settings.patch`` answers with a :class:`PatchResult`; the wire
  layer (:mod:`api_fastapi_server.protocol_v2`) projects it into ``command.ack``
  and ``settings.changed`` through the existing AP-SRV-040 event dispatch seam.
* runtime suppression is only *represented* in the registry metadata. The
  runtime writing authority stays ``trigger_suppression.set`` /
  :meth:`api_fastapi_server.activation.ActivationController.set_runtime_suppression`.
* persistence reuses the existing :class:`RuntimeConfigStore` and its single
  runtime JSON document. The names ``settingsControlOverlay`` and
  ``settingsRevision`` are the binding top-level fields (AP-SRV-050 prompt 23).
* wake-word *detection* stays in AP-SRV-060; this plane manages and publishes
  the requested/effective wake values only.
"""

import math
import numbers
import threading
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Callable, Dict, FrozenSet, Iterable, List, Mapping, Optional, Tuple


# -- frozen value sets ---------------------------------------------------------

SCOPE_SESSION = "session"
SCOPE_SERVER = "server"
SCOPE_CLIENT_LOCAL = "client_local"

AUTH_SESSION = "session"
AUTH_ADMIN = "admin"

TYPE_INT = "int"
TYPE_FLOAT = "float"
TYPE_BOOL = "bool"
TYPE_STRING = "string"
TYPE_STRING_LIST = "string_list"

APPLY_LIVE = "live"
APPLY_NEXT_ACTIVATION = "next_activation"
APPLY_NEXT_SESSION = "next_session"
APPLY_SERVER_RESTART = "server_restart"

#: The only public apply policies. No ``mixed``/``deferred``/``later`` synonyms.
APPLY_POLICIES = (APPLY_LIVE, APPLY_NEXT_ACTIVATION, APPLY_NEXT_SESSION, APPLY_SERVER_RESTART)

#: Deterministic ordering of settings.changed event groups within one transaction.
POLICY_EVENT_ORDER = (APPLY_LIVE, APPLY_NEXT_ACTIVATION, APPLY_NEXT_SESSION, APPLY_SERVER_RESTART)

RESULT_APPLIED = "applied"
RESULT_NO_CHANGE = "no_change"
RESULT_REVISION_CONFLICT = "settings_revision_conflict"
RESULT_REJECTED = "settings_rejected"
RESULT_INTERNAL_ERROR = "internal_error"


# -- registry key names --------------------------------------------------------

ACTIVATION_INITIAL_SPEECH = "activation.initialSpeechTimeoutMs"
ACTIVATION_FOLLOWUP = "activation.followupTimeoutMs"
ACTIVATION_WATCHDOG_INITIAL = "activation.segmentWatchdogInitialMs"
ACTIVATION_WATCHDOG_REFRESH = "activation.segmentWatchdogRefreshMs"
ACTIVATION_WATCHDOG_WARNING = "activation.segmentWatchdogWarningMs"
ACTIVATION_CLOSING_RECOVERY = "activation.closingRecoveryTimeoutMs"

WAKE_WORD_SENSITIVITY = "wakeWord.sensitivity"
WAKE_WORD_SELECTION = "wakeWord.selection"
WAKE_WORD_GLOBAL_DISABLED = "wakeWord.globalDisabledIds"

RUNTIME_SUPPRESSION_MANUAL = "runtimeSuppression.manual"
RUNTIME_SUPPRESSION_WAKE_WORD = "runtimeSuppression.wakeWord"

#: The six contract-frozen activation/watchdog timings, in milliseconds on the
#: public schema; the controller works in seconds, converted centrally.
TIMING_KEYS = frozenset({
    ACTIVATION_INITIAL_SPEECH,
    ACTIVATION_FOLLOWUP,
    ACTIVATION_WATCHDOG_INITIAL,
    ACTIVATION_WATCHDOG_REFRESH,
    ACTIVATION_WATCHDOG_WARNING,
    ACTIVATION_CLOSING_RECOVERY,
})

#: Cross-field rule: ``segmentWatchdogWarningMs`` must be strictly smaller than
#: every currently effective watchdog deadline it can accompany.
WATCHDOG_WARNING_LESS_THAN_KEYS = (
    ACTIVATION_WATCHDOG_INITIAL,
    ACTIVATION_WATCHDOG_REFRESH,
)

#: The cross-field rule runs as soon as *any* of these three keys takes part in
#: a transaction. Otherwise a sequential pair of patches could lower a watchdog
#: deadline below an already accepted warning (AP-SRV-050 C2 F1).
WATCHDOG_CROSS_FIELD_KEYS = frozenset(
    {ACTIVATION_WATCHDOG_WARNING, ACTIVATION_WATCHDOG_INITIAL,
     ACTIVATION_WATCHDOG_REFRESH}
)

# -- validation result codes ---------------------------------------------------

CODE_UNKNOWN_KEY = "unknown_key"
CODE_INVALID_TYPE = "invalid_type"
CODE_OUT_OF_RANGE = "out_of_range"
CODE_TOO_FEW_ITEMS = "too_few_items"
CODE_CROSS_FIELD_CONFLICT = "cross_field_conflict"
CODE_WRONG_SCOPE = "wrong_scope"
CODE_STALE_REVISION = "stale_settings_revision"
CODE_READ_ONLY_AUTHORITY = "read_only_runtime_authority"
CODE_INVALID_PAYLOAD = "invalid_payload"
CODE_WAKE_SELECTION_REQUIRED = "wake_word_selection_required"
CODE_WAKE_WORD_UNAVAILABLE = "wake_word_unavailable"
CODE_PERSISTENCE_FAILED = "persistence_failed"


# -- data structures -----------------------------------------------------------

@dataclass(frozen=True)
class SettingDefinition:
    """Central metadata of one server-managed settings key.

    ``constraints`` is a JSON-safe dict. Known keys:

    * ``min`` / ``max`` - inclusive numeric range for ``int`` / ``float``;
    * ``allowed`` - list of permitted values;
    * ``minItems`` - minimum length for ``string_list``;
    * ``lessThanKeys`` - keys whose final candidate must be strictly greater.

    ``has_server_default`` marks keys with an admin-managed server default;
    they appear in the schema, the server surface and the session surface.
    ``writable`` is ``False`` for keys whose authority lives elsewhere (runtime
    suppression), so the registry can represent them without creating a second
    write path.
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
    writable: bool = True
    secret: bool = False

    def to_schema_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
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

    def to_dict(self) -> Dict[str, str]:
        return {"field": self.field, "code": self.code, "message": self.message}


@dataclass(frozen=True)
class PatchResult:
    """Common result shape of a confirmed or rejected settings change.

    ``accepted`` is only true for ``applied`` and ``no_change``. The wire layer
    projects this value into ``command.ack`` and, for a real change, into the
    ``settings.changed`` events of the transaction.
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

    @property
    def error_dicts(self) -> List[Dict[str, str]]:
        return [error.to_dict() for error in self.errors]

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
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
            payload["errors"] = self.error_dicts
        return payload


# -- registry ------------------------------------------------------------------

def _coerce_copy(value: Any) -> Any:
    """A defensive JSON-safe copy of a registry default value."""
    if isinstance(value, (tuple, list)):
        return [item for item in value]
    if isinstance(value, MappingProxyType):
        return {key: _coerce_copy(item) for key, item in value.items()}
    return value


def builtin_definitions() -> List[SettingDefinition]:
    """The server-managed settings keys of the frozen contract.

    The six activation timings use milliseconds in the public schema, are
    session-scoped with Sessionrecht and ``next_activation`` apply, and each
    exposes an admin-managed server default facet.
    """
    return [
        SettingDefinition(
            key=ACTIVATION_INITIAL_SPEECH,
            scope=SCOPE_SESSION,
            auth=AUTH_SESSION,
            type=TYPE_INT,
            constraints={"min": 100, "max": 3600000, "unit": "ms"},
            default_value=15000,
            apply_policy=APPLY_NEXT_ACTIVATION,
            description=(
                "Wartezeit auf die erste Sprache einer neuen Activation."
            ),
            has_server_default=True,
        ),
        SettingDefinition(
            key=ACTIVATION_FOLLOWUP,
            scope=SCOPE_SESSION,
            auth=AUTH_SESSION,
            type=TYPE_INT,
            constraints={"min": 100, "max": 60000, "unit": "ms"},
            default_value=3000,
            apply_policy=APPLY_NEXT_ACTIVATION,
            description=(
                "Nachfragefenster nach einem beendeten Segment derselben "
                "Activation."
            ),
            has_server_default=True,
        ),
        SettingDefinition(
            key=ACTIVATION_WATCHDOG_INITIAL,
            scope=SCOPE_SESSION,
            auth=AUTH_SESSION,
            type=TYPE_INT,
            constraints={"min": 60000, "max": 3600000, "unit": "ms"},
            default_value=600000,
            apply_policy=APPLY_NEXT_ACTIVATION,
            description="Segment-Watchdog-Deadline beim Segmentstart.",
            has_server_default=True,
        ),
        SettingDefinition(
            key=ACTIVATION_WATCHDOG_REFRESH,
            scope=SCOPE_SESSION,
            auth=AUTH_SESSION,
            type=TYPE_INT,
            constraints={"min": 30000, "max": 600000, "unit": "ms"},
            default_value=180000,
            apply_policy=APPLY_NEXT_ACTIVATION,
            description=(
                "Mindest-Restzeit, die ein Refresh in `segment_active` "
                "sichert."
            ),
            has_server_default=True,
        ),
        SettingDefinition(
            key=ACTIVATION_WATCHDOG_WARNING,
            scope=SCOPE_SESSION,
            auth=AUTH_SESSION,
            type=TYPE_INT,
            constraints={
                "min": 5000,
                "unit": "ms",
                "lessThanKeys": list(WATCHDOG_WARNING_LESS_THAN_KEYS),
            },
            default_value=30000,
            apply_policy=APPLY_NEXT_ACTIVATION,
            description=(
                "Vorwarnzeit vor dem Watchdog-Ablauf. Muss kleiner sein als "
                "die jeweils wirksame Watchdog-Frist."
            ),
            has_server_default=True,
        ),
        SettingDefinition(
            key=ACTIVATION_CLOSING_RECOVERY,
            scope=SCOPE_SESSION,
            auth=AUTH_SESSION,
            type=TYPE_INT,
            constraints={"min": 1000, "max": 30000, "unit": "ms"},
            default_value=5000,
            apply_policy=APPLY_NEXT_ACTIVATION,
            description="Recoveryfrist in `closing_input`.",
            has_server_default=True,
        ),
        SettingDefinition(
            key=WAKE_WORD_SENSITIVITY,
            scope=SCOPE_SESSION,
            auth=AUTH_SESSION,
            type=TYPE_FLOAT,
            constraints={"min": 0.0, "max": 1.0},
            default_value=0.5,
            apply_policy=APPLY_NEXT_ACTIVATION,
            description=(
                "Gemeinsame Wake-Word-Empfindlichkeit der Session. Der Server "
                "validiert und veröffentlicht den tatsächlich aufgelösten Wert; "
                "die Detection selbst gehört AP-SRV-060."
            ),
            has_server_default=True,
        ),
        SettingDefinition(
            key=WAKE_WORD_SELECTION,
            scope=SCOPE_SESSION,
            auth=AUTH_SESSION,
            type=TYPE_STRING_LIST,
            constraints={"minItems": 0},
            default_value=[],
            apply_policy=APPLY_NEXT_SESSION,
            description=(
                "Kanonische IDs der für die Session gewählten Wake Words. "
                "Wirkt auf neu aufgebaute Sessions; die atomare Admission "
                "gehört AP-SRV-060."
            ),
        ),
        SettingDefinition(
            key=RUNTIME_SUPPRESSION_MANUAL,
            scope=SCOPE_SESSION,
            auth=AUTH_SESSION,
            type=TYPE_BOOL,
            constraints={},
            default_value=False,
            apply_policy=APPLY_LIVE,
            description=(
                "Laufzeit-Unterdrückung der manuellen Triggerquelle. Die "
                "Schreibautorität bleibt `trigger_suppression.set`."
            ),
            writable=False,
        ),
        SettingDefinition(
            key=RUNTIME_SUPPRESSION_WAKE_WORD,
            scope=SCOPE_SESSION,
            auth=AUTH_SESSION,
            type=TYPE_BOOL,
            constraints={},
            default_value=False,
            apply_policy=APPLY_LIVE,
            description=(
                "Laufzeit-Unterdrückung der Wake-Word-Quelle. Die "
                "Schreibautorität bleibt `trigger_suppression.set`."
            ),
            writable=False,
        ),
        SettingDefinition(
            key=WAKE_WORD_GLOBAL_DISABLED,
            scope=SCOPE_SERVER,
            auth=AUTH_ADMIN,
            type=TYPE_STRING_LIST,
            constraints={"minItems": 0},
            default_value=[],
            apply_policy=APPLY_NEXT_SESSION,
            description=(
                "Global deaktivierte Wake-Word-Katalog-IDs. Wirkt auf neue "
                "Sessions; der Katalog selbst gehört AP-SRV-060."
            ),
            has_server_default=True,
        ),
    ]


@dataclass
class SettingsRegistry:
    """Read-only catalog of all server-managed settings keys."""

    definitions: Mapping[str, SettingDefinition] = field(default_factory=dict)

    def __init__(self, definitions: Optional[Iterable[SettingDefinition]] = None):
        entries: Dict[str, SettingDefinition] = {}
        for definition in definitions or builtin_definitions():
            entries[definition.key] = definition
        self.definitions = entries
        self._lock = threading.RLock()

    def get(self, key: str) -> Optional[SettingDefinition]:
        return self.definitions.get(key)

    def __contains__(self, key: str) -> bool:
        return key in self.definitions

    def keys(self) -> FrozenSet[str]:
        return frozenset(self.definitions)

    def session_keys(self) -> FrozenSet[str]:
        return frozenset(
            key for key, definition in self.definitions.items()
            if definition.scope == SCOPE_SESSION
        )

    def server_default_keys(self) -> FrozenSet[str]:
        return frozenset(
            key for key, definition in self.definitions.items()
            if definition.has_server_default
        )

    def is_secret(self, key: str) -> bool:
        definition = self.definitions.get(key)
        return bool(definition and definition.secret)

    def defaults(self) -> Dict[str, Any]:
        return {
            key: _coerce_copy(definition.default_value)
            for key, definition in self.definitions.items()
        }

    def defaults_for_server_defaults(self) -> Dict[str, Any]:
        return {
            key: _coerce_copy(definition.default_value)
            for key, definition in self.definitions.items()
            if definition.has_server_default
        }

    def schema_payload(self) -> List[Dict[str, Any]]:
        return [
            definition.to_schema_dict()
            for definition in sorted(
                self.definitions.values(), key=lambda item: item.key
            )
        ]


def build_default_registry() -> SettingsRegistry:
    return SettingsRegistry()


# -- value coercion and validation ---------------------------------------------

def _finite(value: Any) -> bool:
    try:
        return math.isfinite(value)
    except TypeError:
        return False


def _error(defn: SettingDefinition, code: str, message: str) -> FieldError:
    return FieldError(field=defn.key, code=code, message=message)


def coerce_definition_value(
    defn: SettingDefinition, raw: Any
) -> Tuple[Optional[Any], Optional[FieldError]]:
    """Coerces and validates one value against its definition.

    ``bool`` is never accepted for numeric types. Returns ``(value, None)`` on
    success and ``(None, FieldError)`` on failure.
    """
    value_type = defn.type
    if value_type in (TYPE_INT, TYPE_FLOAT) and isinstance(raw, bool):
        return None, _error(defn, CODE_INVALID_TYPE, f"{defn.key} muss eine Zahl sein.")

    value: Any = raw
    if value_type == TYPE_INT:
        if not isinstance(value, int):
            return None, _error(defn, CODE_INVALID_TYPE, f"{defn.key} muss eine Ganzzahl sein.")
        value = int(value)
    elif value_type == TYPE_FLOAT:
        if not isinstance(value, numbers.Real) or isinstance(value, bool):
            return None, _error(defn, CODE_INVALID_TYPE, f"{defn.key} muss eine Zahl sein.")
        value = float(value)
        if not _finite(value):
            return None, _error(defn, CODE_INVALID_TYPE, f"{defn.key} muss endlich sein.")
    elif value_type == TYPE_BOOL:
        if not isinstance(value, bool):
            return None, _error(defn, CODE_INVALID_TYPE, f"{defn.key} muss ein boolescher Wert sein.")
    elif value_type == TYPE_STRING:
        if not isinstance(value, str) or not value:
            return None, _error(defn, CODE_INVALID_TYPE, f"{defn.key} muss eine nicht leere Zeichenfolge sein.")
    elif value_type == TYPE_STRING_LIST:
        if not isinstance(value, (list, tuple)):
            return None, _error(defn, CODE_INVALID_TYPE, f"{defn.key} muss eine Liste sein.")
        normalized = list(value)
        for item in normalized:
            if not isinstance(item, str) or not item:
                return None, _error(
                    defn, CODE_INVALID_TYPE, f"{defn.key} darf nur nicht leere IDs enthalten."
                )
        value = normalized
    else:
        return None, _error(defn, CODE_INVALID_TYPE, f"{defn.key} besitzt einen unbekannten Typ.")

    error = _validate_constraints(defn, value)
    return (value, None) if error is None else (None, error)


def _validate_constraints(defn: SettingDefinition, value: Any) -> Optional[FieldError]:
    constraints = defn.constraints or {}
    minimum = constraints.get("min")
    maximum = constraints.get("max")
    if minimum is not None and value < minimum:
        return _error(defn, CODE_OUT_OF_RANGE, f"{defn.key} muss mindestens {minimum} betragen.")
    if maximum is not None and value > maximum:
        return _error(defn, CODE_OUT_OF_RANGE, f"{defn.key} darf höchstens {maximum} betragen.")
    allowed = constraints.get("allowed")
    if allowed is not None and value not in allowed:
        return _error(defn, CODE_INVALID_TYPE, f"{defn.key} ist kein zulässiger Wert.")
    min_items = constraints.get("minItems")
    if min_items is not None and len(value) < min_items:
        return _error(defn, CODE_TOO_FEW_ITEMS, f"{defn.key} muss mindestens {min_items} Einträge besitzen.")
    return None


def validate_patch_envelope(
    base_revision: Any, changes: Any
) -> Tuple[Optional[int], Optional[Dict[str, Any]], Optional[FieldError]]:
    if isinstance(base_revision, bool) or not isinstance(base_revision, int):
        return None, None, FieldError(
            "baseSettingsRevision", CODE_INVALID_TYPE,
            "baseSettingsRevision muss eine nicht negative Ganzzahl sein.",
        )
    if base_revision < 0:
        return None, None, FieldError(
            "baseSettingsRevision", CODE_OUT_OF_RANGE,
            "baseSettingsRevision muss nicht negativ sein.",
        )
    if not isinstance(changes, dict) or not changes:
        return None, None, FieldError(
            "changes", CODE_INVALID_TYPE, "changes muss ein nicht leeres Objekt sein."
        )
    return int(base_revision), changes, None


def validate_timing_bundle(
    registry: SettingsRegistry,
    changes: Mapping[str, Any],
    candidate: Mapping[str, Any],
) -> List[FieldError]:
    """Cross-field rule of the watchdog warning against the final candidate.

    The rule runs whenever the transaction touches *any* of the three watchdog
    keys (warning, initial, refresh), so a sequential lowering of a deadline
    below an already accepted warning can never slip through. The comparison
    always uses the fully applied final ``candidate`` - never changes alone,
    never an intermediate order (AP-SRV-050 C2 F1).
    """
    if not WATCHDOG_CROSS_FIELD_KEYS.intersection(changes):
        return []
    warning = candidate.get(ACTIVATION_WATCHDOG_WARNING)
    if warning is None or isinstance(warning, bool):
        return []
    if not isinstance(warning, int):
        return []
    errors = []
    for deadline_key in WATCHDOG_WARNING_LESS_THAN_KEYS:
        deadline = candidate.get(deadline_key)
        if deadline is None or not isinstance(deadline, int):
            continue
        if warning >= deadline:
            errors.append(
                FieldError(
                    field=ACTIVATION_WATCHDOG_WARNING,
                    code=CODE_CROSS_FIELD_CONFLICT,
                    message=(
                        f"{ACTIVATION_WATCHDOG_WARNING} ({warning} ms) muss "
                        f"kleiner sein als die wirksame Frist von "
                        f"{deadline_key} ({deadline} ms)."
                    ),
                )
            )
    return errors


# -- session settings state -----------------------------------------------------

def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, MappingProxyType):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw(item) for item in value]
    if isinstance(value, frozenset):
        return {_thaw(item) for item in value}
    return value


@dataclass(frozen=True)
class ActivationAdmissionSettings:
    """One immutable snapshot read for a single activation admission (C2 F3).

    ``effective_settings`` and ``timing_seconds`` are derived from the **same**
    locked session snapshot, and ``settings_revision`` records which revision
    that snapshot belongs to. A settings patch can therefore never yield a
    mixture ("effective from N, timings from N+1") for one admission.
    """

    settings_revision: int
    effective_settings: Mapping[str, Any]
    timing_seconds: Mapping[str, float]


@dataclass(frozen=True)
class SessionSettingsProjection:
    """One immutable atomic read for the wire settings projection (AP-SRV-050 C3).

    ``settings_revision``, ``requested_settings`` and ``effective_settings`` all
    come from the very same locked snapshot of the session settings authority,
    so a ``session.snapshot`` can never mix two settings revisions. The running
    activation latch and the live runtime suppression are overlaid *afterwards*
    by the session/port without re-reading the settings authority.
    """

    settings_revision: int
    requested_settings: Mapping[str, Any]
    effective_settings: Mapping[str, Any]


class SessionSettingsState:
    """Server-authoritative per-session requested/effective settings overlay.

    One instance exists per session and owns the *session* ``settingsRevision``.
    ``requested`` holds the last confirmed request; ``effective`` holds what the
    next activation or rebuilt session will actually see. A running activation
    keeps the immutable snapshot produced when it started - later patches never
    mutate it.
    """

    def __init__(
        self,
        registry: SettingsRegistry,
        *,
        server_defaults: Optional[Mapping[str, Any]] = None,
        requested: Optional[Mapping[str, Any]] = None,
        revision: int = 0,
        validate_key: Optional[Callable[[str, Any], List[FieldError]]] = None,
    ):
        self._registry = registry
        self._lock = threading.RLock()
        self._revision = int(revision) if int(revision) >= 0 else 0
        self._validate_key = validate_key

        base = registry.defaults()
        for key, value in (server_defaults or {}).items():
            if key in base:
                base[key] = _coerce_copy(value)
        for key, value in (requested or {}).items():
            if key in base or key in registry.definitions:
                base[key] = _coerce_copy(value)

        self._requested: Dict[str, Any] = {}
        for key in sorted(registry.keys()):
            if key in base:
                self._requested[key] = base[key]
        # ``effective`` starts identical. next_session/server_restart facets keep
        # the currently effective value across patches until the rebuild seam.
        self._effective: Dict[str, Any] = dict(self._requested)

    @property
    def settings_revision(self) -> int:
        with self._lock:
            return self._revision

    @property
    def registry(self) -> SettingsRegistry:
        return self._registry

    def requested_values(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._requested)

    def effective_values(self) -> Dict[str, Any]:
        """What the next admission/session would use (per-policy semantics)."""
        with self._lock:
            return dict(self._effective)

    def apply_patch(
        self,
        base_revision: Any,
        changes: Mapping[str, Any],
    ) -> PatchResult:
        """Transactional ``session_settings.patch``.

        Session settings are per-session and never persisted; the server
        default overlay is the only persistent part (AP-SRV-050 prompt 21-27).
        """
        with self._lock:
            revision, changes, envelope_error = validate_patch_envelope(base_revision, changes)
            if envelope_error is not None:
                return PatchResult(
                    accepted=False,
                    result=RESULT_REJECTED,
                    settings_revision=self._revision,
                    errors=(envelope_error,),
                )
            if revision != self._revision:
                return PatchResult(
                    accepted=False,
                    result=RESULT_REVISION_CONFLICT,
                    settings_revision=self._revision,
                    errors=(
                        FieldError(
                            field="baseSettingsRevision",
                            code=CODE_STALE_REVISION,
                            message=(
                                "baseSettingsRevision entspricht nicht der "
                                f"aktuellen Revision {self._revision}."
                            ),
                        ),
                    ),
                )

            coerced: Dict[str, Any] = {}
            errors: List[FieldError] = []
            for key, raw in changes.items():
                defn = self._registry.get(key)
                if defn is None:
                    errors.append(FieldError(key, CODE_UNKNOWN_KEY, f"{key} ist unbekannt."))
                    continue
                if defn.scope == SCOPE_SERVER:
                    errors.append(
                        FieldError(
                            field=key,
                            code=CODE_WRONG_SCOPE,
                            message=(
                                f"{key} ist eine Servereinstellung und kann "
                                "nicht über die Session gepatcht werden."
                            ),
                        )
                    )
                    continue
                if not defn.writable:
                    errors.append(
                        FieldError(
                            field=key,
                            code=CODE_READ_ONLY_AUTHORITY,
                            message=(
                                f"{key} ist kein Session-Patch-Schlüssel; die "
                                "Runtime-Schreibautorität ist "
                                "`trigger_suppression.set`."
                            ),
                        )
                    )
                    continue
                candidate, error = coerce_definition_value(defn, raw)
                if error is not None:
                    errors.append(error)
                    continue
                if self._validate_key is not None:
                    errors.extend(self._validate_key(key, candidate))
                    if any(error.field == key for error in errors):
                        continue
                coerced[key] = candidate

            if not errors:
                # Cross-field rule against the *final* candidate of the whole
                # transaction, never against an intermediate order.
                proposal = dict(self._effective)
                proposal.update(coerced)
                errors.extend(validate_timing_bundle(self._registry, coerced, proposal))

            if errors:
                ordered = sorted(
                    errors, key=lambda item: (str(item.field), str(item.code))
                )
                return PatchResult(
                    accepted=False,
                    result=RESULT_REJECTED,
                    settings_revision=self._revision,
                    errors=tuple(ordered),
                )

            if not coerced:
                return PatchResult(
                    accepted=False,
                    result=RESULT_REJECTED,
                    settings_revision=self._revision,
                    errors=(
                        FieldError(
                            field="changes",
                            code=CODE_INVALID_PAYLOAD,
                            message="Es wurden keine änderbaren Werte angegeben.",
                        ),
                    ),
                )

            changed_keys = [
                key for key, value in coerced.items()
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
                if policy == APPLY_LIVE:
                    next_effective[key] = value
                elif policy == APPLY_NEXT_ACTIVATION:
                    next_effective[key] = value
                elif policy == APPLY_NEXT_SESSION:
                    # Reconnect-pflichtig: erst die nächste Session macht diese
                    # Werte wirksam; die laufende Session behält ihren Wert.
                    continue
                else:  # APPLY_SERVER_RESTART
                    continue

            self._revision += 1
            self._requested = next_requested
            self._effective = next_effective

            policies = {
                key: self._registry.get(key).apply_policy for key in changed_keys
            }
            return PatchResult(
                accepted=True,
                result=RESULT_APPLIED,
                settings_revision=self._revision,
                changed_keys=tuple(sorted(changed_keys)),
                values=dict(self._requested),
                effective_values=dict(self._effective),
                apply_policies=policies,
            )

    def freeze_activation(self) -> Mapping[str, Any]:
        """Immutable snapshot for the next activation admission.

        Only ``next_activation`` values are latched into the activation; live
        values (runtime suppression) are read live and are never part of an
        activation snapshot. A running activation keeps its freeze and a later
        patch returns a *different* freeze for the next activation.
        """
        with self._lock:
            frozen: Dict[str, Any] = {}
            for key in sorted(self._requested):
                defn = self._registry.get(key)
                if defn is None:
                    continue
                if defn.apply_policy == APPLY_NEXT_ACTIVATION:
                    frozen[key] = _freeze(_thaw(self._effective[key]))
            return _freeze(frozen)

    def activation_timings_seconds(self) -> Dict[str, float]:
        """Second-based timing values lazily derived (kept for compatibility)."""
        frozen = self.freeze_activation()
        timings: Dict[str, float] = {}
        for key in TIMING_KEYS:
            value = frozen.get(key)
            if value is not None:
                timings[key] = float(value) / 1000.0
        return timings

    def activation_admission_settings(self) -> ActivationAdmissionSettings:
        """The single atomic settings read for one activation admission.

        Effective wire settings, all six timing values and the revision are
        taken from the very same locked snapshot, so an admission can never mix
        two settings revisions (AP-SRV-050 C2 F3).
        """
        with self._lock:
            effective: Dict[str, Any] = {}
            timing: Dict[str, float] = {}
            for key in sorted(self._requested):
                definition = self._registry.get(key)
                if definition is None or definition.scope != SCOPE_SESSION:
                    continue
                value = _thaw(self._effective[key])
                effective[key] = value
                if key in TIMING_KEYS and value is not None:
                    timing[key] = float(value) / 1000.0
            return ActivationAdmissionSettings(
                settings_revision=self._revision,
                effective_settings=_freeze(effective),
                timing_seconds=_freeze(timing),
            )

    def settings_projection(self) -> SessionSettingsProjection:
        """One atomic read of revision/requested/effective for the wire.

        Reads all three under a single ``self._lock`` section and returns them
        defensively immutable, so a snapshot never spans two settings revisions
        (AP-SRV-050 C3). The running-activation latch and runtime suppression
        are applied by the session/port *after* this snapshot.
        """
        with self._lock:
            requested: Dict[str, Any] = {}
            effective: Dict[str, Any] = {}
            for key in sorted(self._requested):
                definition = self._registry.get(key)
                if definition is None or definition.scope != SCOPE_SESSION:
                    continue
                requested[key] = _thaw(self._requested[key])
                effective[key] = _thaw(self._effective[key])
            return SessionSettingsProjection(
                settings_revision=self._revision,
                requested_settings=_freeze(requested),
                effective_settings=_freeze(effective),
            )


# -- server control plane -------------------------------------------------------

class ServerSettingsState:
    """Admin-managed server default overlay with its own revision stream."""

    def __init__(
        self,
        registry: SettingsRegistry,
        *,
        overlay: Optional[Mapping[str, Any]] = None,
        revision: int = 0,
        persist: Optional[Callable[[Mapping[str, Any], int], None]] = None,
    ):
        self._registry = registry
        self._lock = threading.RLock()
        # AP-SRV-050 C2 F4: persisted control data is validated strictly at
        # startup - a manually damaged or half-written runtime JSON must never
        # boot the control plane with out-of-band defaults.
        if isinstance(revision, bool):
            raise ValueError(
                "Invalid settingsControlOverlay: settingsRevision darf kein "
                "boolescher Wert sein."
            )
        revision = int(revision)
        if revision < 0:
            raise ValueError(
                "Invalid settingsControlOverlay: settingsRevision darf nicht "
                "negativ sein."
            )
        self._revision = revision
        self._persist = persist
        if overlay is not None and not isinstance(overlay, dict):
            raise ValueError(
                "Invalid settingsControlOverlay: muss ein Objekt sein."
            )
        loaded = dict(overlay) if overlay else {}
        for key in loaded:
            definition = registry.get(key)
            if definition is None or not definition.has_server_default:
                raise ValueError(
                    f"Invalid settingsControlOverlay: {key} / "
                    "kein admin-managed Serverdefault."
                )
            if definition.secret:
                raise ValueError(
                    f"Invalid settingsControlOverlay: {key} / secret_not_allowed"
                )
            coerced, error = coerce_definition_value(definition, loaded[key])
            if error is not None:
                raise ValueError(
                    f"Invalid settingsControlOverlay: {key} / {error.code}"
                )
            loaded[key] = coerced
        # validate the fully merged candidate (defaults + persisted values)
        # against the same rules a patch would use
        candidate = registry.defaults_for_server_defaults()
        candidate.update(loaded)
        persisted_errors = validate_timing_bundle(registry, loaded, candidate)
        if persisted_errors:
            first = persisted_errors[0]
            raise ValueError(
                f"Invalid settingsControlOverlay: {first.field} / {first.code}"
            )
        self._overlay: Dict[str, Any] = {}
        for key in sorted(registry.server_default_keys()):
            definition = registry.get(key)
            if definition is None:
                continue
            self._overlay[key] = _coerce_copy(
                candidate.get(key, definition.default_value)
            )
        self._server_effective: Dict[str, Any] = dict(self._overlay)

    @property
    def settings_revision(self) -> int:
        with self._lock:
            return self._revision

    @property
    def registry(self) -> SettingsRegistry:
        return self._registry

    def overlay(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._overlay)

    def server_effective(self) -> Dict[str, Any]:
        """What new sessions inherit right now."""
        with self._lock:
            return dict(self._server_effective)

    def patch_server(
        self, base_revision: Any, changes: Mapping[str, Any]
    ) -> PatchResult:
        """Transactional admin patch of server-managed defaults."""
        revision, changes, envelope_error = validate_patch_envelope(base_revision, changes)
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
                            code=CODE_STALE_REVISION,
                            message=(
                                "baseSettingsRevision entspricht nicht der "
                                f"aktuellen Revision {self._revision}."
                            ),
                        ),
                    ),
                )

            coerced: Dict[str, Any] = {}
            errors: List[FieldError] = []
            for key, raw in changes.items():
                defn = self._registry.get(key)
                if defn is None:
                    errors.append(FieldError(key, CODE_UNKNOWN_KEY, f"{key} ist unbekannt."))
                    continue
                if not defn.has_server_default:
                    errors.append(
                        FieldError(
                            field=key,
                            code=CODE_WRONG_SCOPE,
                            message=(
                                f"{key} besitzt kein admin-managed "
                                "Serverdefault; sein Wert ist sessionseitig."
                            ),
                        )
                    )
                    continue
                if defn.secret:
                    errors.append(
                        FieldError(
                            field=key,
                            code=CODE_READ_ONLY_AUTHORITY,
                            message=f"{key} ist ein Secret und nicht patchbar.",
                        )
                    )
                    continue
                candidate, error = coerce_definition_value(defn, raw)
                if error is not None:
                    errors.append(error)
                    continue
                coerced[key] = candidate

            if not errors:
                proposal = dict(self._overlay)
                proposal.update(coerced)
                errors.extend(validate_timing_bundle(self._registry, coerced, proposal))

            if errors:
                ordered = sorted(errors, key=lambda item: (str(item.field), str(item.code)))
                return PatchResult(
                    accepted=False,
                    result=RESULT_REJECTED,
                    settings_revision=self._revision,
                    errors=tuple(ordered),
                )

            changed_keys = [
                key for key, value in coerced.items()
                if self._overlay.get(key) != value
            ]
            if not changed_keys:
                return PatchResult(
                    accepted=True,
                    result=RESULT_NO_CHANGE,
                    settings_revision=self._revision,
                    values=dict(self._overlay),
                    effective_values=dict(self._server_effective),
                    apply_policies={
                        key: self._registry.get(key).apply_policy
                        for key in self._overlay
                    },
                )

            # Prepare -> persist -> commit (AP-SRV-050 C2 F5). The next state is
            # built as copies and persisted *before* any live mutation; if the
            # store fails, RAM and revision stay untouched and the caller gets a
            # machine-readable internal_error instead of a half commit.
            next_overlay = dict(self._overlay)
            next_overlay.update(coerced)
            next_effective = dict(self._server_effective)
            for key, value in coerced.items():
                policy = self._registry.get(key).apply_policy
                if policy != APPLY_SERVER_RESTART:
                    next_effective[key] = value
            next_revision = self._revision + 1
            if self._persist is not None and callable(self._persist):
                try:
                    self._persist(next_overlay, next_revision)
                except Exception:
                    return PatchResult(
                        accepted=False,
                        result=RESULT_INTERNAL_ERROR,
                        settings_revision=self._revision,
                        errors=(
                            FieldError(
                                field="persistence",
                                code=CODE_PERSISTENCE_FAILED,
                                message=(
                                    "Servereinstellungen konnten nicht "
                                    "persistent gespeichert werden."
                                ),
                            ),
                        ),
                    )
            self._overlay = next_overlay
            self._server_effective = next_effective
            self._revision = next_revision
            requires_restart = any(
                self._registry.get(key) is not None
                and self._registry.get(key).apply_policy == APPLY_SERVER_RESTART
                for key in changed_keys
            )
            return PatchResult(
                accepted=True,
                result=RESULT_APPLIED,
                settings_revision=self._revision,
                changed_keys=tuple(sorted(changed_keys)),
                values=dict(self._overlay),
                effective_values=dict(self._server_effective),
                apply_policies={
                    key: self._registry.get(key).apply_policy for key in changed_keys
                },
                requires_restart=requires_restart,
            )

    def server_public(self, *, server_version="", server_commit="unknown") -> Dict[str, Any]:
        """Non-secret requested/effective values of admin-managed defaults."""
        with self._lock:
            overlay = dict(self._overlay)
            effective = dict(self._server_effective)
            revision = self._revision
        entries = []
        for key in sorted(overlay):
            definition = self._registry.get(key)
            if definition is None:
                continue
            if definition.secret:
                entries.append({
                    "key": key,
                    "scope": definition.scope,
                    "auth": definition.auth,
                    "type": definition.type,
                    "redacted": True,
                    "applyPolicy": definition.apply_policy,
                })
                continue
            entries.append({
                "key": key,
                "scope": definition.scope,
                "auth": definition.auth,
                "type": definition.type,
                "constraints": dict(definition.constraints),
                "requestedValue": _thaw(overlay[key]),
                "effectiveValue": _thaw(effective.get(key, overlay[key])),
                "applyPolicy": definition.apply_policy,
            })
        return {
            "protocolVersion": 2,
            "serverVersion": server_version,
            "serverCommit": server_commit,
            "settingsRevision": revision,
            "settings": entries,
        }