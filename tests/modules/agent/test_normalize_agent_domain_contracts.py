from __future__ import annotations

import ast
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
AGENT_DOMAIN = PROJECT_ROOT / "packages" / "woobe-core" / "src" / "modules" / "agent" / "domain"

REQUIRED_DOMAIN_FILES = [
    "entities.py",
    "enums.py",
    "errors.py",
    "events.py",
    "repositories.py",
    "services.py",
    "value_objects.py",
]

FORBIDDEN_FRAMEWORK_MODULES = {"sqlalchemy", "fastapi", "asyncpg", "aiormq"}


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


class TestNormalizeAgentDomainContracts:
    def test_all_required_domain_files_exist(self):
        for name in REQUIRED_DOMAIN_FILES:
            file_path = AGENT_DOMAIN / name
            assert file_path.is_file(), f"Missing domain file: {name}"

    def test_domain_entities_is_populated(self):
        entities_file = AGENT_DOMAIN / "entities.py"
        source = entities_file.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(entities_file))
        class_count = sum(1 for n in ast.walk(tree) if isinstance(n, ast.ClassDef))
        assert class_count >= 10, f"entities.py: expected 10+ classes, found {class_count}"

    def test_domain_enums_is_populated(self):
        enums_file = AGENT_DOMAIN / "enums.py"
        source = enums_file.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(enums_file))
        class_count = sum(1 for n in ast.walk(tree) if isinstance(n, ast.ClassDef))
        assert class_count >= 10, f"enums.py: expected 10+ enum classes, found {class_count}"

    def test_domain_errors_is_populated(self):
        errors_file = AGENT_DOMAIN / "errors.py"
        assert errors_file.stat().st_size > 100, "errors.py is too small (likely empty)"

    def test_domain_events_is_populated(self):
        events_file = AGENT_DOMAIN / "events.py"
        source = events_file.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(events_file))
        class_count = sum(1 for n in ast.walk(tree) if isinstance(n, ast.ClassDef))
        assert class_count >= 1, "events.py must contain at least one event class"

    def test_domain_repositories_use_abc(self):
        repos_file = AGENT_DOMAIN / "repositories.py"
        source = repos_file.read_text(encoding="utf-8")
        assert "from abc import ABC, abstractmethod" in source, "Repositories must use ABC/abstractmethod"
        assert "class " in source, "Repository interfaces must be defined"
        assert "ABC" in source, "Repository classes must inherit from ABC"

    def test_domain_services_stub_exists(self):
        services_file = AGENT_DOMAIN / "services.py"
        assert services_file.is_file()

    def test_domain_value_objects_stub_exists(self):
        vo_file = AGENT_DOMAIN / "value_objects.py"
        assert vo_file.is_file()

    def test_no_domain_file_imports_framework_libraries(self):
        for py_file in AGENT_DOMAIN.rglob("*.py"):
            imports = _get_imports(py_file)
            framework_refs = [m for m in imports if m.lower() in FORBIDDEN_FRAMEWORK_MODULES]
            if framework_refs:
                rel = py_file.relative_to(PROJECT_ROOT).as_posix()
                pytest.fail(f"Domain file {rel} imports: {framework_refs}")

    def test_domain_does_not_import_application_or_infra(self):
        for py_file in AGENT_DOMAIN.rglob("*.py"):
            imports = _get_imports(py_file)
            cross_layer = [i for i in imports if i in ("application", "infra", "presentation")]
            if cross_layer:
                rel = py_file.relative_to(PROJECT_ROOT).as_posix()
                pytest.fail(f"Domain file {rel} imports: {cross_layer}")

    def test_domain_only_imports_own_module_or_shared(self):
        for py_file in AGENT_DOMAIN.rglob("*.py"):
            imports = _get_imports(py_file)
            for imp in imports:
                if imp.startswith("modules") and not imp.startswith("modules.agent"):
                    rel = py_file.relative_to(PROJECT_ROOT).as_posix()
                    pytest.fail(f"Domain file {rel} imports other module: {imp}")
