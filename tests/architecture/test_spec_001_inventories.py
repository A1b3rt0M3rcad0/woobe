from pathlib import Path

INVENTORY_DIR = (
    Path(__file__).resolve().parents[2]
    / "specs"
    / "agent-schema-consolidation"
    / "execution"
    / "inventory"
)

REQUIRED_INVENTORIES = [
    "current-database.md",
    "objects.md",
    "foreign-keys.md",
    "migration-history.md",
    "messaging-state.md",
]

PLACEHOLDER_MARKERS = [
    "Preencher na spec",
    "Preencher nas specs",
]


class TestSpec001Inventories:
    def test_all_required_inventory_files_exist(self):
        missing = []
        for name in REQUIRED_INVENTORIES:
            path = INVENTORY_DIR / name
            if not path.is_file():
                missing.append(name)
        assert not missing, f"Missing inventory files: {missing}"

    def test_no_inventory_file_is_placeholder_only(self):
        for name in REQUIRED_INVENTORIES:
            path = INVENTORY_DIR / name
            content = path.read_text(encoding="utf-8")
            for marker in PLACEHOLDER_MARKERS:
                assert marker not in content, (
                    f"{name} still contains placeholder marker: '{marker}'"
                )

    def test_objects_inventories_all_agent_tables(self):
        path = INVENTORY_DIR / "objects.md"
        content = path.read_text(encoding="utf-8")
        expected_tables = [
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
            "agent_outbox_events",
            "agent_inbox_events",
        ]
        for table in expected_tables:
            assert table in content, f"objects.md must mention table '{table}'"

    def test_foreign_keys_inventories_both_classes(self):
        path = INVENTORY_DIR / "foreign-keys.md"
        content = path.read_text(encoding="utf-8")
        assert "intra-agent" in content.lower(), (
            "foreign-keys.md must classify intra-agent FKs"
        )
        assert "cross-module" in content.lower(), (
            "foreign-keys.md must classify cross-module FKs"
        )

    def test_migration_history_lists_all_revisions(self):
        path = INVENTORY_DIR / "migration-history.md"
        content = path.read_text(encoding="utf-8")
        for rev in ["0001", "0002", "0013", "0014"]:
            assert rev in content, (
                f"migration-history.md must list revision {rev}"
            )
        assert "0014" in content, "migration-history.md must identify head revision"

    def test_messaging_state_lists_all_legacy_tables(self):
        path = INVENTORY_DIR / "messaging-state.md"
        content = path.read_text(encoding="utf-8")
        assert "ai.outbox_events" in content or r"ai\.outbox_events" in content, (
            "messaging-state.md must mention ai.outbox_events"
        )
        assert "knowledge.outbox_events" in content, (
            "messaging-state.md must mention knowledge.outbox_events"
        )
        assert "runtime.outbox_events" in content, (
            "messaging-state.md must mention runtime.outbox_events"
        )
