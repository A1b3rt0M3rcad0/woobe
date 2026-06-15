import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OBSERVABILITY_DIR = PROJECT_ROOT / "src" / "modules" / "observability"

DISALLOWED_SERVICE_IMPORTS = {
    "modules.observability.service",
}

ALLOWED_SERVICE_FILES = {
    "service/dtos.py",
    "service/use_cases.py",
    "service/__init__.py",
}


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


class TestNoNewObservabilityServiceImports:
    def test_no_new_imports_from_service_module(self):
        py_files = list(OBSERVABILITY_DIR.rglob("*.py"))
        violations = []
        for filepath in sorted(py_files):
            rel = filepath.relative_to(OBSERVABILITY_DIR).as_posix()
            if rel in ALLOWED_SERVICE_FILES:
                continue
            imports = _get_import_strings_from_file(filepath)
            for imp in imports:
                for disallowed in DISALLOWED_SERVICE_IMPORTS:
                    if imp == disallowed or imp.startswith(disallowed + "."):
                        violations.append(f"{rel}: imports '{imp}'")

        assert not violations, (
            f"New imports from service/ are prohibited: {violations}"
        )
