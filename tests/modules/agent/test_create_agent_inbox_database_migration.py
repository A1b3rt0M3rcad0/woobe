"""Tests for spec 076 — create agent inbox database migration."""
import importlib.util
import inspect
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
MIGRATION_PATH = (
    PROJECT_ROOT
    / "packages"
    / "woobe-core"
    / "migrations"
    / "versions"
    / "0014_create_agent_inbox_events.py"
)


def _migration():
    spec = importlib.util.spec_from_file_location(
        "woobe_agent_migration_0014", MIGRATION_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestMigrationFileStructure:
    """Verify migration file has correct structure."""

    def test_migration_file_exists(self):
        assert MIGRATION_PATH.is_file()

    def test_migration_has_correct_revision(self):
        mod = _migration()
        assert mod.revision == "0014"
        assert mod.down_revision == "0013"

    def test_migration_has_upgrade_and_downgrade(self):
        mod = _migration()
        assert hasattr(mod, "upgrade")
        assert hasattr(mod, "downgrade")
        assert callable(mod.upgrade)
        assert callable(mod.downgrade)


class TestMigrationUpgradeContent:
    """Verify upgrade creates the correct schema and table."""

    def _get_source(self):
        mod = _migration()
        return inspect.getsource(mod.upgrade)

    def test_creates_agent_schema(self):
        source = self._get_source()
        assert "CREATE SCHEMA IF NOT EXISTS agent" in source

    def test_creates_agent_inbox_events_table(self):
        source = self._get_source()
        assert "agent_inbox_events" in source
        assert 'schema="agent"' in source

    def test_has_deterministic_constraint_names(self):
        source = self._get_source()
        assert "uq_agent_inbox_message_id" in source
        assert "uq_agent_inbox_idempotency_key" in source
        assert "ix_agent_inbox_pending" in source
        assert "ix_agent_inbox_correlation_id" in source

    def test_does_not_drop_legacy_schemas(self):
        source = self._get_source()
        assert "DROP SCHEMA" not in source
        assert "drop_table" not in source

    def test_has_table_comment(self):
        source = self._get_source()
        assert "comment=" in source
        assert "agent" in source

    def test_partial_index_for_received(self):
        source = self._get_source()
        assert "received" in source
        assert "retryable" in source


class TestMigrationDowngradeContent:
    """Verify downgrade only removes objects created in this spec."""

    def _get_source(self):
        mod = _migration()
        return inspect.getsource(mod.downgrade)

    def test_drops_agent_inbox_events_table(self):
        source = self._get_source()
        assert "agent_inbox_events" in source
        assert "drop_table" in source

    def test_drops_indices(self):
        source = self._get_source()
        assert "ix_agent_inbox_correlation_id" in source
        assert "ix_agent_inbox_pending" in source

    def test_does_not_drop_legacy_schemas(self):
        source = self._get_source()
        assert "DROP SCHEMA" not in source.upper() or "agent" not in source
        for schema in ("ai", "knowledge", "runtime"):
            assert "DROP SCHEMA" not in source or schema not in source


class TestIdempotencyConstraint:
    """Verify the inbox model unique constraints."""

    def test_model_has_unique_message_id(self):
        from sqlalchemy import UniqueConstraint as UC
        from modules.agent.infra.database.models import AgentInboxEventModel
        table = AgentInboxEventModel.__table__
        uq = [
            c for c in table.constraints
            if isinstance(c, UC) and "message_id" in {col.name for col in c.columns}
        ]
        assert len(uq) == 1
        assert uq[0].name == "uq_agent_inbox_message_id"

    def test_model_has_unique_idempotency_key(self):
        from sqlalchemy import UniqueConstraint as UC
        from modules.agent.infra.database.models import AgentInboxEventModel
        table = AgentInboxEventModel.__table__
        uq = [
            c for c in table.constraints
            if isinstance(c, UC) and "idempotency_key" in {col.name for col in c.columns}
        ]
        assert len(uq) == 1
        assert uq[0].name == "uq_agent_inbox_idempotency_key"


class TestConcurrencyIndex:
    """Verify partial index for received/retryable enables concurrent claim."""

    def test_pending_index_exists_in_model(self):
        from modules.agent.infra.database.models import AgentInboxEventModel
        table = AgentInboxEventModel.__table__
        index_names = {idx.name for idx in table.indexes}
        assert "ix_agent_inbox_pending" in index_names
