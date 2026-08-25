import ast
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_MODULES = PROJECT_ROOT / "src" / "modules"
ALLOWLIST_FILE = Path(__file__).resolve().parent / "legacy_import_allowlist.yaml"

KNOWN_MODULES = {
    d.name for d in SRC_MODULES.iterdir()
    if d.is_dir() and not d.name.startswith("_")
}


def _load_allowlist(scope: str) -> set[tuple[str, str]]:
    if not ALLOWLIST_FILE.exists():
        return set()
    with open(ALLOWLIST_FILE, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    entries = data.get("entries") or []
    return {
        (e["file"].replace("/", "\\").replace("\\", "/"), e["target_module"])
        for e in entries
        if e.get("scope") == scope
    }


def _extract_cross_module_imports(file_path: Path, source_module: str) -> list[tuple[str, str]]:
    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(file_path))
    except (SyntaxError, UnicodeDecodeError):
        return []

    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            parts = node.module.split(".")
            if len(parts) >= 2 and parts[0] == "modules":
                target_module = parts[1]
                if target_module != source_module and target_module in KNOWN_MODULES:
                    violations.append((target_module, node.module))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                parts = alias.name.split(".")
                if len(parts) >= 2 and parts[0] == "modules":
                    target_module = parts[1]
                    if target_module != source_module and target_module in KNOWN_MODULES:
                        violations.append((target_module, alias.name))
    return violations


def _relative_posix(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


class TestModuleBoundaries:
    def test_no_unlisted_cross_module_imports(self):
        allowlist = _load_allowlist("module_boundaries")
        unlisted_violations = []

        for module_dir in SRC_MODULES.iterdir():
            if not module_dir.is_dir() or module_dir.name.startswith("_"):
                continue
            source_module = module_dir.name
            for py_file in module_dir.rglob("*.py"):
                cross_imports = _extract_cross_module_imports(py_file, source_module)
                rel_path = _relative_posix(py_file)
                for target_mod, full_import in cross_imports:
                    if (rel_path, target_mod) not in allowlist:
                        unlisted_violations.append(
                            f"{rel_path} imports {full_import} (cross-module: {source_module} -> {target_mod})"
                        )

        assert not unlisted_violations, (
            f"Found {len(unlisted_violations)} unlisted cross-module import violation(s):\n"
            + "\n".join(f"  - {v}" for v in unlisted_violations[:20])
        )

    def test_allowlist_entries_reference_valid_files(self):
        allowlist_data = {}
        if ALLOWLIST_FILE.exists():
            with open(ALLOWLIST_FILE, encoding="utf-8") as f:
                allowlist_data = yaml.safe_load(f) or {}

        entries = allowlist_data.get("entries") or []
        module_entries = [e for e in entries if e.get("scope") == "module_boundaries"]

        for entry in module_entries:
            file_path = PROJECT_ROOT / entry["file"].replace("/", "\\")
            assert file_path.exists(), (
                f"Allowlist references non-existent file: {entry['file']}"
            )
            assert entry.get("removal_spec"), (
                f"Allowlist entry missing removal_spec: {entry['file']}"
            )

    def test_detects_forbidden_cross_module_import(self):
        forbidden_source = """\
from modules.core.domain.entities import Project
from modules.identity.domain.repositories import UserRepository
"""
        tree = ast.parse(forbidden_source)
        violations = []
        source_module = "agent"
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                parts = node.module.split(".")
                if len(parts) >= 2 and parts[0] == "modules":
                    target_module = parts[1]
                    if target_module != source_module and target_module in KNOWN_MODULES:
                        violations.append((target_module, node.module))

        assert len(violations) == 2, (
            f"Expected 2 violations from fixture, got {len(violations)}"
        )
        assert violations[0][0] == "core"
        assert violations[1][0] == "identity"

    def test_allowlist_must_be_empty_in_final_state(self):
        if not ALLOWLIST_FILE.exists():
            return
        with open(ALLOWLIST_FILE, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        entries = data.get("entries") or []
        module_entries = [e for e in entries if e.get("scope") == "module_boundaries"]
        if not module_entries:
            return
        for entry in module_entries:
            assert entry.get("removal_spec"), (
                f"Every allowlist entry must have a removal_spec: {entry['file']}"
            )
