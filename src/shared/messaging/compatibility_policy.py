"""Standardized event compatibility policy.

Defines breaking-change rules, consumer tolerance, and shim deprecation
contracts applicable to all modules.

Rules:
 1. Breaking changes require a new event_version.
 2. Consumers must tolerate extra/unknown fields in the payload.
 3. Removing a previously required field requires a new version.
 4. Changing field semantics (type, meaning) requires a new version.
 5. Event shims must have a removal date and a final test that fails
    if the shim persists after the cutoff date.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


class CompatibilityAction(str, enum.Enum):
    ACCEPT = "accept"
    ACCEPT_WITH_WARNING = "accept_with_warning"
    REJECT = "reject"


class FieldChangeType(str, enum.Enum):
    ADDED_OPTIONAL = "added_optional"
    ADDED_REQUIRED = "added_required"
    REMOVED_REQUIRED = "removed_required"
    REMOVED_OPTIONAL = "removed_optional"
    TYPE_CHANGED = "type_changed"
    SEMANTICS_CHANGED = "semantics_changed"


class CompatibilityError(ValueError):
    pass


BREAKING_CHANGE_TYPES: frozenset[str] = frozenset(
    [
        FieldChangeType.REMOVED_REQUIRED.value,
        FieldChangeType.TYPE_CHANGED.value,
        FieldChangeType.SEMANTICS_CHANGED.value,
    ]
)

NON_BREAKING_CHANGE_TYPES: frozenset[str] = frozenset(
    [
        FieldChangeType.ADDED_OPTIONAL.value,
        FieldChangeType.ADDED_REQUIRED.value,
        FieldChangeType.REMOVED_OPTIONAL.value,
    ]
)


def is_breaking_change(change_type: FieldChangeType) -> bool:
    return change_type.value in BREAKING_CHANGE_TYPES


def classify_field_change(
    field_name: str,
    old_schema: dict[str, Any] | None,
    new_schema: dict[str, Any] | None,
) -> FieldChangeType | None:
    if old_schema is None and new_schema is not None:
        required = new_schema.get("required", False)
        if required:
            return FieldChangeType.ADDED_REQUIRED
        return FieldChangeType.ADDED_OPTIONAL

    if old_schema is not None and new_schema is None:
        old_required = old_schema.get("required", False)
        if old_required:
            return FieldChangeType.REMOVED_REQUIRED
        return FieldChangeType.REMOVED_OPTIONAL

    if old_schema is not None and new_schema is not None:
        old_type = old_schema.get("type", "")
        new_type = new_schema.get("type", "")
        if old_type != new_type and old_type and new_type:
            return FieldChangeType.TYPE_CHANGED
        old_semantics = old_schema.get("semantics", "")
        new_semantics = new_schema.get("semantics", "")
        if old_semantics != new_semantics and old_semantics and new_semantics:
            return FieldChangeType.SEMANTICS_CHANGED

    return None


def validate_payload_compatibility(
    payload: dict[str, Any],
    expected_required_fields: frozenset[str],
) -> None:
    missing = expected_required_fields - set(payload.keys())
    if missing:
        raise CompatibilityError(
            f"Missing required fields in payload: {sorted(missing)}"
        )


def validate_extra_fields_tolerance(
    payload: dict[str, Any],
    known_fields: frozenset[str],
) -> CompatibilityAction:
    extra = set(payload.keys()) - known_fields
    if extra:
        return CompatibilityAction.ACCEPT_WITH_WARNING
    return CompatibilityAction.ACCEPT


def check_event_version_for_change(
    change_type: FieldChangeType,
    current_version: int,
    new_version: int,
) -> CompatibilityAction:
    if is_breaking_change(change_type) and new_version <= current_version:
        raise CompatibilityError(
            f"Breaking change ({change_type.value}) requires a new version: "
            f"current={current_version}, new={new_version}"
        )
    if is_breaking_change(change_type) and new_version > current_version:
        return CompatibilityAction.ACCEPT
    if not is_breaking_change(change_type):
        return CompatibilityAction.ACCEPT
    return CompatibilityAction.ACCEPT


@dataclass
class EventShimRegistration:
    event_type: str
    version: int
    shim_location: str
    removal_date: datetime
    description: str = ""

    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) >= self.removal_date


def validate_shim_registration(shim: EventShimRegistration) -> None:
    if not shim.event_type:
        raise CompatibilityError("event_type must not be empty")
    if shim.version < 1:
        raise CompatibilityError(f"version must be >= 1, got: {shim.version}")
    if not shim.shim_location:
        raise CompatibilityError("shim_location must not be empty")
    if shim.removal_date <= datetime.now(timezone.utc):
        raise CompatibilityError(
            f"shim removal_date ({shim.removal_date.isoformat()}) "
            f"must be in the future"
        )


def shim_must_be_removed(shim: EventShimRegistration) -> bool:
    return shim.is_expired()


def validate_payload_required_fields(
    required_fields: frozenset[str],
    payload: dict[str, Any],
) -> None:
    missing = required_fields - set(payload.keys())
    if missing:
        raise CompatibilityError(
            f"Payload missing required fields for compatibility: "
            f"{sorted(missing)}"
        )
    for field in required_fields:
        value = payload[field]
        if value is None:
            raise CompatibilityError(
                f"Required field '{field}' is null in payload"
            )
