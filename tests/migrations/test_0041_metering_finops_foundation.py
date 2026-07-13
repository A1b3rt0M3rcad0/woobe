"""Tests for migration 0041: metering FinOps foundation."""

import importlib


def _get_migration():
    return importlib.import_module("migrations.versions.0041_metering_finops_foundation")


def test_migration_revision_chain():
    migration = _get_migration()
    assert migration.revision == "0041"
    assert migration.down_revision == "0040"


def test_usage_models_expose_finops_dimensions():
    from modules.metering.infra.database.models import (
        UsageDailyProjectModel,
        UsageEventModel,
    )

    event_columns = UsageEventModel.__table__.columns
    for column in (
        "source_event_id",
        "occurred_at",
        "trace_id",
        "call_id",
        "environment",
        "agent_release_id",
        "provider_model_id",
        "cost_status",
        "usage_complete",
        "pricing_snapshot",
    ):
        assert column in event_columns

    daily_columns = UsageDailyProjectModel.__table__.columns
    for column in (
        "successful_requests",
        "failed_requests",
        "cancelled_requests",
        "llm_calls",
        "priced_requests",
        "partial_cost_requests",
        "unpriced_requests",
    ):
        assert column in daily_columns

    assert "uq_metering_usage_events_source_event" in {
        index.name for index in UsageEventModel.__table__.indexes
    }
