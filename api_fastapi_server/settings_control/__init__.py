"""AP-SRV-050 settings control plane.

Public surface of the central settings registry and control plane. Product
modules use these names instead of inventing a parallel settings architecture.
"""

from .control_plane import SettingsControlPlane
from .enums import (
    ApplyPolicy,
    AuthRequirement,
    SettingScope,
    SettingType,
)
from .metadata import APP_VERSION, resolve_server_commit
from .model import FieldError, PatchResult, SettingDefinition
from .provider import (
    ActivationSettingsProvider,
    SessionActivationSettingsProvider,
    milliseconds_to_seconds,
)
from .registry import (
    ACTIVATION_CLOSING_RECOVERY,
    ACTIVATION_FOLLOWUP,
    ACTIVATION_INITIAL_SPEECH,
    ACTIVATION_WATCHDOG_INITIAL,
    ACTIVATION_WATCHDOG_REFRESH,
    ACTIVATION_WATCHDOG_WARNING,
    RUNTIME_SUPPRESSION_MANUAL,
    RUNTIME_SUPPRESSION_WAKE_WORD,
    WAKE_WORD_GLOBAL_DISABLED,
    WAKE_WORD_SELECTION,
    WAKE_WORD_SENSITIVITY,
    SettingsRegistry,
    builtin_definitions,
    build_default_registry,
    timing_keys,
)
from .session import SessionSettingsState
from .store import RuntimeSettingsStore
from .rest import create_settings_v2_router

__all__ = [
    "ACTIVATION_CLOSING_RECOVERY",
    "ACTIVATION_FOLLOWUP",
    "ACTIVATION_INITIAL_SPEECH",
    "ACTIVATION_WATCHDOG_INITIAL",
    "ACTIVATION_WATCHDOG_REFRESH",
    "ACTIVATION_WATCHDOG_WARNING",
    "APP_VERSION",
    "ActivationSettingsProvider",
    "ApplyPolicy",
    "AuthRequirement",
    "FieldError",
    "PatchResult",
    "RUNTIME_SUPPRESSION_MANUAL",
    "RUNTIME_SUPPRESSION_WAKE_WORD",
    "SessionActivationSettingsProvider",
    "SessionSettingsState",
    "SettingDefinition",
    "SettingScope",
    "SettingType",
    "SettingsControlPlane",
    "SettingsRegistry",
    "RuntimeSettingsStore",
    "WAKE_WORD_GLOBAL_DISABLED",
    "WAKE_WORD_SELECTION",
    "WAKE_WORD_SENSITIVITY",
    "builtin_definitions",
    "build_default_registry",
    "create_settings_v2_router",
    "milliseconds_to_seconds",
    "resolve_server_commit",
    "timing_keys",
]