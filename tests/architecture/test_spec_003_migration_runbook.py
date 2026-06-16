from pathlib import Path

EXECUTION_DIR = (
    Path(__file__).resolve().parents[2]
    / "specs"
    / "agent-schema-consolidation"
    / "execution"
)
RUNBOOK_FILE = EXECUTION_DIR / "migration-runbook.md"


class TestSpec003MigrationRunbook:
    def test_runbook_exists(self):
        assert RUNBOOK_FILE.is_file(), f"migration-runbook.md not found: {RUNBOOK_FILE}"

    def test_runbook_defines_expand_phase(self):
        content = RUNBOOK_FILE.read_text(encoding="utf-8")
        assert "expand" in content.lower(), "Runbook must define expand phase"

    def test_runbook_defines_migrate_phase(self):
        content = RUNBOOK_FILE.read_text(encoding="utf-8")
        assert "migrate" in content.lower(), "Runbook must define migrate phase"

    def test_runbook_defines_contract_phase(self):
        content = RUNBOOK_FILE.read_text(encoding="utf-8")
        assert "contract" in content.lower(), "Runbook must define contract phase"

    def test_runbook_defines_rollback_protocol(self):
        content = RUNBOOK_FILE.read_text(encoding="utf-8")
        assert "rollback" in content.lower(), "Runbook must define rollback protocol"

    def test_runbook_defines_lock_policy(self):
        content = RUNBOOK_FILE.read_text(encoding="utf-8")
        assert "lock" in content.lower(), "Runbook must define lock policy"

    def test_runbook_defines_view_compatibility(self):
        content = RUNBOOK_FILE.read_text(encoding="utf-8")
        assert "view" in content.lower() or "compatibilidade" in content.lower(), (
            "Runbook must define view compatibility strategy"
        )

    def test_runbook_addresses_all_business_tables(self):
        content = RUNBOOK_FILE.read_text(encoding="utf-8")
        tables = [
            "provider_credentials",
            "agents",
            "agent_prompts",
            "document_collections",
            "documents",
            "document_chunks",
            "sessions",
            "messages",
            "ask_jobs",
        ]
        for table in tables:
            assert table in content, f"Runbook must address table '{table}'"

    def test_runbook_addresses_messaging_table_conflicts(self):
        content = RUNBOOK_FILE.read_text(encoding="utf-8")
        assert "legacy_outbox_events" in content or "legacy_inbox_events" in content, (
            "Runbook must address legacy messaging table renaming"
        )
