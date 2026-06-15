import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
CORE_CONTROLLERS_DIR = ROOT / "src" / "modules" / "core" / "presentation" / "controllers"


class TestCoreControllers:
    def test_all_controllers_import_from_application_use_cases(self):
        py_files = sorted(CORE_CONTROLLERS_DIR.glob("*_controller.py"))
        assert len(py_files) > 0, "Controller directory must have controller files"

        violations = []
        for py_file in py_files:
            source = py_file.read_text(encoding="utf-8")
            if "from modules.core.application.use_cases" not in source:
                violations.append(py_file.name)
        assert not violations, (
            f"Controllers must import from application/use_cases: {violations}"
        )

    def test_controllers_do_not_import_repositories(self):
        py_files = sorted(CORE_CONTROLLERS_DIR.glob("*_controller.py"))
        assert len(py_files) > 0, "Controller directory must have controller files"

        violations = []
        for py_file in py_files:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    if "infra.repositories" in node.module or "domain.repositories" in node.module:
                        violations.append(py_file.name)
                        break
        assert not violations, (
            f"Controllers must not import repositories: {violations}"
        )

    def test_controllers_import_use_case_classes(self):
        py_files = sorted(CORE_CONTROLLERS_DIR.glob("*_controller.py"))
        assert len(py_files) > 0, "Controller directory must have controller files"

        has_use_case_import = False
        for py_file in py_files:
            source = py_file.read_text(encoding="utf-8")
            if "UseCase" in source:
                has_use_case_import = True
        assert has_use_case_import, (
            "At least one controller must import a UseCase class"
        )

    def test_controllers_implement_controller_interface(self):
        py_files = sorted(CORE_CONTROLLERS_DIR.glob("*_controller.py"))
        assert len(py_files) > 0, "Controller directory must have controller files"

        has_handle_method = False
        for py_file in py_files:
            source = py_file.read_text(encoding="utf-8")
            if "async def handle" in source:
                has_handle_method = True
        assert has_handle_method, (
            "At least one controller must implement async handle()"
        )

    def test_no_legacy_service_imports_in_controllers(self):
        py_files = sorted(CORE_CONTROLLERS_DIR.glob("*_controller.py"))
        violations = []
        for py_file in py_files:
            source = py_file.read_text(encoding="utf-8")
            if "from modules.core.service" in source:
                violations.append(py_file.name)
        assert not violations, (
            f"No controller should import from legacy service/: {violations}"
        )
