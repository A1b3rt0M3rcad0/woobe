from __future__ import annotations

import ast
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[3]
AGENT_APP = PROJECT_ROOT / "packages" / "woobe-core" / "src" / "modules" / "agent" / "application"

REQUIRED_APP_DIRS = ["composers", "dtos", "handlers", "use_cases"]

FORBIDDEN_FRAMEWORK_MODULES = {"sqlalchemy", "fastapi", "asyncpg", "aiormq"}
RUNTIME_ORCHESTRATION_FILES = {
    "ask_agent_stream_service.py",
    "ask_use_case.py",
    "instrumented_execution_finalizer.py",
}


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


class TestNormalizeAgentApplicationLayout:
    def test_application_has_all_required_directories(self):
        for name in REQUIRED_APP_DIRS:
            dir_path = AGENT_APP / name
            assert dir_path.is_dir(), f"Missing application directory: {name}/"

    def test_dtos_package_exports_all_dtos(self):
        dto_init = AGENT_APP / "dtos" / "__init__.py"
        assert dto_init.exists()
        source = dto_init.read_text(encoding="utf-8")
        assert "__all__" in source, "dtos/__init__.py must define __all__"
        assert len(source) > 500, "dtos/__init__.py must have meaningful re-exports"

    def test_use_cases_package_exports_all_use_cases(self):
        uc_init = AGENT_APP / "use_cases" / "__init__.py"
        assert uc_init.exists()
        source = uc_init.read_text(encoding="utf-8")
        assert "__all__" in source, "use_cases/__init__.py must define __all__"
        assert len(source) > 500, "use_cases/__init__.py must have meaningful re-exports"

    def test_composers_directory_has_multiple_files(self):
        composers_dir = AGENT_APP / "composers"
        assert composers_dir.is_dir()
        py_files = [
            f
            for f in composers_dir.iterdir()
            if f.suffix == ".py" and not f.name.startswith("__")
        ]
        assert len(py_files) >= 40, f"Expected 40+ composers, found {len(py_files)}"

    def test_handlers_directory_has_init(self):
        handlers_dir = AGENT_APP / "handlers"
        assert handlers_dir.is_dir()
        assert (handlers_dir / "__init__.py").exists()

    def test_no_application_file_imports_framework_libraries(self):
        for py_file in AGENT_APP.rglob("*.py"):
            if "__pycache__" in py_file.parts:
                continue
            if py_file.parent.name == "composers":
                continue
            if py_file.name in RUNTIME_ORCHESTRATION_FILES:
                continue
            imports = _get_imports(py_file)
            framework_refs = [
                module
                for module in imports
                if module.split(".")[0].lower() in FORBIDDEN_FRAMEWORK_MODULES
            ]
            if framework_refs:
                rel = py_file.relative_to(PROJECT_ROOT).as_posix()
                pytest.fail(f"Application file {rel} imports: {framework_refs}")

    def test_use_cases_only_import_domain_or_shared(self):
        for py_file in (AGENT_APP / "use_cases").rglob("*.py"):
            if "__pycache__" in py_file.parts or py_file.name == "__init__.py":
                continue
            if py_file.name in RUNTIME_ORCHESTRATION_FILES:
                continue
            imports = _get_imports(py_file)
            for imp in imports:
                parts = imp.split(".")
                if len(parts) >= 3 and parts[:2] == ["modules", "agent"]:
                    layer = parts[2]
                    if layer in ("infra", "presentation"):
                        rel = py_file.relative_to(PROJECT_ROOT).as_posix()
                        pytest.fail(f"Use case file {rel} imports {layer}: {imp}")

    def test_dto_imports_can_be_resolved_through_package(self):
        dto_init = AGENT_APP / "dtos" / "__init__.py"
        tree = ast.parse(dto_init.read_text(encoding="utf-8"), filename=str(dto_init))
        exports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "__all__":
                        if isinstance(node.value, ast.List):
                            exports = {
                                element.value
                                for element in node.value.elts
                                if isinstance(element, ast.Constant)
                            }
        assert len(exports) >= 60, f"Expected 60+ DTO exports, found {len(exports)}"
