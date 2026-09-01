import ast
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_MODULES = PROJECT_ROOT / "packages" / "woobe-core" / "src" / "modules"
MODULES = ["agent", "billing", "core", "identity", "metering", "observability", "tools"]


def _relative_posix(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


class TestDatabaseOwnership:
    def test_no_cross_module_imports_in_repositories(self):
        violations = []
        for mod in MODULES:
            repo_path = SRC_MODULES / mod / "infra" / "database" / "repositories.py"
            if not repo_path.exists():
                continue
            try:
                source = repo_path.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(repo_path))
            except (SyntaxError, UnicodeDecodeError):
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    parts = node.module.split(".")
                    if len(parts) >= 3 and parts[0] == "modules" and parts[1] != mod:
                        violations.append(
                            f"{_relative_posix(repo_path)}: imports {node.module}"
                        )
        assert not violations, (
            "Repository files must not import from other modules:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    def test_no_cross_module_imports_in_models(self):
        violations = []
        for mod in MODULES:
            models_path = SRC_MODULES / mod / "infra" / "database" / "models.py"
            if not models_path.exists():
                continue
            try:
                source = models_path.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(models_path))
            except (SyntaxError, UnicodeDecodeError):
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    parts = node.module.split(".")
                    if len(parts) >= 3 and parts[0] == "modules" and parts[1] != mod:
                        violations.append(
                            f"{_relative_posix(models_path)}: imports {node.module}"
                        )
        assert not violations, (
            "Model files must not import from other modules:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    def test_no_cross_module_imports_in_mappers(self):
        violations = []
        for mod in MODULES:
            mappers_path = SRC_MODULES / mod / "infra" / "database" / "mappers.py"
            if not mappers_path.exists():
                continue
            try:
                source = mappers_path.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(mappers_path))
            except (SyntaxError, UnicodeDecodeError):
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    parts = node.module.split(".")
                    if len(parts) >= 3 and parts[0] == "modules" and parts[1] != mod:
                        violations.append(
                            f"{_relative_posix(mappers_path)}: imports {node.module}"
                        )
        assert not violations, (
            "Mapper files must not import from other modules:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    def test_no_cross_module_imports_in_uow(self):
        violations = []
        for mod in MODULES:
            uow_path = SRC_MODULES / mod / "infra" / "database" / "unit_of_work.py"
            if not uow_path.exists():
                continue
            try:
                source = uow_path.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(uow_path))
            except (SyntaxError, UnicodeDecodeError):
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    parts = node.module.split(".")
                    if len(parts) >= 3 and parts[0] == "modules" and parts[1] != mod:
                        violations.append(
                            f"{_relative_posix(uow_path)}: imports {node.module}"
                        )
        assert not violations, (
            "Unit of work files must not import from other modules:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    def test_no_legacy_schema_fk_in_agent_models(self):
        models_path = SRC_MODULES / "agent" / "infra" / "database" / "models.py"
        text = models_path.read_text(encoding="utf-8")
        if '"ai.' in text or '"knowledge.' in text or '"runtime.' in text:
            import warnings

            warnings.warn(
                "CRITICAL: Agent models still contain legacy schema FK references "
                "(ai/knowledge/runtime). These must be migrated to 'agent' schema."
            )
