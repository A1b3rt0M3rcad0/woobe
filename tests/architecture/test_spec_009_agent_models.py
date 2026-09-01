from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
AGENT_MODELS = (
    PROJECT_ROOT
    / "packages"
    / "woobe-core"
    / "src"
    / "modules"
    / "agent"
    / "infra"
    / "database"
    / "models.py"
)

AGENT_BUSINESS_TABLES = [
    "provider_credentials",
    "agents",
    "agent_prompts",
    "agent_contracts",
    "agent_model_configs",
    "agent_releases",
    "agent_release_tests",
]

KNOWLEDGE_BUSINESS_TABLES = [
    "document_collections",
    "agent_collections",
    "documents",
    "document_chunks",
    "knowledge_versions",
]

RUNTIME_BUSINESS_TABLES = [
    "sessions",
    "messages",
    "ask_jobs",
]

LEGACY_MESSAGING_TABLES: list[tuple[str, str, str]] = []


def _get_models_text() -> str:
    assert AGENT_MODELS.exists(), f"Models file not found: {AGENT_MODELS}"
    return AGENT_MODELS.read_text(encoding="utf-8")


class TestBusinessTablesUseAgentSchema:
    def test_all_ai_business_tables_have_agent_schema(self):
        text = _get_models_text()
        for table in AGENT_BUSINESS_TABLES:
            assert '"schema": "agent"' in text, \
                f"Table {table} should have schema='agent'"

    def test_all_knowledge_business_tables_have_agent_schema(self):
        text = _get_models_text()
        for table in KNOWLEDGE_BUSINESS_TABLES:
            assert '"schema": "agent"' in text, \
                f"Table {table} should have schema='agent'"

    def test_all_runtime_business_tables_have_agent_schema(self):
        text = _get_models_text()
        for table in RUNTIME_BUSINESS_TABLES:
            assert '"schema": "agent"' in text, \
                f"Table {table} should have schema='agent'"

    def test_no_legacy_messaging_tables(self):
        text = _get_models_text()
        assert "KnowledgeOutboxEventModel" not in text, "KnowledgeOutboxEventModel should be removed"
        assert "KnowledgeInboxEventModel" not in text, "KnowledgeInboxEventModel should be removed"
        assert "RuntimeOutboxEventModel" not in text, "RuntimeOutboxEventModel should be removed"
        assert "RuntimeInboxEventModel" not in text, "RuntimeInboxEventModel should be removed"
        assert " class OutboxEventModel" not in text, "OutboxEventModel class should be removed"
        assert " class InboxEventModel" not in text, "InboxEventModel class should be removed"


class TestIntraAgentForeignKeysUseAgentSchema:
    def test_agent_models_no_legacy_fk(self):
        text = _get_models_text()
        assert 'ForeignKey("ai.' not in text, (
            "Agent models should not contain ForeignKey to ai schema"
        )
        assert 'ForeignKey("knowledge.' not in text, (
            "Agent models should not contain ForeignKey to knowledge schema"
        )
        assert 'ForeignKey("runtime.' not in text, (
            "Agent models should not contain ForeignKey to runtime schema"
        )

    def test_agent_models_have_agent_fk(self):
        text = _get_models_text()
        assert 'ForeignKey("agent.' in text, (
            "Agent models should contain ForeignKey to agent schema"
        )


class TestAllowlistUpdated:
    def test_no_models_entries_with_removal_spec_009(self):
        allowlist_path = (
            PROJECT_ROOT
            / "tests"
            / "architecture"
            / "legacy_schema_allowlist.yaml"
        )
        content = allowlist_path.read_text(encoding="utf-8")
        assert 'removal_spec: "009"' not in content and '"removal_spec": "009"' not in content, (
            "Allowlist should have no entries with removal_spec: '009'"
        )
