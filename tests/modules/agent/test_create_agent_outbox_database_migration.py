"""Tests for spec 075 — create agent outbox database migration."""
import importlib
import inspect


class TestMigrationFileStructure:
    """Verify migration file has correct structure."""

    def test_migration_file_exists(self):
        import os
        path = os.path.join("migrations", "versions", "0013_create_agent_outbox_events.py")
        assert os.path.isfile(path)

    def test_migration_has_correct_revision(self):
        mod = importlib.import_module("migrations.versions.0013_create_agent_outbox_events")
        assert mod.revision == "0013"
        assert mod.down_revision == "0012"

    def test_migration_has_upgrade_and_downgrade(self):
        mod = importlib.import_module("migrations.versions.0013_create_agent_outbox_events")
        assert hasattr(mod, "upgrade")
        assert hasattr(mod, "downgrade")
        assert callable(mod.upgrade)
        assert callable(mod.downgrade)


class TestMigrationUpgradeContent:
    """Verify upgrade creates the correct schema and table."""

    def _get_source(self):
        mod = importlib.import_module("migrations.versions.0013_create_agent_outbox_events")
        return inspect.getsource(mod.upgrade)

    def test_creates_agent_schema(self):
        source = self._get_source()
        assert "CREATE SCHEMA IF NOT EXISTS agent" in source

    def test_creates_agent_outbox_events_table(self):
        source = self._get_source()
        assert "agent_outbox_events" in source
        assert 'schema="agent"' in source

    def test_has_deterministic_constraint_names(self):
        source = self._get_source()
        assert "uq_agent_outbox_idempotency_key" in source
        assert "ix_agent_outbox_pending" in source
        assert "ix_agent_outbox_correlation_id" in source
        assert "ix_agent_outbox_aggregate" in source

    def test_does_not_drop_legacy_schemas(self):
        source = self._get_source()
        assert "DROP SCHEMA" not in source
        assert "drop_table" not in source

    def test_has_table_comment(self):
        source = self._get_source()
        assert "comment=" in source
        assert "agent" in source

    def test_partial_index_for_pending(self):
        source = self._get_source()
        assert "pending" in source
        assert "retryable" in source


class TestMigrationDowngradeContent:
    """Verify downgrade only removes objects created in this spec."""

    def _get_source(self):
        mod = importlib.import_module("migrations.versions.0013_create_agent_outbox_events")
        return inspect.getsource(mod.downgrade)

    def test_drops_agent_outbox_events_table(self):
        source = self._get_source()
        assert "agent_outbox_events" in source
        assert "drop_table" in source

    def test_drops_indices(self):
        source = self._get_source()
        assert "ix_agent_outbox_aggregate" in source
        assert "ix_agent_outbox_correlation_id" in source
        assert "ix_agent_outbox_pending" in source

    def test_does_not_drop_legacy_schemas(self):
        source = self._get_source()
        assert "DROP SCHEMA" not in source.upper() or "agent" not in source
        for schema in ("ai", "knowledge", "runtime"):
            assert "DROP SCHEMA" not in source or schema not in source


class TestIdempotencyConstraint:
    """Verify the outbox model unique constraint on idempotency_key."""

    def test_model_has_unique_idempotency_key(self):
        from sqlalchemy import UniqueConstraint as UC
        from modules.agent.infra.database.models import AgentOutboxEventModel
        table = AgentOutboxEventModel.__table__
        uq = [
            c for c in table.constraints
            if isinstance(c, UC) and "idempotency_key" in {col.name for col in c.columns}
        ]
        assert len(uq) == 1
        assert uq[0].name == "uq_agent_outbox_idempotency_key"


class TestConcurrencyIndex:
    """Verify partial index for pending/retryable enables concurrent claim."""

    def test_pending_index_exists_in_model(self):
        from modules.agent.infra.database.models import AgentOutboxEventModel
        table = AgentOutboxEventModel.__table__
        index_names = {idx.name for idx in table.indexes}
        assert "ix_agent_outbox_pending" in index_names
