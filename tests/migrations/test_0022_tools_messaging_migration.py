import re
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations" / "versions"
MIGRATION_FILE = MIGRATIONS_DIR / "0022_consolidate_tools_messaging.py"


class TestMigration0022Structure:

    def test_migration_file_exists(self):
        assert MIGRATION_FILE.is_file(), f"Migration file not found: {MIGRATION_FILE}"

    def test_revision_is_0022(self):
        text = MIGRATION_FILE.read_text(encoding="utf-8")
        assert 'revision = "0022"' in text

    def test_down_revision_is_0021(self):
        text = MIGRATION_FILE.read_text(encoding="utf-8")
        assert 'down_revision = "0021"' in text

    def test_upgrade_function_exists(self):
        text = MIGRATION_FILE.read_text(encoding="utf-8")
        assert "def upgrade()" in text

    def test_downgrade_function_exists(self):
        text = MIGRATION_FILE.read_text(encoding="utf-8")
        assert "def downgrade()" in text

    def test_copies_pending_outbox_events(self):
        text = MIGRATION_FILE.read_text(encoding="utf-8")
        assert "pending" in text and "retryable" in text
        assert "outbox_events" in text

    def test_copies_pending_inbox_events(self):
        text = MIGRATION_FILE.read_text(encoding="utf-8")
        assert "inbox_events" in text
        assert "received" in text and "retryable" in text

    def test_handles_duplicate_idempotency(self):
        text = MIGRATION_FILE.read_text(encoding="utf-8")
        assert "ON CONFLICT (idempotency_key) DO NOTHING" in text

    def test_marks_migrated_events(self):
        text = MIGRATION_FILE.read_text(encoding="utf-8")
        assert "status = 'migrated'" in text

    def test_archives_old_events(self):
        text = MIGRATION_FILE.read_text(encoding="utf-8")
        assert "archived" in text

    def test_archives_with_retention_period(self):
        text = MIGRATION_FILE.read_text(encoding="utf-8")
        assert "7 days" in text

    def test_compat_views_created(self):
        text = MIGRATION_FILE.read_text(encoding="utf-8")
        assert "CREATE OR REPLACE VIEW tools.outbox_events" in text
        assert "CREATE OR REPLACE VIEW tools.inbox_events" in text

    def test_downgrade_drops_compat_views(self):
        text = MIGRATION_FILE.read_text(encoding="utf-8")
        assert "DROP VIEW IF EXISTS tools.outbox_events" in text
        assert "DROP VIEW IF EXISTS tools.inbox_events" in text

    def test_downgrade_reverses_status(self):
        text = MIGRATION_FILE.read_text(encoding="utf-8")
        assert "status = 'pending' WHERE status = 'migrated'" in text
        assert "status = 'received' WHERE status = 'migrated'" in text

    def test_maps_tool_events_to_agent(self):
        text = MIGRATION_FILE.read_text(encoding="utf-8")
        assert "replace(o.event_type, 'tools.tool.', 'agent.tool.')" in text
        assert "replace(o.event_type, 'tools.secret.', 'agent.secret.')" in text

    def test_downgrade_deletes_agent_copies(self):
        text = MIGRATION_FILE.read_text(encoding="utf-8")
        assert "DELETE FROM agent.agent_outbox_events" in text
        assert "DELETE FROM agent.agent_inbox_events" in text


class TestMigrationChain:

    def test_0022_follows_0021(self):
        text = MIGRATION_FILE.read_text(encoding="utf-8")
        assert 'down_revision = "0021"' in text

    def test_all_revisions_linear(self):
        migration_files = sorted(MIGRATIONS_DIR.glob("[0-9]*.py"))
        prev = None
        for mf in migration_files:
            text = mf.read_text(encoding="utf-8")
            rev_match = re.search(r'revision = "(\d+)"', text)
            if rev_match:
                rev = int(rev_match.group(1))
                if prev is not None:
                    assert rev == prev + 1, (
                        f"Expected revision {prev + 1:04d}, got {rev:04d}"
                    )
                prev = rev
