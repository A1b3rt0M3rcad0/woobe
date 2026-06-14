import ast
import importlib
import sys
import warnings
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
AGENT_DIR = PROJECT_ROOT / "src" / "modules" / "agent"
ALLOWLIST_FILE = Path(__file__).resolve().parent / "legacy_import_allowlist.yaml"

FORBIDDEN_IMPORT_PREFIXES = [
    "modules.knowledge",
]


def _load_allowlist() -> set[tuple[str, str]]:
    if not ALLOWLIST_FILE.exists():
        return set()
    with open(ALLOWLIST_FILE, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    entries = data.get("entries") or []
    return {
        (e["file"].replace("/", "\\").replace("\\", "/"), e["target_module"])
        for e in entries
        if e.get("scope") == "module_boundaries"
    }


class TestUpdateKnowledgeImportsToAgentImports:
    def test_update_knowledge_imports_to_agent_imports_success(self):
        db_dir = AGENT_DIR / "infra" / "database"
        assert (db_dir / "models.py").exists()
        assert (db_dir / "repositories.py").exists()
        assert (db_dir / "mappers.py").exists()

        models_content = (db_dir / "models.py").read_text(encoding="utf-8")
        assert "class DocumentCollectionModel" in models_content
        assert "class DocumentModel" in models_content
        assert "class DocumentChunkModel" in models_content

        repos_content = (db_dir / "repositories.py").read_text(encoding="utf-8")
        assert "class SQLAlchemyDocumentCollectionRepository" in repos_content
        assert "class SQLAlchemyDocumentRepository" in repos_content

        mappers_content = (db_dir / "mappers.py").read_text(encoding="utf-8")
        assert "def model_to_document" in mappers_content

    def test_update_knowledge_imports_to_agent_imports_rejects_forbidden_dependency(self):
        allowlist = _load_allowlist()
        for py_file in AGENT_DIR.rglob("*.py"):
            source = py_file.read_text(encoding="utf-8")
            try:
                tree = ast.parse(source, filename=str(py_file))
            except SyntaxError:
                continue

            rel_path = py_file.relative_to(PROJECT_ROOT).as_posix()

            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    for prefix in FORBIDDEN_IMPORT_PREFIXES:
                        if node.module.startswith(prefix):
                            target = prefix.split(".")[-1]
                            if (rel_path, target) in allowlist:
                                continue
                            assert False, (
                                f"Forbidden import '{node.module}' in "
                                f"{py_file.relative_to(PROJECT_ROOT)}. "
                                f"Agent module must not import from knowledge module."
                            )
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        for prefix in FORBIDDEN_IMPORT_PREFIXES:
                            if alias.name.startswith(prefix):
                                target = prefix.split(".")[-1]
                                if (rel_path, target) in allowlist:
                                    continue
                                assert False, (
                                    f"Forbidden import '{alias.name}' in "
                                    f"{py_file.relative_to(PROJECT_ROOT)}. "
                                    f"Agent module must not import from knowledge module."
                                )

    def test_update_knowledge_imports_to_agent_imports_keeps_legacy_compatibility(self):
        for mod_name in list(sys.modules.keys()):
            if mod_name.startswith("modules.knowledge.infra"):
                del sys.modules[mod_name]

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            import modules.knowledge.infra.models as k_models
            importlib.reload(k_models)
            import modules.knowledge.infra.repositories as k_repos
            importlib.reload(k_repos)
            import modules.knowledge.infra.mappers as k_mappers
            importlib.reload(k_mappers)

        deprecation_messages = [str(warning.message) for warning in w
                                if issubclass(warning.category, DeprecationWarning)]

        assert len(deprecation_messages) >= 1, (
            f"Expected at least 1 deprecation warning from knowledge.infra shims, "
            f"got {len(deprecation_messages)}: {deprecation_messages}"
        )

        assert hasattr(k_models, "DocumentCollectionModel"), (
            "Legacy shim knowledge.infra.models must export DocumentCollectionModel"
        )
        assert hasattr(k_repos, "SQLAlchemyDocumentCollectionRepository"), (
            "Legacy shim knowledge.infra.repositories must export SQLAlchemyDocumentCollectionRepository"
        )
        assert hasattr(k_mappers, "model_to_document"), (
            "Legacy shim knowledge.infra.mappers must export model_to_document"
        )
