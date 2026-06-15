from __future__ import annotations

import ast
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
AGENT_DIR = PROJECT_ROOT / "src" / "modules" / "agent"

CANONICAL_STRUCTURE = {
    "application": {"composers", "dtos", "handlers", "use_cases"},
    "domain": {"entities.py", "enums.py", "errors.py", "events.py", "repositories.py", "services.py", "value_objects.py"},
    "infra": {"database", "messaging", "workers", "llm"},
    "presentation": {"controllers", "mappers.py", "routes.py", "schemas.py"},
}


def _get_py_files_recursive(dir_path: Path) -> list[Path]:
    return [p for p in dir_path.rglob("*.py") if "__pycache__" not in p.parts]


def _get_imports(file_path: Path) -> list[str]:
    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(file_path))
    except (SyntaxError, UnicodeDecodeError):
        return []
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    return imports


class TestAuditAgentAsCanonicalReference:
    def test_agent_has_canonical_directory_structure(self):
        for layer, expected_items in CANONICAL_STRUCTURE.items():
            layer_dir = AGENT_DIR / layer
            assert layer_dir.is_dir(), f"Missing canonical layer: {layer}/"
            for item in expected_items:
                item_path = layer_dir / item
                exists = item_path.is_dir() or item_path.is_file()
                assert exists, f"Missing canonical item: {layer}/{item}"

    def test_agent_has_all_canonical_domain_files(self):
        domain_dir = AGENT_DIR / "domain"
        assert domain_dir.is_dir()
        expected = {"entities.py", "enums.py", "errors.py", "events.py", "repositories.py", "services.py", "value_objects.py"}
        existing = {f.name for f in domain_dir.iterdir() if f.suffix == ".py"}
        missing = expected - existing
        assert not missing, f"Missing domain files: {missing}"

    def test_agent_exposes_routes_and_registry_in_all(self):
        init_file = AGENT_DIR / "__init__.py"
        assert init_file.exists()
        source = init_file.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(init_file))
        exports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "__all__":
                        if isinstance(node.value, ast.List):
                            exports = {e.value for e in node.value.elts if isinstance(e, ast.Constant)}
        assert "routes" in exports, "routes not in agent __all__"
        assert "registry" in exports, "registry not in agent __all__"

    def test_no_legacy_ai_knowledge_runtime_imports_in_agent(self):
        for py_file in _get_py_files_recursive(AGENT_DIR):
            imports = _get_imports(py_file)
            for imp in imports:
                if "modules.ai" in imp or "modules.knowledge" in imp or "modules.runtime" in imp:
                    rel = py_file.relative_to(PROJECT_ROOT).as_posix()
                    pytest.fail(f"Legacy import in {rel}: {imp}")

    def test_agent_unit_of_work_coordinates_only_agent_repos_and_outbox_inbox(self):
        uow_file = AGENT_DIR / "infra" / "database" / "unit_of_work.py"
        assert uow_file.exists()
        source = uow_file.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(uow_file))
        class_defs = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
        agent_uow_names = [c.name for c in class_defs if "AgentUnitOfWork" in c.name or "UoW" in c.name]
        assert len(agent_uow_names) == 1, f"Expected exactly 1 AgentUnitOfWork, found: {agent_uow_names}"
        imports = _get_imports(uow_file)
        agent_repo_imports = [i for i in imports if "modules.agent.infra.database.repositories" in i]
        assert len(agent_repo_imports) >= 1, "AgentUnitOfWork must import agent repositories"
        cross_module_repos = [i for i in imports if i.startswith("modules.") and not i.startswith("modules.agent")]
        assert len(cross_module_repos) == 0, f"AgentUnitOfWork must not import other module repos: {cross_module_repos}"

    def test_domain_layer_no_sqlalchemy_or_fastapi_dependencies(self):
        domain_dir = AGENT_DIR / "domain"
        for py_file in _get_py_files_recursive(domain_dir):
            imports = _get_imports(py_file)
            sqlalchemy_refs = [i for i in imports if "sqlalchemy" in i.lower()]
            fastapi_refs = [i for i in imports if "fastapi" in i.lower()]
            combined = sqlalchemy_refs + fastapi_refs
            if combined:
                rel = py_file.relative_to(PROJECT_ROOT).as_posix()
                pytest.fail(f"Domain file {rel} imports framework dependencies: {combined}")

    def test_postgres_unit_of_work_usage_is_in_composers_and_one_worker(self):
        composers_dir = AGENT_DIR / "application" / "composers"
        workers_dir = AGENT_DIR / "infra" / "workers"
        occurrences: list[str] = []
        for py_file in list(_get_py_files_recursive(composers_dir)) + list(_get_py_files_recursive(workers_dir)):
            source = py_file.read_text(encoding="utf-8")
            if "PostgresUnitOfWork" in source:
                rel = py_file.relative_to(PROJECT_ROOT).as_posix()
                occurrences.append(rel)
        assert len(occurrences) >= 40, f"Expected 40+ PostgresUnitOfWork occurrences, found {len(occurrences)}"
        assert any("ask_job_worker" in o for o in occurrences), "ask_job_worker must use PostgresUnitOfWork"

    def test_infra_llm_is_specific_to_agent(self):
        llm_dir = AGENT_DIR / "infra" / "llm"
        assert llm_dir.is_dir(), "infra/llm must exist in agent"
        py_files = _get_py_files_recursive(llm_dir)
        assert len(py_files) >= 2, "agent infra/llm should have at least 2 source files"
