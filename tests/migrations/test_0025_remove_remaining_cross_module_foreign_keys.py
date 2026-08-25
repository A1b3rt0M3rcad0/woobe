"""Tests for migration 0025: remove remaining cross-module FKs.

Covers historical migration structure and the Community model metadata that remains
in the public distribution.
"""
import importlib

MIGRATION_ID = "0025"


def _get_migration():
    module_path = f"migrations.versions.{MIGRATION_ID}_remove_remaining_cross_module_foreign_keys"
    return importlib.import_module(module_path)


class TestMigrationStructure:
    def test_migration_revision_correct(self):
        migration = _get_migration()
        assert migration.revision == MIGRATION_ID
        assert migration.down_revision == "0024"

    def test_cross_module_fk_list_has_9_entries(self):
        migration = _get_migration()
        assert len(migration.CROSS_MODULE_FKS) == 9

    def test_all_fk_names_are_plausible(self):
        migration = _get_migration()
        for schema, table, column, fk_name in migration.CROSS_MODULE_FKS:
            assert fk_name.endswith("_fkey")
            assert schema
            assert table
            assert column


class TestMetadataScan:
    """No cross-module ForeignKey must remain in Community model definitions."""

    def test_core_no_cross_module_fk(self):
        from modules.core.infra.database.models import ProjectModel, ApiKeyModel
        assert "ForeignKey" not in str(ProjectModel.__table__.columns["workspace_id"].foreign_keys)
        assert "ForeignKey" not in str(ApiKeyModel.__table__.columns["created_by_user_id"].foreign_keys)

    def test_metering_no_cross_module_fk(self):
        from modules.metering.infra.database.models import UsageEventModel, UsageDailyProjectModel, UsageDailyAgentModel
        assert len(UsageEventModel.__table__.foreign_keys) == 0
        assert len(UsageDailyProjectModel.__table__.foreign_keys) == 0
        assert len(UsageDailyAgentModel.__table__.foreign_keys) == 0

    def test_observability_no_cross_module_fk(self):
        from modules.observability.infra.database.models import TraceModel, TraceEventModel
        assert len(TraceModel.__table__.foreign_keys) == 0
        assert len(TraceEventModel.__table__.foreign_keys) == 1  # trace_id is internal

    def test_internal_fks_preserved(self):
        from modules.core.infra.database.models import ApiKeyModel
        from modules.observability.infra.database.models import TraceEventModel
        assert len(ApiKeyModel.__table__.foreign_keys) == 1  # project_id -> core.projects
        internal_fk = list(TraceEventModel.__table__.foreign_keys)[0]
        assert "observability.traces" in str(internal_fk)
