import re
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations" / "versions"
MIGRATION_FILE = MIGRATIONS_DIR / "0021_move_tools_tables_to_agent.py"


class TestMigration0021Structure:

    def test_migration_file_exists(self):
        assert MIGRATION_FILE.is_file(), f"Migration file not found: {MIGRATION_FILE}"

    def test_revision_is_0021(self):
        text = MIGRATION_FILE.read_text(encoding="utf-8")
        assert 'revision = "0021"' in text

    def test_down_revision_is_0020(self):
        text = MIGRATION_FILE.read_text(encoding="utf-8")
        assert 'down_revision = "0020"' in text

    def test_upgrade_function_exists(self):
        text = MIGRATION_FILE.read_text(encoding="utf-8")
        assert "def upgrade()" in text

    def test_downgrade_function_exists(self):
        text = MIGRATION_FILE.read_text(encoding="utf-8")
        assert "def downgrade()" in text

    def test_tools_tables_moved_to_agent(self):
        text = MIGRATION_FILE.read_text(encoding="utf-8")
        assert 'ALTER TABLE tools.tools SET SCHEMA agent' in text
        assert 'ALTER TABLE tools.secrets SET SCHEMA agent' in text

    def test_secrets_renamed_to_tool_secrets(self):
        text = MIGRATION_FILE.read_text(encoding="utf-8")
        assert "RENAME TO tool_secrets" in text

    def test_cross_module_fks_removed(self):
        text = MIGRATION_FILE.read_text(encoding="utf-8")
        assert 'DROP CONSTRAINT IF EXISTS tools_tools_project_id_fkey' in text
        assert 'DROP CONSTRAINT IF EXISTS tools_secrets_project_id_fkey' in text

    def test_compat_views_created(self):
        text = MIGRATION_FILE.read_text(encoding="utf-8")
        assert "CREATE OR REPLACE VIEW tools.tools AS SELECT * FROM agent.tools" in text
        assert "CREATE OR REPLACE VIEW tools.secrets AS SELECT * FROM agent.tool_secrets" in text

    def test_indexes_recreated(self):
        text = MIGRATION_FILE.read_text(encoding="utf-8")
        assert "ix_agent_tools_project_id" in text
        assert "ix_agent_tools_agent_id" in text
        assert "ix_agent_tool_secrets_project_id" in text

    def test_agent_fk_created_conditionally(self):
        text = MIGRATION_FILE.read_text(encoding="utf-8")
        assert "fk_agent_tools_agent_id" in text
        assert "agent.agents(id)" in text

    def test_downgrade_restores_views(self):
        text = MIGRATION_FILE.read_text(encoding="utf-8")
        assert "DROP VIEW IF EXISTS tools.tools" in text
        assert "DROP VIEW IF EXISTS tools.secrets" in text

    def test_downgrade_restores_schema(self):
        text = MIGRATION_FILE.read_text(encoding="utf-8")
        assert "ALTER TABLE agent.secrets SET SCHEMA tools" in text
        assert "ALTER TABLE agent.tools SET SCHEMA tools" in text

    def test_downgrade_restores_old_indexes(self):
        text = MIGRATION_FILE.read_text(encoding="utf-8")
        assert "ix_tools_tools_project_id" in text
        assert "ix_tools_tools_agent_id" in text


class TestMigrationChain:

    def test_chain_is_linear(self):
        migration_files = sorted(MIGRATIONS_DIR.glob("[0-9]*.py"))
        previous_revision = None
        for migration_file in migration_files:
            text = migration_file.read_text(encoding="utf-8")
            revision_match = re.search(r'revision = "([^"]+)"', text)
            down_revision_match = re.search(r'down_revision = "([^"]+)"', text)
            if revision_match is None:
                continue
            revision = revision_match.group(1)
            if previous_revision is not None:
                assert down_revision_match is not None, f"Missing down_revision in {migration_file.name}"
                assert down_revision_match.group(1) == previous_revision, (
                    f"Expected {migration_file.name} to follow {previous_revision}, "
                    f"got {down_revision_match.group(1)}"
                )
            previous_revision = revision

    def test_0021_follows_0020(self):
        text = MIGRATION_FILE.read_text(encoding="utf-8")
        assert 'down_revision = "0020"' in text
