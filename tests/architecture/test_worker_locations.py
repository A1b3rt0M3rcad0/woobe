import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CORE_SRC = PROJECT_ROOT / "packages" / "woobe-core" / "src"
WORKER_SRC = PROJECT_ROOT / "packages" / "woobe-workers" / "src"
SRC_MODULES = CORE_SRC / "modules"

KNOWN_MODULES = {
    d.name
    for d in SRC_MODULES.iterdir()
    if d.is_dir() and not d.name.startswith("_")
}


def _relative_posix(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def _extract_module_presentation_imports(file_path: Path) -> list[str]:
    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(file_path))
    except (SyntaxError, UnicodeDecodeError):
        return []

    violations = []
    for node in ast.walk(tree):
        imported_modules: list[str] = []
        if isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)
        elif isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)

        for imported in imported_modules:
            parts = imported.split(".")
            if (
                len(parts) >= 3
                and parts[0] == "modules"
                and parts[1] in KNOWN_MODULES
                and parts[2] == "presentation"
            ):
                violations.append(imported)
    return violations


class TestWorkerLocations:
    def test_worker_process_package_does_not_depend_on_http_presentation(self):
        if not WORKER_SRC.exists():
            return

        violations = []
        for py_file in WORKER_SRC.rglob("*.py"):
            for imported in _extract_module_presentation_imports(py_file):
                violations.append(f"{_relative_posix(py_file)} imports {imported}")

        assert not violations, (
            "woobe-workers is a process composition boundary and must not depend on module presentation/http code:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    def test_concrete_workers_belong_to_core_modules(self):
        if not SRC_MODULES.exists():
            return

        for module_dir in SRC_MODULES.iterdir():
            if not module_dir.is_dir() or module_dir.name.startswith("_"):
                continue
            workers_dir = module_dir / "infra" / "workers"
            if workers_dir.exists():
                for py_file in workers_dir.rglob("*.py"):
                    if py_file.name.startswith("_"):
                        continue
                    try:
                        source = py_file.read_text(encoding="utf-8")
                        tree = ast.parse(source, filename=str(py_file))
                    except (SyntaxError, UnicodeDecodeError):
                        continue
                    for node in ast.walk(tree):
                        if isinstance(node, ast.ClassDef) and "worker" in node.name.lower():
                            rel_path = _relative_posix(py_file)
                            assert rel_path.startswith(
                                "packages/woobe-core/src/modules/"
                            ), (
                                f"Worker {node.name} in {rel_path} is not owned by a Core module"
                            )

    def test_worker_process_package_contains_no_concrete_worker_classes(self):
        if not WORKER_SRC.exists():
            return

        violations = []
        for py_file in WORKER_SRC.rglob("*.py"):
            try:
                tree = ast.parse(
                    py_file.read_text(encoding="utf-8"), filename=str(py_file)
                )
            except (SyntaxError, UnicodeDecodeError):
                continue
            for node in tree.body:
                if isinstance(node, ast.ClassDef) and "worker" in node.name.lower():
                    violations.append(f"{_relative_posix(py_file)}: {node.name}")

        assert not violations, (
            "woobe-workers must contain process bootstrap/composition only; concrete workers belong to woobe-core modules:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    def test_detects_presentation_import_in_worker_process(self):
        forbidden_source = "from modules.agent.presentation.http.routes import router"
        tree = ast.parse(forbidden_source)
        violations = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                parts = node.module.split(".")
                if (
                    len(parts) >= 3
                    and parts[0] == "modules"
                    and parts[1] in KNOWN_MODULES
                    and parts[2] == "presentation"
                ):
                    violations.append(node.module)

        assert violations == ["modules.agent.presentation.http.routes"]
