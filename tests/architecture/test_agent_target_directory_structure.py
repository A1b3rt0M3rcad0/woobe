from pathlib import Path

SPECS_DIR = Path(__file__).resolve().parents[2] / "specs"
STRUCTURE_FILE = SPECS_DIR / "002-agent-target-directory-structure.md"


class TestAgentTargetDirectoryStructure:
    def test_agent_target_directory_structure_success(self):
        assert STRUCTURE_FILE.exists(), f"Spec file not found: {STRUCTURE_FILE}"

        content = STRUCTURE_FILE.read_text(encoding="utf-8")

        assert "src/modules/agent/" in content, (
            "Spec must define target path src/modules/agent/"
        )

        required_layers = ["application", "domain", "infra", "presentation"]
        for layer in required_layers:
            assert layer in content, (
                f"Spec must define layer: {layer}"
            )

        required_infra_sublayers = ["database", "llm", "messaging", "workers"]
        for sublayer in required_infra_sublayers:
            assert sublayer in content, (
                f"Spec must define infra sublayer: {sublayer}"
            )

        assert "entities" in content, "Spec must reference domain entities"
        assert "repositories" in content, "Spec must reference repositories"
        assert "unit_of_work" in content, "Spec must reference unit_of_work"

        assert "expand-migrate-contract" in content, (
            "Spec must reference expand-migrate-contract for schema migration"
        )

        assert "agent" in content.lower(), (
            "Spec must define agent as the target bounded context"
        )

    def test_agent_target_directory_structure_rejects_forbidden_dependency(self):
        content = STRUCTURE_FILE.read_text(encoding="utf-8")

        assert "ai" in content and "knowledge" in content and "runtime" in content, (
            "Spec must reference all three legacy modules"
        )

        legacy_not_final_indicators = [
            "não existem no estado final",
            "não devem permanecer",
            "substituir",
        ]

        found = any(
            indicator.lower() in content.lower()
            for indicator in legacy_not_final_indicators
        )
        assert found, (
            "Spec must declare that ai, knowledge, runtime do not exist in the final state"
        )

        assert "outbox" in content.lower(), (
            "Spec must reference Outbox for cross-module communication"
        )

        assert "shim" in content.lower() or "shims" in content.lower(), (
            "Spec must reference shims for backward compatibility during migration"
        )
