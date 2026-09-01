import ast
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CORE_SRC = PROJECT_ROOT / "packages" / "woobe-core" / "src"
SRC_MODULES = CORE_SRC / "modules"
SRC_SHARED = CORE_SRC / "shared"
ALLOWLIST_FILE = PROJECT_ROOT / "tests" / "architecture" / "legacy_import_allowlist.yaml"

FORBIDDEN_USE_CASE_IMPORTS = {"fastapi", "sqlalchemy"}
USE_CASE_PATTERNS = {"service/use_cases.py", "application/use_cases"}
SCOPE = "application_boundaries"
COMPOSER_LOGIC_ALLOWLIST: set[str] = set()


def _relative_posix(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def _load_allowlist() -> set[tuple[str, str]]:
    if not ALLOWLIST_FILE.exists():
        return set()
    with open(ALLOWLIST_FILE, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    entries = data.get("entries") or []
    return {
        (e["file"].replace("\\", "/"), e.get("target_package", ""))
        for e in entries
        if e.get("scope") == SCOPE
    }


class TestApplicationBoundaries:
    def test_no_use_case_imports_fastapi_or_sqlalchemy(self):
        allowlist = _load_allowlist()
        violations = []

        for module_dir in SRC_MODULES.iterdir():
            if not module_dir.is_dir() or module_dir.name.startswith("_"):
                continue

            for py_file in module_dir.rglob("*.py"):
                rel_path = _relative_posix(py_file)
                is_use_case_file = any(pattern in rel_path for pattern in USE_CASE_PATTERNS)
                if not is_use_case_file:
                    continue

                try:
                    source = py_file.read_text(encoding="utf-8")
                    tree = ast.parse(source, filename=str(py_file))
                except (SyntaxError, UnicodeDecodeError):
                    continue

                for node in ast.walk(tree):
                    package = ""
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            top_level = alias.name.split(".")[0]
                            if top_level in FORBIDDEN_USE_CASE_IMPORTS:
                                package = top_level
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        top_level = node.module.split(".")[0]
                        if top_level in FORBIDDEN_USE_CASE_IMPORTS:
                            package = top_level

                    if package and (rel_path, package) not in allowlist:
                        violations.append(f"{rel_path} imports forbidden '{package}'")

        assert not violations, (
            f"Found {len(violations)} use case violation(s):\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    def test_no_composer_contains_domain_logic(self):
        violations = []

        for module_dir in SRC_MODULES.iterdir():
            if not module_dir.is_dir() or module_dir.name.startswith("_"):
                continue

            composer_dir = module_dir / "application" / "composers"
            if not composer_dir.is_dir():
                continue

            for py_file in composer_dir.rglob("*.py"):
                rel_path = _relative_posix(py_file)
                if rel_path in COMPOSER_LOGIC_ALLOWLIST:
                    continue

                try:
                    source = py_file.read_text(encoding="utf-8")
                    tree = ast.parse(source, filename=str(py_file))
                except (SyntaxError, UnicodeDecodeError):
                    continue

                for node in ast.walk(tree):
                    if isinstance(node, (ast.If, ast.For, ast.While, ast.Try)):
                        violations.append(
                            f"{rel_path} contains domain logic ({type(node).__name__})"
                        )
                        break

        assert not violations, (
            f"Found {len(violations)} composer logic violation(s):\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    def test_dtos_not_in_shared(self):
        shared_dtos = list(SRC_SHARED.rglob("**/dtos*"))
        shared_dto_files = [str(p) for p in shared_dtos if p.is_file()]

        assert len(shared_dto_files) == 0, (
            f"DTOs must not live in shared: found {len(shared_dto_files)} file(s)"
        )
