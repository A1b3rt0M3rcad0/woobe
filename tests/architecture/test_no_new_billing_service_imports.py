import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BILLING_ROOT = PROJECT_ROOT / "src" / "editions" / "cloud" / "billing"
BILLING_COMPOSERS_DIR = BILLING_ROOT / "application" / "composers"
BILLING_CONTROLLERS_DIR = BILLING_ROOT / "presentation" / "controllers"

FORBIDDEN_IMPORT_PREFIXES = (
    "editions.cloud.billing.service",
    "modules.billing",
)


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


def _assert_no_forbidden_imports(py_files: list[Path]) -> None:
    violations = []
    for filepath in sorted(py_files):
        for imp in _get_import_strings_from_file(filepath):
            for forbidden in FORBIDDEN_IMPORT_PREFIXES:
                if imp.startswith(forbidden):
                    violations.append(f"{filepath.name}: imports '{imp}'")
    assert not violations, f"Cloud Billing contains forbidden imports: {violations}"


class TestNoLegacyBillingImports:
    def test_compatibility_shim_is_removed(self):
        assert not (PROJECT_ROOT / "src" / "modules" / "billing.py").exists()
        assert not (PROJECT_ROOT / "src" / "modules" / "billing").exists()

    def test_cloud_billing_package_uses_canonical_namespace(self):
        _assert_no_forbidden_imports(list(BILLING_ROOT.rglob("*.py")))

    def test_composers_do_not_import_service_or_legacy_namespace(self):
        py_files = list(BILLING_COMPOSERS_DIR.rglob("*.py"))
        assert py_files, "Cloud Billing composers directory must exist"
        _assert_no_forbidden_imports(py_files)

    def test_controllers_do_not_import_service_or_legacy_namespace(self):
        py_files = list(BILLING_CONTROLLERS_DIR.rglob("*.py"))
        assert py_files, "Cloud Billing controllers directory must exist"
        _assert_no_forbidden_imports(py_files)
