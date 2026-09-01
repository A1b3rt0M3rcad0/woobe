import ast
import fnmatch
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CORE_SRC = PROJECT_ROOT / "packages" / "woobe-core" / "src"
SRC_MODULES = CORE_SRC / "modules"
ALLOWLIST_FILE = PROJECT_ROOT / "tests" / "architecture" / "legacy_import_allowlist.yaml"


def _load_allowlist_patterns(scope: str) -> list[str]:
    if not ALLOWLIST_FILE.exists():
        return []
    with open(ALLOWLIST_FILE, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    entries = data.get("entries") or []
    return [
        e["file"].replace("\\", "/")
        for e in entries
        if e.get("scope") == scope
    ]


def _is_allowlisted(rel_path: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(rel_path, p) for p in patterns)


def _find_all_uow_files() -> list[Path]:
    return sorted(SRC_MODULES.rglob("unit_of_work.py"))


def _module_from_path(file_path: Path) -> str:
    rel = file_path.relative_to(SRC_MODULES)
    return rel.parts[0]


def _extract_imported_modules(source: str) -> list[str]:
    tree = ast.parse(source)
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            parts = node.module.split(".")
            if len(parts) >= 3 and parts[0] == "modules":
                imported.append(parts[1])
        elif isinstance(node, ast.Import):
            for alias in node.names:
                parts = alias.name.split(".")
                if len(parts) >= 3 and parts[0] == "modules":
                    imported.append(parts[1])
    return imported


class TestUnitOfWorkOwnership:
    def test_uow_does_not_import_other_module_repositories(self):
        uow_files = _find_all_uow_files()
        assert len(uow_files) >= 1, "At least one unit_of_work.py must exist"

        violations = []
        for uow_file in uow_files:
            source_mod = _module_from_path(uow_file)
            try:
                source = uow_file.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            imported = _extract_imported_modules(source)
            for mod in set(imported):
                if mod != source_mod:
                    violations.append(
                        f"{uow_file.relative_to(PROJECT_ROOT).as_posix()}: "
                        f"imports repository from module '{mod}' (own module: '{source_mod}')"
                    )

        assert not violations, (
            "UnitOfWork implementations must not import repositories from other modules:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    def test_postgres_unit_of_work_not_used_in_composers(self):
        allowlist = _load_allowlist_patterns("uow_ownership")
        violations = []

        for py_file in SRC_MODULES.rglob("*.py"):
            if "composer" not in py_file.name.lower():
                continue
            try:
                source = py_file.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue

            if "PostgresUnitOfWork" in source:
                rel = py_file.relative_to(PROJECT_ROOT).as_posix()
                if not _is_allowlisted(rel, allowlist):
                    violations.append(rel)

        assert not violations, (
            "Composers must not instantiate PostgresUnitOfWork directly:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    def test_uow_exposes_outbox_and_inbox(self):
        uow_files = _find_all_uow_files()
        assert len(uow_files) >= 1

        for uow_file in uow_files:
            try:
                source = uow_file.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue

            tree = ast.parse(source)
            outbox_props = []
            inbox_props = []
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == "outbox":
                    outbox_props.append(node)
                if isinstance(node, ast.FunctionDef) and node.name == "inbox":
                    inbox_props.append(node)

            if "agent" in uow_file.parent.as_posix().lower():
                assert len(outbox_props) >= 1, (
                    f"{uow_file.relative_to(PROJECT_ROOT).as_posix()}: missing outbox property"
                )
                assert len(inbox_props) >= 1, (
                    f"{uow_file.relative_to(PROJECT_ROOT).as_posix()}: missing inbox property"
                )
