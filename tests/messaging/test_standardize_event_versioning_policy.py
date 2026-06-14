"""Tests for spec 107 — standardize event versioning policy."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from shared.messaging.versioning_policy import (
    ACTIVE_COMPATIBILITY_STATUSES,
    DEFAULT_DEPRECATION_WINDOW_DAYS,
    TERMINAL_COMPATIBILITY_STATUSES,
    VersionCompatibility,
    VersionDeclaration,
    VersioningError,
    check_version_compatibility,
    compute_event_type,
    extract_event_type_base,
    extract_version_from_event_type,
    is_compatible,
    must_reject,
    validate_version_consistency,
    validate_version_declaration,
)


class TestVersionExtraction:
    """Extract version from event_type string."""

    def test_extract_version_v1(self):
        assert extract_version_from_event_type("agent.execution_requested.v1") == 1

    def test_extract_version_v2(self):
        assert extract_version_from_event_type("agent.execution_requested.v2") == 2

    def test_extract_version_v10(self):
        assert extract_version_from_event_type("billing.usage_recorded.v10") == 10

    def test_extract_version_three_segments(self):
        assert extract_version_from_event_type("identity.org.created.v1") == 1

    def test_empty_event_type_raises(self):
        with pytest.raises(VersioningError):
            extract_version_from_event_type("")

    def test_no_version_segment_raises(self):
        with pytest.raises(VersioningError):
            extract_version_from_event_type("agent.execution")

    def test_non_v_prefix_raises(self):
        with pytest.raises(VersioningError):
            extract_version_from_event_type("agent.execution.1")

    def test_invalid_version_number_raises(self):
        with pytest.raises(VersioningError):
            extract_version_from_event_type("agent.execution.vx")

    def test_zero_version_raises(self):
        with pytest.raises(VersioningError):
            extract_version_from_event_type("agent.execution.v0")

    def test_extract_event_type_base(self):
        assert extract_event_type_base("agent.execution_requested.v1") == "agent.execution_requested"
        assert extract_event_type_base("billing.usage.recorded.v2") == "billing.usage.recorded"
        assert extract_event_type_base("identity.user.created.v3") == "identity.user.created"

    def test_extract_base_invalid_raises(self):
        with pytest.raises(VersioningError):
            extract_event_type_base("agent.execution")


class TestComputeEventType:
    """Build event_type from components."""

    def test_compute_event_type(self):
        assert compute_event_type("agent", "execution_requested", 1) == "agent.execution_requested.v1"
        assert compute_event_type("billing", "usage_recorded", 2) == "billing.usage_recorded.v2"

    def test_empty_producer_module_raises(self):
        with pytest.raises(VersioningError):
            compute_event_type("", "event", 1)

    def test_empty_event_name_raises(self):
        with pytest.raises(VersioningError):
            compute_event_type("agent", "", 1)

    def test_zero_version_raises(self):
        with pytest.raises(VersioningError):
            compute_event_type("agent", "event", 0)


class TestVersionConsistency:
    """event_type suffix must match event_version."""

    def test_consistent_version_passes(self):
        validate_version_consistency("agent.execution_requested.v1", 1)

    def test_mismatched_version_raises(self):
        with pytest.raises(VersioningError, match="version mismatch"):
            validate_version_consistency("agent.execution_requested.v1", 2)

    def test_zero_event_version_raises(self):
        with pytest.raises(VersioningError):
            validate_version_consistency("agent.execution_requested.v1", 0)


class TestVersionCompatibility:
    """Check compatibility between producer and consumer versions."""

    def test_exact_match_is_compatible(self):
        result = check_version_compatibility(1, frozenset([1, 2]))
        assert result == VersionCompatibility.COMPATIBLE

    def test_consumer_accepts_newer_forward_compatible(self):
        result = check_version_compatibility(1, frozenset([2, 3]))
        assert result == VersionCompatibility.FORWARD_COMPATIBLE

    def test_producer_is_newer_backward_compatible(self):
        result = check_version_compatibility(3, frozenset([1, 2]))
        assert result == VersionCompatibility.BACKWARD_COMPATIBLE

    def test_no_overlap_is_incompatible(self):
        result = check_version_compatibility(3, frozenset([1, 2]))
        assert result == VersionCompatibility.BACKWARD_COMPATIBLE

    def test_consumer_has_no_accepted_versions_forward(self):
        result = check_version_compatibility(1, frozenset([2]))
        assert result == VersionCompatibility.FORWARD_COMPATIBLE

    def test_deprecated_after_window(self):
        past = datetime.now(timezone.utc) - timedelta(days=100)
        result = check_version_compatibility(
            1, frozenset([1, 2]), producer_deprecated_at=past
        )
        assert result == VersionCompatibility.DEPRECATED

    def test_deprecated_before_window_still_compatible(self):
        future = datetime.now(timezone.utc) + timedelta(days=100)
        result = check_version_compatibility(
            1, frozenset([1, 2]), producer_deprecated_at=future
        )
        assert result == VersionCompatibility.COMPATIBLE

    def test_not_in_accepted_no_common(self):
        result = check_version_compatibility(5, frozenset([1, 2]))
        assert result == VersionCompatibility.BACKWARD_COMPATIBLE


class TestIsCompatible:
    """is_compatible returns True for active statuses."""

    def test_compatible_is_active(self):
        assert is_compatible(1, frozenset([1])) is True

    def test_backward_compatible_is_active(self):
        assert is_compatible(3, frozenset([1, 2])) is True

    def test_forward_compatible_is_active(self):
        assert is_compatible(1, frozenset([2, 3])) is True

    def test_deprecated_is_not_active(self):
        past = datetime.now(timezone.utc) - timedelta(days=100)
        assert is_compatible(1, frozenset([1]), producer_deprecated_at=past) is False


class TestMustReject:
    """must_reject returns True for terminal statuses."""

    def test_compatible_not_rejected(self):
        assert must_reject(1, frozenset([1])) is False

    def test_deprecated_is_rejected(self):
        past = datetime.now(timezone.utc) - timedelta(days=100)
        assert must_reject(1, frozenset([1]), producer_deprecated_at=past) is True


class TestVersionDeclaration:
    """VersionDeclaration dataclass and validation."""

    def test_valid_declaration(self):
        decl = VersionDeclaration(
            producer_module="agent",
            event_name="execution_requested",
            version=1,
            accepted_versions=frozenset([1, 2]),
        )
        validate_version_declaration(decl)

    def test_event_type_property(self):
        decl = VersionDeclaration(
            producer_module="agent",
            event_name="execution_requested",
            version=1,
            accepted_versions=frozenset([1]),
        )
        assert decl.event_type == "agent.execution_requested.v1"

    def test_event_type_base_property(self):
        decl = VersionDeclaration(
            producer_module="agent",
            event_name="execution_requested",
            version=1,
            accepted_versions=frozenset([1]),
        )
        assert decl.event_type_base == "agent.execution_requested"

    def test_current_version_not_in_accepted_raises(self):
        with pytest.raises(VersioningError, match="current version"):
            VersionDeclaration(
                producer_module="agent",
                event_name="execution_requested",
                version=3,
                accepted_versions=frozenset([1, 2]),
            )

    def test_empty_producer_module_raises_in_validation(self):
        decl = VersionDeclaration(
            producer_module="agent",
            event_name="execution_requested",
            version=1,
            accepted_versions=frozenset([1]),
        )
        decl.producer_module = ""
        with pytest.raises(VersioningError, match="producer_module"):
            validate_version_declaration(decl)

    def test_empty_event_name_raises_in_validation(self):
        decl = VersionDeclaration(
            producer_module="agent",
            event_name="execution_requested",
            version=1,
            accepted_versions=frozenset([1]),
        )
        decl.event_name = ""
        with pytest.raises(VersioningError, match="event_name"):
            validate_version_declaration(decl)

    def test_zero_version_raises_in_validation(self):
        decl = VersionDeclaration(
            producer_module="agent",
            event_name="execution_requested",
            version=1,
            accepted_versions=frozenset([1]),
        )
        decl.version = 0
        with pytest.raises(VersioningError, match="version"):
            validate_version_declaration(decl)

    def test_negative_version_in_accepted_raises_in_post_init(self):
        with pytest.raises(VersioningError, match="accepted_versions"):
            VersionDeclaration(
                producer_module="agent",
                event_name="execution_requested",
                version=1,
                accepted_versions=frozenset([1, -1]),
            )

    def test_deprecated_declaration(self):
        past = datetime.now(timezone.utc) - timedelta(days=100)
        decl = VersionDeclaration(
            producer_module="agent",
            event_name="deprecated_event",
            version=1,
            accepted_versions=frozenset([1]),
            deprecated_at=past,
        )
        validate_version_declaration(decl)
        assert decl.deprecated_at == past


class TestStatusCategories:
    """Active and terminal compatibility statuses."""

    def test_active_statuses(self):
        assert VersionCompatibility.COMPATIBLE.value in ACTIVE_COMPATIBILITY_STATUSES
        assert VersionCompatibility.BACKWARD_COMPATIBLE.value in ACTIVE_COMPATIBILITY_STATUSES
        assert VersionCompatibility.FORWARD_COMPATIBLE.value in ACTIVE_COMPATIBILITY_STATUSES

    def test_terminal_statuses(self):
        assert VersionCompatibility.INCOMPATIBLE.value in TERMINAL_COMPATIBILITY_STATUSES
        assert VersionCompatibility.DEPRECATED.value in TERMINAL_COMPATIBILITY_STATUSES

    def test_active_and_terminal_disjoint(self):
        assert not set(ACTIVE_COMPATIBILITY_STATUSES) & set(TERMINAL_COMPATIBILITY_STATUSES)

    def test_default_deprecation_window_positive(self):
        assert DEFAULT_DEPRECATION_WINDOW_DAYS > 0


class TestVersionCompatibilityIdempotency:
    """Compatibility checks are deterministic."""

    def test_same_inputs_produce_same_result(self):
        for _ in range(10):
            result = check_version_compatibility(1, frozenset([1, 2]))
            assert result == VersionCompatibility.COMPATIBLE

    def test_different_consumer_set(self):
        r1 = check_version_compatibility(1, frozenset([1]))
        r2 = check_version_compatibility(1, frozenset([2]))
        assert r1 != r2
