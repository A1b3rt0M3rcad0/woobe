from datetime import datetime, timezone

import pytest

from modules.agent.domain.release_versioning import (
    ReleaseChangeKind,
    calculate_next_release_version,
    parse_release_version,
)


def test_parse_release_version_contract() -> None:
    version = parse_release_version("v0.1.20260620.07")

    assert version.compatibility == 0
    assert version.feature == 1
    assert version.release_date.isoformat() == "2026-06-20"
    assert version.sequence == 7
    assert str(version) == "v0.1.20260620.07"


def test_first_release_starts_at_first_daily_sequence() -> None:
    assert calculate_next_release_version(
        [],
        ReleaseChangeKind.CHANGE,
        now=datetime(2026, 6, 20, tzinfo=timezone.utc),
    ) == "v0.0.20260620.01"


def test_regular_change_increments_daily_sequence_only() -> None:
    assert calculate_next_release_version(
        ["v0.0.20260620.00"],
        ReleaseChangeKind.CHANGE,
        now=datetime(2026, 6, 20, tzinfo=timezone.utc),
    ) == "v0.0.20260620.01"


def test_feature_change_increments_feature_bucket_and_keeps_daily_sequence() -> None:
    assert calculate_next_release_version(
        ["v0.0.20260620.02"],
        ReleaseChangeKind.FEATURE,
        now=datetime(2026, 6, 20, tzinfo=timezone.utc),
    ) == "v0.1.20260620.03"


def test_compatibility_change_increments_compatibility_and_keeps_daily_sequence() -> None:
    assert calculate_next_release_version(
        ["v0.3.20260620.02"],
        ReleaseChangeKind.COMPATIBILITY,
        now=datetime(2026, 6, 20, tzinfo=timezone.utc),
    ) == "v1.0.20260620.03"


def test_daily_sequence_is_scoped_by_date() -> None:
    assert calculate_next_release_version(
        ["v0.0.20260619.09"],
        ReleaseChangeKind.CHANGE,
        now=datetime(2026, 6, 20, tzinfo=timezone.utc),
    ) == "v0.0.20260620.01"


def test_invalid_existing_versions_do_not_block_generation() -> None:
    assert calculate_next_release_version(
        ["release-1", "v0.0.20260620.00"],
        ReleaseChangeKind.CHANGE,
        now=datetime(2026, 6, 20, tzinfo=timezone.utc),
    ) == "v0.0.20260620.01"


def test_invalid_new_change_kind_is_rejected() -> None:
    with pytest.raises(ValueError):
        calculate_next_release_version(
            ["v0.0.20260620.00"],
            "unknown",
            now=datetime(2026, 6, 20, tzinfo=timezone.utc),
        )
