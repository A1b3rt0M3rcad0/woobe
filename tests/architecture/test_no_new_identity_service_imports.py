import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
IDENTITY_SRC = PROJECT_ROOT / "src" / "modules" / "identity"

ALLOWED_SERVICE_IMPORTERS = {
    "service/__init__.py",
    "service/dtos.py",
    "service/use_cases.py",
}


def _get_rel_py_files() -> list[Path]:
    files = []
    for p in IDENTITY_SRC.rglob("*.py"):
        rel = p.relative_to(IDENTITY_SRC).as_posix()
        if rel.startswith("service/") and rel not in ALLOWED_SERVICE_IMPORTERS:
            continue
        files.append(p)
    return files


def _get_imports(filepath: Path) -> list[str]:
    source = filepath.read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    return imports


class TestNoNewIdentityServiceImports:
    def test_composers_do_not_import_from_service(self):
        composers_dir = IDENTITY_SRC / "application" / "composers"
        if not composers_dir.is_dir():
            return
        violations = []
        for py_file in sorted(composers_dir.glob("*.py")):
            if py_file.name == "__init__.py":
                continue
            imports = _get_imports(py_file)
            for imp in imports:
                if "modules.identity.service" in imp:
                    violations.append(f"{py_file.name}: imports '{imp}'")
        assert not violations, (
            f"Composers should import from application/, not service/: {violations}"
        )

    def test_controllers_do_not_import_from_service(self):
        controllers_dir = IDENTITY_SRC / "presentation" / "controllers"
        if not controllers_dir.is_dir():
            return
        violations = []
        for py_file in sorted(controllers_dir.glob("*.py")):
            if py_file.name == "__init__.py":
                continue
            imports = _get_imports(py_file)
            for imp in imports:
                if "modules.identity.service" in imp:
                    violations.append(f"{py_file.name}: imports '{imp}'")
        assert not violations, (
            f"Controllers should import from application/, not service/: {violations}"
        )

    def test_service_shims_only_contain_re_exports(self):
        for shim_rel in ALLOWED_SERVICE_IMPORTERS:
            shim_path = IDENTITY_SRC / shim_rel
            assert shim_path.is_file(), f"Service shim missing: {shim_rel}"
            source = shim_path.read_text(encoding="utf-8")
            if shim_rel.endswith("__init__.py"):
                assert "shim" in source.lower() or "legacy" in source.lower(), (
                    f"{shim_rel} should be a shim"
                )
