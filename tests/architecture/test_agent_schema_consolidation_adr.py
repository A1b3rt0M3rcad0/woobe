from pathlib import Path

SUITE_ROOT = Path(__file__).resolve().parents[2] / "specs" / "agent-schema-consolidation"
ADR_FILE = SUITE_ROOT / "000-architecture-decision-agent-schema-as-single-owner.md"


class TestAgentSchemaConsolidationAdr:
    def test_adr_exists(self):
        assert ADR_FILE.exists(), f"ADR file not found: {ADR_FILE}"

    def test_adr_declares_agent_as_single_schema(self):
        content = ADR_FILE.read_text(encoding="utf-8")
        assert "agent" in content, "ADR must reference 'agent' schema"
        assert "único schema" in content or "single owner" in content.lower(), (
            "ADR must declare agent as the single schema"
        )

    def test_adr_references_legacy_schemas(self):
        content = ADR_FILE.read_text(encoding="utf-8")
        assert "ai" in content, "ADR must reference legacy 'ai' schema"
        assert "knowledge" in content, "ADR must reference legacy 'knowledge' schema"
        assert "runtime" in content, "ADR must reference legacy 'runtime' schema"

    def test_adr_prohibits_cross_module_foreign_keys(self):
        content = ADR_FILE.read_text(encoding="utf-8")
        assert "FK" in content or "Foreign Key" in content or "foreign key" in content, (
            "ADR must address Foreign Key policy"
        )
        assert "proib" in content or "prohibit" in content.lower() or "não" in content, (
            "ADR must prohibit certain Foreign Keys"
        )

    def test_adr_defines_fk_policy(self):
        content = ADR_FILE.read_text(encoding="utf-8")
        assert "intra-agent" in content or "intra agent" in content or "interna" in content, (
            "ADR must define intra-agent FK policy"
        )
        assert "cross-module" in content or "cross module" in content or "entre módulos" in content, (
            "ADR must define cross-module FK policy"
        )

    def test_adr_adopts_expand_migrate_contract(self):
        content = ADR_FILE.read_text(encoding="utf-8")
        assert "expand" in content.lower() and "migrate" in content.lower(), (
            "ADR must reference expand-migrate-contract strategy"
        )

    def test_adr_addresses_legacy_schema_freeze(self):
        content = ADR_FILE.read_text(encoding="utf-8")
        assert "congelar" in content or "freeze" in content.lower() or "legado" in content, (
            "ADR must address legacy schema freeze or deprecation"
        )
