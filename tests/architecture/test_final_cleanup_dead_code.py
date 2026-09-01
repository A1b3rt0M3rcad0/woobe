"""Current dead-code and post-migration architecture checks."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE_SRC = ROOT / "packages" / "woobe-core" / "src"
PYTHON_SOURCE_ROOTS = (
    CORE_SRC,
    ROOT / "packages" / "woobe-api" / "src",
    ROOT / "packages" / "woobe-workers" / "src",
)
LEGACY_MODULES = {"ai", "knowledge", "runtime"}
AUTOGEN_PARTS = {"__pycache__", ".pytest_cache", ".venv", ".git"}
CANONICAL_MODULES = {"agent", "billing", "core", "identity", "metering", "observability"}


def _is_autogen(path: Path) -> bool:
    return any(part in AUTOGEN_PARTS for part in path.parts)


def _imports(path: Path) -> list[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        return []
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
        elif isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
    return imports


def _python_files() -> list[Path]:
    files: list[Path] = []
    for source_root in PYTHON_SOURCE_ROOTS:
        if source_root.is_dir():
            files.extend(source_root.rglob("*.py"))
    return files


class TestFinalCleanupDeadCode:
    def test_no_imports_from_removed_modules(self):
        violations = []
        for py_file in _python_files():
            if _is_autogen(py_file):
                continue
            for module in _imports(py_file):
                parts = module.split(".")
                if len(parts) >= 2 and parts[0] == "modules" and parts[1] in LEGACY_MODULES:
                    violations.append(f"{py_file.relative_to(ROOT)}: {module}")
        assert not violations, "Imports from removed modules:\n" + "\n".join(violations)

    def test_no_orphan_package_markers(self):
        orphaned = []
        for source_root in PYTHON_SOURCE_ROOTS:
            if not source_root.is_dir():
                continue
            for init_file in source_root.rglob("__init__.py"):
                if _is_autogen(init_file) or init_file.read_text(encoding="utf-8").strip():
                    continue
                siblings = [
                    child for child in init_file.parent.iterdir()
                    if child.name != "__init__.py" and child.name != "__pycache__"
                ]
                if not siblings:
                    orphaned.append(init_file.relative_to(ROOT).as_posix())
        assert not orphaned, f"Orphaned __init__.py files: {orphaned}"

    def test_no_duplicate_public_top_level_definitions_in_agent_layers(self):
        duplicates = []
        agent_dir = CORE_SRC / "modules" / "agent"
        for layer_name in ("domain", "application", "infra", "presentation"):
            layer_dir = agent_dir / layer_name
            definitions: dict[str, str] = {}
            for py_file in layer_dir.rglob("*.py"):
                if _is_autogen(py_file) or py_file.name.startswith("__"):
                    continue
                try:
                    tree = ast.parse(py_file.read_text(encoding="utf-8", errors="replace"))
                except SyntaxError:
                    continue
                for node in tree.body:
                    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                        continue
                    if node.name.startswith("_"):
                        continue
                    current = py_file.relative_to(ROOT).as_posix()
                    previous = definitions.get(node.name)
                    if previous and previous != current:
                        duplicates.append(
                            f"{layer_name}: {node.name} in {previous} and {current}"
                        )
                    definitions[node.name] = current
        assert not duplicates, f"Duplicate public top-level definitions: {duplicates}"

    def test_canonical_modules_and_agent_layers_exist(self):
        modules_dir = CORE_SRC / "modules"
        actual = {
            path.name for path in modules_dir.iterdir()
            if path.is_dir() and not path.name.startswith("_")
        }
        assert CANONICAL_MODULES.issubset(actual)
        assert "tools" not in actual, "Tools are consolidated into the agent bounded context"
        for layer in ("domain", "application", "infra", "presentation"):
            assert (modules_dir / "agent" / layer).is_dir()

    def test_shared_layer_exists(self):
        assert (CORE_SRC / "shared").is_dir()


class TestFinalCleanupDetectionFixtures:
    def test_detects_removed_module_import(self):
        tree = ast.parse("from modules.ai.domain.entities import Agent\n")
        imports = [
            node.module for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        ]
        assert imports == ["modules.ai.domain.entities"]

    def test_placeholder_has_no_definition(self):
        tree = ast.parse('"""Placeholder-only docstring."""')
        assert not any(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Assign))
            for node in ast.walk(tree)
        )
