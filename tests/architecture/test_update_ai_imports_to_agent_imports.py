import ast
import warnings
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parents[2] / "src" / "modules" / "agent"

FORBIDDEN_IMPORT_PREFIXES = [
    "modules.ai",
    "modules.runtime",
    "modules.knowledge",
]


class TestUpdateAiImportsToAgentImports:
    def test_update_ai_imports_to_agent_imports_success(self):
        db_dir = AGENT_DIR / "infra" / "database"
        assert (db_dir / "models.py").exists()
        assert (db_dir / "repositories.py").exists()
        assert (db_dir / "mappers.py").exists()

        models_content = (db_dir / "models.py").read_text(encoding="utf-8")
        assert "class AgentModel" in models_content
        assert "class ProviderCredentialModel" in models_content

        repos_content = (db_dir / "repositories.py").read_text(encoding="utf-8")
        assert "class SQLAlchemyAgentRepository" in repos_content

        mappers_content = (db_dir / "mappers.py").read_text(encoding="utf-8")
        assert "def agent_entity_to_model" in mappers_content

    def test_update_ai_imports_to_agent_imports_rejects_forbidden_dependency(self):
        for py_file in AGENT_DIR.rglob("*.py"):
            source = py_file.read_text(encoding="utf-8")
            try:
                tree = ast.parse(source, filename=str(py_file))
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    for prefix in FORBIDDEN_IMPORT_PREFIXES:
                        assert not node.module.startswith(prefix), (
                            f"Forbidden import '{node.module}' in "
                            f"{py_file.relative_to(AGENT_DIR.parent.parent.parent)}. "
                            f"Agent module must not import from legacy modules."
                        )
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        for prefix in FORBIDDEN_IMPORT_PREFIXES:
                            assert not alias.name.startswith(prefix), (
                                f"Forbidden import '{alias.name}' in "
                                f"{py_file.relative_to(AGENT_DIR.parent.parent.parent)}. "
                                f"Agent module must not import from legacy modules."
                            )

    def test_update_ai_imports_to_agent_imports_keeps_legacy_compatibility(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            from modules.ai.infra import models as ai_models
            from modules.ai.infra import repositories as ai_repos
            from modules.ai.infra import mappers as ai_mappers

        deprecation_messages = [str(warning.message) for warning in w
                                if issubclass(warning.category, DeprecationWarning)]

        assert len(deprecation_messages) >= 1, (
            f"Expected at least 1 deprecation warning from ai.infra shims, "
            f"got {len(deprecation_messages)}: {deprecation_messages}"
        )

        assert hasattr(ai_models, "AgentModel"), (
            "Legacy shim ai.infra.models must export AgentModel"
        )
        assert hasattr(ai_repos, "SQLAlchemyAgentRepository"), (
            "Legacy shim ai.infra.repositories must export SQLAlchemyAgentRepository"
        )
        assert hasattr(ai_mappers, "agent_entity_to_model"), (
            "Legacy shim ai.infra.mappers must export agent_entity_to_model"
        )
