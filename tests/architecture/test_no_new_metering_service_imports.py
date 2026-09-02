import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
METERING_ROOT = (
    PROJECT_ROOT / "packages" / "woobe-core" / "src" / "modules" / "metering"
)
METERING_COMPOSERS_DIR = METERING_ROOT / "composition" / "composers"
METERING_CONTROLLERS_DIR = METERING_ROOT / "presentation" / "controllers"

FORBIDDEN_IMPORT_PREFIXES = ("modules.metering.service",)


def _get_import_strings_from_file(filepath: Path) -> list[str]:
    source = filepath.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    return imports


class TestNoNewMeteringServiceImports:
    def test_composers_do_not_import_service(self):
        py_files = list(METERING_COMPOSERS_DIR.rglob("*.py"))
        assert py_files, "Composers directory must exist"

        violations = []
        for filepath in sorted(py_files):
            imports = _get_import_strings_from_file(filepath)
            for imp in imports:
                for forbidden in FORBIDDEN_IMPORT_PREFIXES:
                    if imp.startswith(forbidden):
                        violations.append(f"{filepath.name}: imports '{imp}'")

        assert not violations, f"Composers must not import service/: {violations}"

    def test_controllers_do_not_import_service(self):
        py_files = list(METERING_CONTROLLERS_DIR.rglob("*.py"))
        assert py_files, "Controllers directory must exist"

        violations = []
        for filepath in sorted(py_files):
            imports = _get_import_strings_from_file(filepath)
            for imp in imports:
                for forbidden in FORBIDDEN_IMPORT_PREFIXES:
                    if imp.startswith(forbidden):
                        violations.append(f"{filepath.name}: imports '{imp}'")

        assert not violations, f"Controllers must not import service/: {violations}"
