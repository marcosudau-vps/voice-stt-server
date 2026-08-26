"""Settings registry: the single source of truth for settings keys.

The registry owns key names, scope, auth, type, constraints, defaults and
apply policies. No product module may carry a second loose list of these keys.
"""

from dataclasses import dataclass, field
from typing import Dict, FrozenSet, Iterable, List, Mapping, Optional

from .enums import (
    ApplyPolicy,
    AuthRequirement,
    SettingScope,
    SettingType,
)
from .model import SettingDefinition

#: Window in which a new activation may wait for its first speech.
ACTIVATION_INITIAL_SPEECH = "activation.initialSpeechTimeoutMs"
#: Follow-up window after a regular segment end.
ACTIVATION_FOLLOWUP = "activation.followupTimeoutMs"
#: Segment watchdog deadline when a segment starts.
ACTIVATION_WATCHDOG_INITIAL = "activation.segmentWatchdogInitialMs"
#: Minimum remaining time a ``refresh`` secures inside ``segment_active``.
ACTIVATION_WATCHDOG_REFRESH = "activation.segmentWatchdogRefreshMs"
#: Warning lead time before the watchdog deadline.
ACTIVATION_WATCHDOG_WARNING = "activation.segmentWatchdogWarningMs"
#: ``closing_input`` recovery timeout.
ACTIVATION_CLOSING_RECOVERY = "activation.closingRecoveryTimeoutMs"

WAKE_WORD_SENSITIVITY = "wakeWord.sensitivity"
WAKE_WORD_SELECTION = "wakeWord.selection"
WAKE_WORD_GLOBAL_DISABLED = "wakeWord.globalDisabledIds"

RUNTIME_SUPPRESSION_MANUAL = "runtimeSuppression.manual"
RUNTIME_SUPPRESSION_WAKE_WORD = "runtimeSuppression.wakeWord"

#: The contract-frozen activation timings, in milliseconds internally.
_ACTIVATION_TIMING_KEYS = frozenset(
    {
        ACTIVATION_INITIAL_SPEECH,
        ACTIVATION_FOLLOWUP,
        ACTIVATION_WATCHDOG_INITIAL,
        ACTIVATION_WATCHDOG_REFRESH,
        ACTIVATION_WATCHDOG_WARNING,
        ACTIVATION_CLOSING_RECOVERY,
    }
)

#: Cross-field rule of the watchdog warning: it must be strictly smaller than
#: every currently effective watchdog deadline it can accompany.
WATCHDOG_WARNING_LESS_THAN_KEYS = (
    ACTIVATION_WATCHDOG_INITIAL,
    ACTIVATION_WATCHDOG_REFRESH,
)


def builtin_definitions() -> List[SettingDefinition]:
    """The server-managed settings keys of the frozen contract.

    The six trigger timings use milliseconds on the public schema. Sessions
    own the values (Sessionrecht); the registry also exposes each as an
    admin-managed server default facet (``has_server_default``), so an admin
    may change what a new session inherits through the server REST surface.
    """
    return [
        SettingDefinition(
            key=ACTIVATION_INITIAL_SPEECH,
            scope=SettingScope.SESSION.value,
            auth=AuthRequirement.SESSION.value,
            type=SettingType.INT.value,
            constraints={"min": 100, "max": 3600000, "unit": "ms"},
            default_value=15000,
            apply_policy=ApplyPolicy.NEXT_ACTIVATION.value,
            description=(
                "Wartezeit auf die erste Sprache einer neuen Activation."
            ),
            has_server_default=True,
        ),
        SettingDefinition(
            key=ACTIVATION_FOLLOWUP,
            scope=SettingScope.SESSION.value,
            auth=AuthRequirement.SESSION.value,
            type=SettingType.INT.value,
            constraints={"min": 100, "max": 60000, "unit": "ms"},
            default_value=3000,
            apply_policy=ApplyPolicy.NEXT_ACTIVATION.value,
            description=(
                "Nachfragefenster nach einem beendeten Segment derselben "
                "Activation."
            ),
            has_server_default=True,
        ),
        SettingDefinition(
            key=ACTIVATION_WATCHDOG_INITIAL,
            scope=SettingScope.SESSION.value,
            auth=AuthRequirement.SESSION.value,
            type=SettingType.INT.value,
            constraints={"min": 60000, "max": 3600000, "unit": "ms"},
            default_value=600000,
            apply_policy=ApplyPolicy.NEXT_ACTIVATION.value,
            description="Segment-Watchdog-Deadline beim Segmentstart.",
            has_server_default=True,
        ),
        SettingDefinition(
            key=ACTIVATION_WATCHDOG_REFRESH,
            scope=SettingScope.SESSION.value,
            auth=AuthRequirement.SESSION.value,
            type=SettingType.INT.value,
            constraints={"min": 30000, "max": 600000, "unit": "ms"},
            default_value=180000,
            apply_policy=ApplyPolicy.NEXT_ACTIVATION.value,
            description=(
                "Mindest-Restzeit, die ein Refresh in `segment_active` "
                "sichert."
            ),
            has_server_default=True,
        ),
        SettingDefinition(
            key=ACTIVATION_WATCHDOG_WARNING,
            scope=SettingScope.SESSION.value,
            auth=AuthRequirement.SESSION.value,
            type=SettingType.INT.value,
            constraints={
                "min": 5000,
                "unit": "ms",
                "lessThanKeys": list(WATCHDOG_WARNING_LESS_THAN_KEYS),
            },
            default_value=30000,
            apply_policy=ApplyPolicy.NEXT_ACTIVATION.value,
            description=(
                "Vorwarnzeit vor dem Watchdog-Ablauf. Muss kleiner sein als "
                "die jeweils wirksame Watchdog-Frist."
            ),
            has_server_default=True,
        ),
        SettingDefinition(
            key=ACTIVATION_CLOSING_RECOVERY,
            scope=SettingScope.SESSION.value,
            auth=AuthRequirement.SESSION.value,
            type=SettingType.INT.value,
            constraints={"min": 1000, "max": 30000, "unit": "ms"},
            default_value=5000,
            apply_policy=ApplyPolicy.NEXT_ACTIVATION.value,
            description="Recoveryfrist in `closing_input`.",
            has_server_default=True,
        ),
        SettingDefinition(
            key=WAKE_WORD_SENSITIVITY,
            scope=SettingScope.SESSION.value,
            auth=AuthRequirement.SESSION.value,
            type=SettingType.FLOAT.value,
            constraints={"min": 0.0, "max": 1.0},
            default_value=0.5,
            apply_policy=ApplyPolicy.NEXT_ACTIVATION.value,
            description=(
                "Gemeinsame Wake-Word-Empfindlichkeit der Session. Der Server "
                "validiert und veröffentlicht den tatsächlich aufgelösten "
                "Wert."
            ),
            has_server_default=True,
        ),
        SettingDefinition(
            key=WAKE_WORD_SELECTION,
            scope=SettingScope.SESSION.value,
            auth=AuthRequirement.SESSION.value,
            type=SettingType.STRING_LIST.value,
            constraints={"minItems": 0},
            default_value=[],
            apply_policy=ApplyPolicy.NEXT_SESSION.value,
            description=(
                "Kanonische IDs der für die Session gewählten Wake Words. "
                "Wirkt auf neu aufgebaute Sessions. Die atomare Admission "
                "gehört AP-SRV-060."
            ),
        ),
        SettingDefinition(
            key=RUNTIME_SUPPRESSION_MANUAL,
            scope=SettingScope.SESSION.value,
            auth=AuthRequirement.SESSION.value,
            type=SettingType.BOOL.value,
            constraints={},
            default_value=False,
            apply_policy=ApplyPolicy.LIVE.value,
            description=(
                "Laufzeit-Unterdrückung der manuellen Triggerquelle. Wirkt "
                "live für neue Admissions; eine laufende Activation wird "
                "nicht umgequelt."
            ),
        ),
        SettingDefinition(
            key=RUNTIME_SUPPRESSION_WAKE_WORD,
            scope=SettingScope.SESSION.value,
            auth=AuthRequirement.SESSION.value,
            type=SettingType.BOOL.value,
            constraints={},
            default_value=False,
            apply_policy=ApplyPolicy.LIVE.value,
            description=(
                "Laufzeit-Unterdrückung der Wake-Word-Quelle. Wirkt live für "
                "neue Admissions; eine laufende Activation wird nicht "
                "umgequelt."
            ),
        ),
        SettingDefinition(
            key=WAKE_WORD_GLOBAL_DISABLED,
            scope=SettingScope.SERVER.value,
            auth=AuthRequirement.ADMIN.value,
            type=SettingType.STRING_LIST.value,
            constraints={"minItems": 0},
            default_value=[],
            apply_policy=ApplyPolicy.NEXT_SESSION.value,
            description=(
                "Global deaktivierte Wake-Word-Katalog-IDs. Wirkt auf neue "
                "Sessions. Der Katalog selbst gehört AP-SRV-060."
            ),
            has_server_default=True,
        ),
    ]


def coerce_default_value(raw):
    """Returns a defensive JSON-safe copy of a registry default value."""
    if raw is None:
        return None
    if isinstance(raw, list):
        return list(raw)
    if isinstance(raw, tuple):
        return list(raw)
    return raw


@dataclass(frozen=True)
class SettingsRegistry:
    """Read-only catalog of all server-managed settings keys."""

    definitions: Mapping[str, SettingDefinition] = field(default_factory=dict)

    def __init__(
        self,
        definitions: Optional[Iterable[SettingDefinition]] = None,
    ):
        entries = {}
        for definition in definitions or builtin_definitions():
            entries[definition.key] = definition
        object.__setattr__(self, "definitions", entries)

    def get(self, key: str) -> Optional[SettingDefinition]:
        return self.definitions.get(key)

    def __contains__(self, key):
        return key in self.definitions

    def keys(self) -> FrozenSet[str]:
        return frozenset(self.definitions)

    def session_keys(self) -> FrozenSet[str]:
        return frozenset(
            key
            for key, definition in self.definitions.items()
            if definition.scope == SettingScope.SESSION.value
        )

    def server_keys(self) -> FrozenSet[str]:
        return frozenset(
            key
            for key, definition in self.definitions.items()
            if definition.scope == SettingScope.SERVER.value
        )

    def admin_keys(self) -> FrozenSet[str]:
        return frozenset(
            key
            for key, definition in self.definitions.items()
            if definition.auth == AuthRequirement.ADMIN.value
        )

    def is_secret(self, key: str) -> bool:
        definition = self.definitions.get(key)
        return bool(definition and definition.secret)

    def has_server_default(self, key: str) -> bool:
        definition = self.definitions.get(key)
        return bool(definition and definition.has_server_default)

    def defaults(self) -> Dict[str, object]:
        return {
            key: coerce_default_value(definition.default_value)
            for key, definition in self.definitions.items()
        }

    def defaults_for_server_defaults(self) -> Dict[str, object]:
        """Default values of every admin-managed server-default key."""
        return {
            key: coerce_default_value(definition.default_value)
            for key, definition in self.definitions.items()
            if definition.has_server_default
        }

    def schema_payload(self) -> List[dict]:
        """Public schema definitions; never requested/effective values."""
        return [
            definition.to_schema_dict()
            for definition in self.definitions.values()
        ]


def build_default_registry() -> SettingsRegistry:
    return SettingsRegistry()


def timing_keys() -> FrozenSet[str]:
    return _ACTIVATION_TIMING_KEYS