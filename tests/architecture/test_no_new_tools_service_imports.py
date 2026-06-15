import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TOOLS_SRC = PROJECT_ROOT / "src" / "modules" / "tools"




def _get_imports_from_file(filepath: Path) -> list[str]:
    source = filepath.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    return imports


class TestNoNewToolsServiceImports:
    def test_composers_do_not_import_from_service(self):
        composers_dir = TOOLS_SRC / "application" / "composers"
        if not composers_dir.is_dir():
            return
        violations = []
        for py_file in sorted(composers_dir.rglob("*.py")):
            if py_file.name.startswith("__"):
                continue
            imports = _get_imports_from_file(py_file)
            for imp in imports:
                if "modules.tools.service" in imp:
                    violations.append(f"{py_file.name}: imports '{imp}'")
        assert not violations, (
            f"Composers must not import from service/: {violations}"
        )

    def test_controllers_do_not_import_from_service(self):
        controllers_dir = TOOLS_SRC / "presentation" / "controllers"
        if not controllers_dir.is_dir():
            return
        violations = []
        for py_file in sorted(controllers_dir.rglob("*.py")):
            if py_file.name.startswith("__"):
                continue
            imports = _get_imports_from_file(py_file)
            for imp in imports:
                if "modules.tools.service" in imp:
                    violations.append(f"{py_file.name}: imports '{imp}'")
        assert not violations, (
            f"Controllers must not import from service/: {violations}"
        )
