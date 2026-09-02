import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[5]
IDENTITY_CONTROLLERS_DIR = (
    PROJECT_ROOT
    / "packages"
    / "woobe-core"
    / "src"
    / "modules"
    / "identity"
    / "presentation"
    / "controllers"
)


class TestIdentityControllers:
    def test_all_controllers_depend_on_application_use_case_contract(self):
        py_files = sorted(IDENTITY_CONTROLLERS_DIR.glob("*_controller.py"))
        assert py_files, "Controller directory must have controller files"

        violations = []
        for py_file in py_files:
            source = py_file.read_text(encoding="utf-8")
            if "from modules.identity.application.interfaces.use_case import UseCase" not in source:
                violations.append(py_file.name)
        assert not violations, (
            f"Controllers must depend on the application UseCase contract: {violations}"
        )

    def test_controllers_do_not_import_repositories(self):
        py_files = sorted(IDENTITY_CONTROLLERS_DIR.glob("*_controller.py"))
        assert py_files

        violations = []
        for py_file in py_files:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    if "infra.repositories" in node.module or "domain.repositories" in node.module:
                        violations.append(py_file.name)
                        break
        assert not violations, f"Controllers must not import repositories: {violations}"

    def test_controllers_do_not_import_concrete_use_cases(self):
        py_files = sorted(IDENTITY_CONTROLLERS_DIR.glob("*_controller.py"))
        violations = []
        for py_file in py_files:
            source = py_file.read_text(encoding="utf-8")
            if "from modules.identity.application.use_cases" in source:
                violations.append(py_file.name)
        assert not violations, f"Controllers import concrete use cases: {violations}"

    def test_controllers_implement_controller_interface(self):
        py_files = sorted(IDENTITY_CONTROLLERS_DIR.glob("*_controller.py"))
        assert any(
            "async def handle" in py_file.read_text(encoding="utf-8")
            for py_file in py_files
        )

    def test_no_legacy_service_imports_in_controllers(self):
        py_files = sorted(IDENTITY_CONTROLLERS_DIR.glob("*_controller.py"))
        violations = []
        for py_file in py_files:
            source = py_file.read_text(encoding="utf-8")
            if "from modules.identity.service" in source:
                violations.append(py_file.name)
        assert not violations
