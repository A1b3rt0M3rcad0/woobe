import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BILLING_COMPOSERS_DIR = PROJECT_ROOT / "src" / "modules" / "billing" / "application" / "composers"
BILLING_CONTROLLERS_DIR = PROJECT_ROOT / "src" / "modules" / "billing" / "presentation" / "controllers"


FORBIDDEN_IMPORT_PREFIXES = ("modules.billing.service",)


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


class TestNoNewBillingServiceImports:
    def test_composers_do_not_import_service(self):
        py_files = list(BILLING_COMPOSERS_DIR.rglob("*.py"))
        assert len(py_files) > 0, "Composers directory must exist"

        violations = []
        for filepath in sorted(py_files):
            imports = _get_import_strings_from_file(filepath)
            for imp in imports:
                for forbidden in FORBIDDEN_IMPORT_PREFIXES:
                    if imp.startswith(forbidden):
                        violations.append(f"{filepath.name}: imports '{imp}'")

        assert not violations, (
            f"Composers must not import service/: {violations}"
        )

    def test_controllers_do_not_import_service(self):
        py_files = list(BILLING_CONTROLLERS_DIR.rglob("*.py"))
        assert len(py_files) > 0, "Controllers directory must exist"

        violations = []
        for filepath in sorted(py_files):
            imports = _get_import_strings_from_file(filepath)
            for imp in imports:
                for forbidden in FORBIDDEN_IMPORT_PREFIXES:
                    if imp.startswith(forbidden):
                        violations.append(f"{filepath.name}: imports '{imp}'")

        assert not violations, (
            f"Controllers must not import service/: {violations}"
        )
