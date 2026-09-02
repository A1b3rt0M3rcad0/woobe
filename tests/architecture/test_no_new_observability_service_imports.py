import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
OBSERVABILITY_DIR = (
    PROJECT_ROOT
    / "packages"
    / "woobe-core"
    / "src"
    / "modules"
    / "observability"
)

DISALLOWED_SERVICE_IMPORTS = {"modules.observability.service"}
ALLOWED_SERVICE_FILES: set[str] = set()


def _get_import_strings_from_file(filepath: Path) -> list[str]:
    tree = ast.parse(filepath.read_text(encoding="utf-8"))
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    return imports


class TestNoNewObservabilityServiceImports:
    def test_no_new_imports_from_service_module(self):
        violations = []
        for filepath in sorted(OBSERVABILITY_DIR.rglob("*.py")):
            rel = filepath.relative_to(OBSERVABILITY_DIR).as_posix()
            if rel in ALLOWED_SERVICE_FILES:
                continue
            for imported in _get_import_strings_from_file(filepath):
                for disallowed in DISALLOWED_SERVICE_IMPORTS:
                    if imported == disallowed or imported.startswith(disallowed + "."):
                        violations.append(f"{rel}: imports '{imported}'")
        assert not violations, f"New imports from service/ are prohibited: {violations}"
