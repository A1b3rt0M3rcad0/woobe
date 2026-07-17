"""Tests for migration 0050: multiple Networks per Project."""

import importlib


def _migration():
    return importlib.import_module(
        "migrations.versions.0050_multiple_networks_per_project"
    )


def test_migration_revision_chain_is_linear() -> None:
    migration = _migration()
    assert migration.revision == "0050"
    assert migration.down_revision == "0049"
    assert migration.branch_labels is None


def test_network_model_allows_multiple_rows_per_project() -> None:
    from modules.network.infra.database.models import NetworkModel

    constraints = {constraint.name for constraint in NetworkModel.__table__.constraints}
    indexes = {index.name for index in NetworkModel.__table__.indexes}

    assert "uq_networks_project_id" not in constraints
    assert "ck_networks_name_not_blank" in constraints
    assert "ix_networks_project_updated" in indexes
    assert "uq_networks_project_normalized_name" in indexes


def test_runtime_key_metadata_matches_polymorphic_target_constraints() -> None:
    from modules.core.infra.database.models import ApiKeyModel

    columns = ApiKeyModel.__table__.columns
    constraints = {
        constraint.name for constraint in ApiKeyModel.__table__.constraints
    }
    indexes = {index.name for index in ApiKeyModel.__table__.indexes}

    assert "target_type" in columns
    assert "target_id" in columns
    assert "ck_core_api_keys_runtime_binding" in constraints
    assert "ck_core_api_keys_runtime_target" in constraints
    assert "ck_core_api_keys_runtime_interfaces" in constraints
    assert "ix_core_api_keys_runtime_target_binding" in indexes


def test_operational_models_expose_network_dimensions() -> None:
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
