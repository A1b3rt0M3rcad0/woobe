import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CORE_APPLICATION_DIR = PROJECT_ROOT / "src" / "modules" / "core" / "application"
CORE_PRESENTATION_DIR = PROJECT_ROOT / "src" / "modules" / "core" / "presentation"


def _get_import_strings_from_file(filepath: Path) -> list[str]:
    source = filepath.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
    return imports


class TestNoNewCoreServiceImports:
    def test_composers_do_not_import_service_use_cases(self):
        composers_dir = CORE_APPLICATION_DIR / "composers"
        violations = []
        for filepath in sorted(composers_dir.rglob("*.py")):
            imports = _get_import_strings_from_file(filepath)
            for imp in imports:
                if "modules.core.service.use_cases" in imp:
                    violations.append(f"{filepath.name}: imports '{imp}'")
        assert not violations, f"Composers must not import from service/use_cases: {violations}"

    def test_controllers_do_not_import_service_layer(self):
        controllers_dir = CORE_PRESENTATION_DIR / "controllers"
        violations = []
        for filepath in sorted(controllers_dir.rglob("*.py")):
            imports = _get_import_strings_from_file(filepath)
            for imp in imports:
                if "modules.core.service" in imp:
                    violations.append(f"{filepath.name}: imports '{imp}'")
        assert not violations, f"Controllers must not import from service/: {violations}"
