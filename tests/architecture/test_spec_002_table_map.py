from pathlib import Path

INVENTORY_DIR = (
    Path(__file__).resolve().parents[2]
    / "specs"
    / "agent-schema-consolidation"
    / "execution"
    / "inventory"
)
TABLE_MAP_FILE = INVENTORY_DIR / "table-map.md"


class TestSpec002TableMap:
    def test_table_map_exists(self):
        assert TABLE_MAP_FILE.is_file(), f"table-map.md not found: {TABLE_MAP_FILE}"

    def test_table_map_maps_all_business_tables(self):
        content = TABLE_MAP_FILE.read_text(encoding="utf-8")
        expected = [
            "provider_credentials",
            "agents",
            "agent_prompts",
            "agent_contracts",
            "agent_model_configs",
            "agent_releases",
            "agent_release_tests",
            "document_collections",
            "agent_collections",
            "documents",
            "document_chunks",
            "knowledge_versions",
            "sessions",
            "messages",
            "ask_jobs",
        ]
        for table in expected:
            assert f"agent.{table}" in content, (
                f"table-map.md must map agent.{table}"
            )

    def test_table_map_addresses_messaging_collisions(self):
        content = TABLE_MAP_FILE.read_text(encoding="utf-8")
        assert "require" in content.lower() or "rename" in content.lower() or "conflito" in content, (
            "table-map.md must address legacy messaging table naming conflicts"
        )

    def test_table_map_lists_cross_module_fks(self):
        content = TABLE_MAP_FILE.read_text(encoding="utf-8")
        assert "cross-module" in content.lower() or "cross module" in content.lower(), (
            "table-map.md must list cross-module FKs"
        )

    def test_table_map_lists_external_fks_to_repont(self):
        content = TABLE_MAP_FILE.read_text(encoding="utf-8")
        assert "metering" in content, "table-map.md must address metering FKs"
        assert "observability" in content, "table-map.md must address observability FKs"
        assert "tools" in content, "table-map.md must address tools FKs"

    def test_table_map_defines_index_policy(self):
        content = TABLE_MAP_FILE.read_text(encoding="utf-8")
        assert "índice" in content or "index" in content.lower(), (
            "table-map.md must define index policy for external IDs"
        )
