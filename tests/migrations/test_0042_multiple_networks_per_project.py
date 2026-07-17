"""Tests for migration 0042: multiple Networks per Project."""

import importlib


def _migration():
    return importlib.import_module(
        "migrations.versions.0042_multiple_networks_per_project"
    )


def test_migration_revision_chain_is_linear():
    migration = _migration()
    assert migration.revision == "0042"
    assert migration.down_revision == "0041"
    assert migration.branch_labels is None


def test_network_model_allows_multiple_rows_per_project():
    from modules.network.infra.database.models import NetworkModel

    constraints = {constraint.name for constraint in NetworkModel.__table__.constraints}
    indexes = {index.name for index in NetworkModel.__table__.indexes}

    assert "uq_networks_project_id" not in constraints
    assert "ck_networks_name_not_blank" in constraints
    assert "ix_networks_project_updated" in indexes
    assert "uq_networks_project_normalized_name" in indexes


def test_runtime_keys_expose_polymorphic_target_columns():
    from modules.core.infra.database.models import ApiKeyModel

    columns = ApiKeyModel.__table__.columns
    indexes = {index.name for index in ApiKeyModel.__table__.indexes}

    assert "target_type" in columns
    assert "target_id" in columns
    assert "ix_core_api_keys_runtime_target_binding" in indexes


def test_operational_models_expose_network_dimensions():
    from modules.metering.infra.database.models import UsageEventModel
    from modules.observability.infra.database.models import TraceModel

    trace_columns = TraceModel.__table__.columns
    for name in (
        "network_id",
        "network_execution_id",
        "network_session_id",
        "network_version_id",
    ):
        assert name in trace_columns

    usage_columns = UsageEventModel.__table__.columns
    for name in ("network_id", "network_execution_id", "network_version_id"):
        assert name in usage_columns
