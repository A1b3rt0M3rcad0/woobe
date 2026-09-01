"""Contract tests for spec 006 — presentation layer contract.

Validates that all modules follow the canonical presentation structure:
- Routes only adapt FastAPI and call composers.
- Controllers validate DTOs and call use cases (no session/repository).
- Mappers convert domain output to public schemas (conditional).
- No route contains direct infra access.
"""
import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CORE_SRC = PROJECT_ROOT / "packages" / "woobe-core" / "src"
SRC_MODULES = CORE_SRC / "modules"

REQUIRED_PRESENTATION_FILES = {"routes.py", "schemas.py"}
OPTIONAL_PRESENTATION_FILES = {"mappers.py"}

KNOWN_MODULES = {
    d.name
    for d in SRC_MODULES.iterdir()
    if d.is_dir() and not d.name.startswith("_")
}


def _relative_posix(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def _has_forbidden_imports(source: str) -> list[str]:
    tree = ast.parse(source)
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            parts = node.module.split(".")
            if len(parts) >= 3 and parts[0] == "modules":
                layer = parts[2]
                if layer in {"domain", "infra"}:
                    violations.append(node.module)
                if layer == "application" and "composers" not in node.module:
                    violations.append(node.module)
    return violations


class TestHttpRoutesCompatibility:
    def test_all_modules_have_required_presentation_files(self):
        missing = []
        for mod in KNOWN_MODULES:
            pres_dir = SRC_MODULES / mod / "presentation"
            if not pres_dir.is_dir():
                missing.append(f"{mod}/presentation (directory missing)")
                continue
            for filename in REQUIRED_PRESENTATION_FILES:
                if not (pres_dir / filename).is_file():
                    missing.append(f"{mod}/presentation/{filename}")
        assert not missing, (
            "All modules must have routes.py and schemas.py in presentation/:\n"
            + "\n".join(f"  - {m}" for m in missing)
        )

    def test_presentation_directory_exists_for_all_modules(self):
        missing = []
        for mod in KNOWN_MODULES:
            if not (SRC_MODULES / mod / "presentation").is_dir():
                missing.append(mod)
        assert not missing, (
            "All modules must have a presentation/ directory:\n"
            + "\n".join(f"  - {m}" for m in missing)
        )

    def test_routes_do_not_contain_business_logic(self):
        violations = []
        for mod in KNOWN_MODULES:
            routes_file = SRC_MODULES / mod / "presentation" / "routes.py"
            if not routes_file.is_file():
                continue
            try:
                source = routes_file.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            forbidden = _has_forbidden_imports(source)
            if forbidden:
                violations.append(
                    f"{_relative_posix(routes_file)}: imports domain/infra: {forbidden}"
                )
        assert not violations, (
            "Routes must not import domain or infra layers:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    def test_controllers_do_not_open_direct_sessions(self):
        violations = []
        for mod in KNOWN_MODULES:
            controllers_dir = SRC_MODULES / mod / "presentation" / "controllers"
            if not controllers_dir.is_dir():
                continue
            for py_file in controllers_dir.rglob("*.py"):
                if py_file.name.startswith("_"):
                    continue
                try:
                    source = py_file.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    continue
                if "Session" in source or "session" in source.lower():
                    if "from sqlalchemy" in source or "AsyncSession" in source:
                        violations.append(
                            f"{_relative_posix(py_file)}: references SQLAlchemy session directly"
                        )
        assert not violations, (
            "Controllers must not open direct sessions:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    def test_mappers_are_conditional(self):
        modules_without_mappers = []
        for mod in KNOWN_MODULES:
            pres_dir = SRC_MODULES / mod / "presentation"
            has_schemas = (pres_dir / "schemas.py").is_file()
            has_mappers = (pres_dir / "mappers.py").is_file()
            if has_schemas and not has_mappers:
                modules_without_mappers.append(mod)

        if modules_without_mappers:
            import warnings
            warnings.warn(
                "Modules with schemas.py but no mappers.py (conditional file): "
                + ", ".join(modules_without_mappers)
            )
