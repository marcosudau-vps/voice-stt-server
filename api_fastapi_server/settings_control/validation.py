"""Value validation and coercion of the settings control plane.

All checks here are pure. A change is only accepted after *every* field of a
patch passed; the control plane never applies a partial patch.
"""

import numbers
from typing import Any, Dict, List, Mapping, Optional, Tuple

from .model import FieldError, SettingDefinition
from .registry import (
    ACTIVATION_WATCHDOG_WARNING,
    SettingsRegistry,
    WATCHDOG_WARNING_LESS_THAN_KEYS,
)

#: Codes used in machine-readable field errors.
UNKNOWN_KEY = "unknown_key"
INVALID_TYPE = "invalid_type"
OUT_OF_RANGE = "out_of_range"
INVALID_VALUE = "invalid_value"
TOO_FEW_ITEMS = "too_few_items"
CROSS_FIELD_CONFLICT = "cross_field_conflict"


def _error(field: str, code: str, message: str) -> FieldError:
    return FieldError(field=field, code=code, message=message)


def coerce_and_validate(
    definition: SettingDefinition,
    value: Any,
) -> Tuple[Optional[Any], Optional[FieldError]]:
    """Coerces and validates one value against its definition.

    Returns ``(coerced, None)`` on success and ``(None, FieldError)`` on
    failure. ``bool`` is never accepted for numeric types.
    """
    value_type = definition.type
    is_number = value_type in {"int", "float"}
    if is_number and isinstance(value, bool):
        return None, _error(
            definition.key,
            INVALID_TYPE,
            f"{definition.key} muss eine Zahl sein.",
        )
    if value_type == "int":
        if not isinstance(value, int):
            return None, _error(
                definition.key,
                INVALID_TYPE,
                f"{definition.key} muss eine Ganzzahl sein.",
            )
        value = int(value)
    elif value_type == "float":
        if not isinstance(value, numbers.Real) or isinstance(value, bool):
            return None, _error(
                definition.key,
                INVALID_TYPE,
                f"{definition.key} muss eine Zahl sein.",
            )
        value = float(value)
        if not _finite(value):
            return None, _error(
                definition.key,
                INVALID_VALUE,
                f"{definition.key} muss endlich sein.",
            )
    elif value_type == "bool":
        if not isinstance(value, bool):
            return None, _error(
                definition.key,
                INVALID_TYPE,
                f"{definition.key} muss ein boolescher Wert sein.",
            )
    elif value_type == "string":
        if not isinstance(value, str) or not value:
            return None, _error(
                definition.key,
                INVALID_TYPE,
                f"{definition.key} muss eine nicht leere Zeichenfolge sein.",
            )
    elif value_type == "string_list":
        if not isinstance(value, (list, tuple)):
            return None, _error(
                definition.key,
                INVALID_TYPE,
                f"{definition.key} muss eine Liste sein.",
            )
        for item in value:
            if not isinstance(item, str) or not item:
                return None, _error(
                    definition.key,
                    INVALID_TYPE,
                    f"{definition.key} darf nur nicht leere IDs enthalten.",
                )
        value = list(value)
    else:
        return None, _error(
            definition.key,
            INVALID_TYPE,
            f"{definition.key} besitzt einen unbekannten Typ.",
        )

    error = _validate_constraints(definition, value)
    return (value, None) if error is None else (None, error)


def _finite(value):
    try:
        import math

        return math.isfinite(value)
    except TypeError:
        return False


def _validate_constraints(definition: SettingDefinition, value: Any):
    constraints = definition.constraints or {}
    minimum = constraints.get("min")
    maximum = constraints.get("max")
    if minimum is not None and value < minimum:
        return _error(
            definition.key,
            OUT_OF_RANGE,
            f"{definition.key} muss mindestens {minimum} betragen.",
        )
    if maximum is not None and value > maximum:
        return _error(
            definition.key,
            OUT_OF_RANGE,
            f"{definition.key} darf höchstens {maximum} betragen.",
        )
    allowed = constraints.get("allowed")
    if allowed is not None and value not in allowed:
        return _error(
            definition.key,
            INVALID_VALUE,
            f"{definition.key} ist kein zulässiger Wert.",
        )
    min_items = constraints.get("minItems")
    if min_items is not None and len(value) < min_items:
        return _error(
            definition.key,
            TOO_FEW_ITEMS,
            f"{definition.key} muss mindestens {min_items} Einträge besitzen.",
        )
    return None


def validate_change(
    registry: SettingsRegistry,
    key: str,
    value: Any,
) -> Tuple[Optional[Any], Optional[FieldError]]:
    definition = registry.get(key)
    if definition is None:
        return None, _error(key, UNKNOWN_KEY, f"{key} ist unbekannt.")
    return coerce_and_validate(definition, value)


def validate_timing_bundle(
    registry: SettingsRegistry,
    changes: Mapping[str, Any],
    current: Mapping[str, Any],
) -> List[FieldError]:
    """Cross-field rule of the watchdog warning.

    ``activation.segmentWatchdogWarningMs`` must be strictly smaller than the
    currently effective value of every watchdog deadline it can accompany
    (initial and refresh). Values in ``changes`` win over ``current``.
    """
    if ACTIVATION_WATCHDOG_WARNING not in changes:
        return []
    warning = changes.get(ACTIVATION_WATCHDOG_WARNING)
    if warning is None:
        return []
    if not isinstance(warning, int) or isinstance(warning, bool):
        return []
    errors = []
    for deadline_key in WATCHDOG_WARNING_LESS_THAN_KEYS:
        effective = (
            changes.get(deadline_key)
            if deadline_key in changes
            else current.get(deadline_key)
        )
        if effective is None or not isinstance(effective, int):
            continue
        if warning >= effective:
            errors.append(
                _error(
                    ACTIVATION_WATCHDOG_WARNING,
                    CROSS_FIELD_CONFLICT,
                    (
                        f"{ACTIVATION_WATCHDOG_WARNING} muss kleiner sein als "
                        f"die wirksame Frist von {deadline_key} "
                        f"({effective} ms)."
                    ),
                )
            )
    return errors


def validate_patch_envelope(
    base_revision: Any,
    changes: Any,
) -> Tuple[
    Optional[int], Optional[Dict[str, Any]], Optional[FieldError]
]:
    if isinstance(base_revision, bool) or not isinstance(base_revision, int):
        return None, None, _error(
            "baseSettingsRevision",
            INVALID_TYPE,
            "baseSettingsRevision muss eine nicht negative Ganzzahl sein.",
        )
    if base_revision < 0:
        return None, None, _error(
            "baseSettingsRevision",
            OUT_OF_RANGE,
            "baseSettingsRevision muss nicht negativ sein.",
        )
    if not isinstance(changes, dict) or not changes:
        return None, None, _error(
            "changes",
            INVALID_TYPE,
            "changes muss ein nicht leeres Objekt sein.",
        )
    return int(base_revision), changes, None