from pathlib import Path

SPECS_DIR = Path(__file__).resolve().parents[2] / "specs"
RULES_FILE = SPECS_DIR / "001-architecture-rules-modular-monolith-boundaries.md"


class TestArchitectureRulesModularMonolithBoundaries:
    def test_architecture_rules_modular_monolith_boundaries_success(self):
        assert RULES_FILE.exists(), f"Rules spec not found: {RULES_FILE}"

        content = RULES_FILE.read_text(encoding="utf-8")

        assert "imports permitidos" in content.lower() or "allowed" in content.lower(), (
            "Spec must define allowed imports"
        )

        assert "imports proibidos" in content.lower() or "forbidden" in content.lower(), (
            "Spec must define forbidden imports"
        )

        assert "foreignkey" in content.lower(), (
            "Spec must define Foreign Key boundary rules"
        )

        assert "worker" in content.lower(), (
            "Spec must define worker placement rules"
        )

        assert "uow" in content.lower() or "unit of work" in content.lower(), (
            "Spec must define Unit of Work scope rules"
        )

        assert "outbox" in content.lower(), (
            "Spec must reference Outbox pattern for cross-module communication"
        )

        assert "inbox" in content.lower(), (
            "Spec must reference Inbox pattern for cross-module communication"
        )

        assert "allowlist" in content.lower(), (
            "Spec must define temporary allowlist exception mechanism"
        )

        assert "ast" in content.lower() or "test_module_boundaries" in content, (
            "Spec must reference AST-based or programmatic validation mechanism"
        )

    def test_architecture_rules_modular_monolith_boundaries_rejects_forbidden_dependency(self):
        content = RULES_FILE.read_text(encoding="utf-8")

        forbidden_patterns = [
            "modules.<other>.domain",
            "modules.<other>.application",
            "modules.<other>.infra",
            "modules.<other>.presentation",
        ]

        for pattern in forbidden_patterns:
            assert pattern.lower() in content.lower(), (
                f"Spec must explicitly forbid import pattern: '{pattern}'"
            )

        forbidden_rules = [
            ("cross-module foreign key", "foreignkey"),
            ("domain in shared", "shared"),
            ("synchronous state change between modules", "síncrona"),
            ("remove legacy before deprecation", "remover"),
        ]

        for description, keyword in forbidden_rules:
            assert keyword.lower() in content.lower(), (
                f"Spec must address forbidden pattern: {description}"
            )

        assert "proibid" in content.lower() or "não" in content.lower(), (
            "Spec must contain explicit prohibition language"
        )
