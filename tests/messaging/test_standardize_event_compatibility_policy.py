"""Tests for spec 109 — standardize event compatibility policy."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from shared.messaging.compatibility_policy import (
    BREAKING_CHANGE_TYPES,
    NON_BREAKING_CHANGE_TYPES,
    CompatibilityAction,
    CompatibilityError,
    EventShimRegistration,
    FieldChangeType,
    check_event_version_for_change,
    classify_field_change,
    is_breaking_change,
    shim_must_be_removed,
    validate_extra_fields_tolerance,
    validate_payload_compatibility,
    validate_payload_required_fields,
    validate_shim_registration,
)


class TestBreakingChangeDetection:
    """Breaking changes require new event_version."""

    def test_removed_required_is_breaking(self):
        assert is_breaking_change(FieldChangeType.REMOVED_REQUIRED) is True

    def test_type_changed_is_breaking(self):
        assert is_breaking_change(FieldChangeType.TYPE_CHANGED) is True

    def test_semantics_changed_is_breaking(self):
        assert is_breaking_change(FieldChangeType.SEMANTICS_CHANGED) is True

    def test_added_optional_is_not_breaking(self):
        assert is_breaking_change(FieldChangeType.ADDED_OPTIONAL) is False

    def test_added_required_is_not_breaking(self):
        assert is_breaking_change(FieldChangeType.ADDED_REQUIRED) is False

    def test_removed_optional_is_not_breaking(self):
        assert is_breaking_change(FieldChangeType.REMOVED_OPTIONAL) is False

    def test_breaking_and_non_breaking_disjoint(self):
        assert not set(BREAKING_CHANGE_TYPES) & set(NON_BREAKING_CHANGE_TYPES)


class TestClassifyFieldChange:
    """Classify field changes between schemas."""

    def test_added_optional_field(self):
        result = classify_field_change("new_field", None, {"type": "string", "required": False})
        assert result == FieldChangeType.ADDED_OPTIONAL

    def test_added_required_field(self):
        result = classify_field_change("new_field", None, {"type": "string", "required": True})
        assert result == FieldChangeType.ADDED_REQUIRED

    def test_removed_required_field(self):
        result = classify_field_change("old_field", {"type": "string", "required": True}, None)
        assert result == FieldChangeType.REMOVED_REQUIRED

    def test_removed_optional_field(self):
        result = classify_field_change("old_field", {"type": "string", "required": False}, None)
        assert result == FieldChangeType.REMOVED_OPTIONAL

    def test_type_changed_field(self):
        result = classify_field_change(
            "field",
            {"type": "string", "required": True},
            {"type": "integer", "required": True},
        )
        assert result == FieldChangeType.TYPE_CHANGED

    def test_semantics_changed_field(self):
        result = classify_field_change(
            "field",
            {"type": "string", "required": True, "semantics": "user_name"},
            {"type": "string", "required": True, "semantics": "email"},
        )
        assert result == FieldChangeType.SEMANTICS_CHANGED

    def test_no_change(self):
        result = classify_field_change(
            "field",
            {"type": "string", "required": True},
            {"type": "string", "required": True},
        )
        assert result is None

    def test_both_none(self):
        result = classify_field_change("field", None, None)
        assert result is None


class TestVersionCheckForChange:
    """Breaking changes require version bump."""

    def test_breaking_change_with_newer_version(self):
        result = check_event_version_for_change(
            FieldChangeType.TYPE_CHANGED, current_version=1, new_version=2
        )
        assert result == CompatibilityAction.ACCEPT

    def test_breaking_change_with_same_version_raises(self):
        with pytest.raises(CompatibilityError, match="new version"):
            check_event_version_for_change(
                FieldChangeType.TYPE_CHANGED, current_version=1, new_version=1
            )

    def test_breaking_change_with_lower_version_raises(self):
        with pytest.raises(CompatibilityError, match="new version"):
            check_event_version_for_change(
                FieldChangeType.TYPE_CHANGED, current_version=2, new_version=1
            )

    def test_non_breaking_change_with_same_version(self):
        result = check_event_version_for_change(
            FieldChangeType.ADDED_OPTIONAL, current_version=1, new_version=1
        )
        assert result == CompatibilityAction.ACCEPT


class TestPayloadCompatibility:
    """Consumer must tolerate extra fields; missing required fields fail."""

    def test_required_fields_present(self):
        validate_payload_compatibility(
            {"name": "test", "value": 42},
            frozenset(["name", "value"]),
        )

    def test_missing_required_field_raises(self):
        with pytest.raises(CompatibilityError, match="Missing required"):
            validate_payload_compatibility(
                {"name": "test"},
                frozenset(["name", "value"]),
            )

    def test_extra_fields_are_tolerated(self):
        validate_payload_compatibility(
            {"name": "test", "extra": "ignored"},
            frozenset(["name"]),
        )

    def test_extra_fields_accept_with_warning(self):
        result = validate_extra_fields_tolerance(
            {"name": "test", "extra": "ignored"},
            frozenset(["name"]),
        )
        assert result == CompatibilityAction.ACCEPT_WITH_WARNING

    def test_no_extra_fields_accept(self):
        result = validate_extra_fields_tolerance(
            {"name": "test"},
            frozenset(["name"]),
        )
        assert result == CompatibilityAction.ACCEPT


class TestPayloadRequiredFields:
    """validate_payload_required_fields checks required fields are non-null."""

    def test_all_required_present_and_non_null(self):
        validate_payload_required_fields(
            frozenset(["id", "name"]),
            {"id": 1, "name": "test", "extra": "ok"},
        )

    def test_missing_required_field_raises(self):
        with pytest.raises(CompatibilityError, match="missing"):
            validate_payload_required_fields(
                frozenset(["id", "name"]),
                {"id": 1},
            )

    def test_null_required_field_raises(self):
        with pytest.raises(CompatibilityError, match="null"):
            validate_payload_required_fields(
                frozenset(["id", "name"]),
                {"id": 1, "name": None},
            )


class TestEventShimRegistration:
    """Shim registration with removal date."""

    def test_valid_shim(self):
        future = datetime.now(timezone.utc) + timedelta(days=90)
        shim = EventShimRegistration(
            event_type="agent.legacy_event.v1",
            version=1,
            shim_location="src/modules/agent/presentation/shim.py",
            removal_date=future,
            description="Legacy event shim",
        )
        validate_shim_registration(shim)

    def test_shim_not_expired(self):
        future = datetime.now(timezone.utc) + timedelta(days=90)
        shim = EventShimRegistration(
            event_type="agent.legacy_event.v1",
            version=1,
            shim_location="shim.py",
            removal_date=future,
        )
        assert shim_must_be_removed(shim) is False

    def test_shim_expired(self):
        past = datetime.now(timezone.utc) - timedelta(days=1)
        shim = EventShimRegistration(
            event_type="agent.legacy_event.v1",
            version=1,
            shim_location="shim.py",
            removal_date=past,
        )
        assert shim_must_be_removed(shim) is True

    def test_past_removal_date_raises_on_validation(self):
        past = datetime.now(timezone.utc) - timedelta(days=1)
        shim = EventShimRegistration(
            event_type="agent.legacy_event.v1",
            version=1,
            shim_location="shim.py",
            removal_date=past,
        )
        with pytest.raises(CompatibilityError, match="future"):
            validate_shim_registration(shim)

    def test_empty_event_type_raises(self):
        future = datetime.now(timezone.utc) + timedelta(days=90)
        shim = EventShimRegistration(
            event_type="",
            version=1,
            shim_location="shim.py",
            removal_date=future,
        )
        with pytest.raises(CompatibilityError, match="event_type"):
            validate_shim_registration(shim)

    def test_empty_shim_location_raises(self):
        future = datetime.now(timezone.utc) + timedelta(days=90)
        shim = EventShimRegistration(
            event_type="agent.legacy_event.v1",
            version=1,
            shim_location="",
            removal_date=future,
        )
        with pytest.raises(CompatibilityError, match="shim_location"):
            validate_shim_registration(shim)

    def test_zero_version_raises(self):
        future = datetime.now(timezone.utc) + timedelta(days=90)
        shim = EventShimRegistration(
            event_type="agent.legacy_event.v1",
            version=0,
            shim_location="shim.py",
            removal_date=future,
        )
        with pytest.raises(CompatibilityError, match="version"):
            validate_shim_registration(shim)

    def test_shim_default_description(self):
        future = datetime.now(timezone.utc) + timedelta(days=90)
        shim = EventShimRegistration(
            event_type="agent.legacy_event.v1",
            version=1,
            shim_location="shim.py",
            removal_date=future,
        )
        assert shim.description == ""


class TestCompatibilityIdempotency:
    """Compatibility checks are deterministic."""

    def test_payload_validation_reproducible(self):
        for _ in range(10):
            validate_payload_compatibility(
                {"a": 1, "b": 2},
                frozenset(["a", "b"]),
            )
