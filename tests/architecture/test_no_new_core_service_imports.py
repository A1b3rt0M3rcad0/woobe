import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CORE_ROOT = (
    PROJECT_ROOT / "packages" / "woobe-core" / "src" / "modules" / "core"
)
CORE_COMPOSITION_DIR = CORE_ROOT / "composition" / "composers"
CORE_PRESENTATION_DIR = CORE_ROOT / "presentation"


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    return imports


class TestNoNewCoreServiceImports:
    def test_composers_do_not_import_legacy_service_use_cases(self):
        violations = [
            path.name
            for path in sorted(CORE_COMPOSITION_DIR.rglob("*.py"))
            if "modules.core.service.use_cases" in _imports(path)
        ]
        assert not violations

    def test_controllers_do_not_import_service_layer(self):
        violations = [
            path.name
            for path in sorted(CORE_PRESENTATION_DIR.rglob("*.py"))
            if "modules.core.service" in _imports(path)
        ]
        assert not violations
