"""Frozen value sets of the AP-SRV-050 settings control plane.

The enums here are the only place that names the wire-level concepts of the
settings contract. Product modules import these names instead of spreading
bare strings through the code base.
"""

from enum import Enum


class SettingScope(str, Enum):
    """Who owns and persists a setting value."""

    SESSION = "session"
    SERVER = "server"
    CLIENT_LOCAL = "client_local"


class AuthRequirement(str, Enum):
    """Who may change a setting."""

    SESSION = "session"
    ADMIN = "admin"


class ApplyPolicy(str, Enum):
    """When a confirmed change becomes effective."""

    LIVE = "live"
    NEXT_ACTIVATION = "next_activation"
    NEXT_SESSION = "next_session"
    SERVER_RESTART = "server_restart"


class SettingType(str, Enum):
    """JSON-safe value type of a setting."""

    INT = "int"
    FLOAT = "float"
    BOOL = "bool"
    STRING = "string"
    STRING_LIST = "string_list"


# The six contract requirements that a successful change can confirm with an
# accepted result. ``applied`` / ``no_change`` are the only ones a command
# ready to be projected into a v2 ``command.ack`` may confirm with ``true``.
RESULT_APPLIED = "applied"
RESULT_NO_CHANGE = "no_change"
RESULT_REVISION_CONFLICT = "settings_revision_conflict"
RESULT_REJECTED = "settings_rejected"