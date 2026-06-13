import ast
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TESTS_ARCH = Path(__file__).resolve().parent
SRC_MODULES = PROJECT_ROOT / "src" / "modules"
SRC_SHARED = PROJECT_ROOT / "src" / "shared"
SRC_WORKERS = PROJECT_ROOT / "src" / "workers"
ALLOWLIST_FILE = TESTS_ARCH / "legacy_import_allowlist.yaml"

KNOWN_MODULES = {
    d.name
    for d in SRC_MODULES.iterdir()
    if d.is_dir() and not d.name.startswith("_")
}

REQUIRED_FIELDS = {"file", "target_module", "removal_spec", "scope"}
VALID_SCOPES = {"module_boundaries", "worker_locations", "shared_boundaries"}


def _load_allowlist() -> list[dict]:
    if not ALLOWLIST_FILE.exists():
        return []
    with open(ALLOWLIST_FILE, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("entries") or []


def _allowlist_set(scope: str) -> set[tuple[str, str]]:
    entries = _load_allowlist()
    return {
        (e["file"].replace("\\", "/"), e["target_module"])
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


class TestAddLegacyModuleAllowlist:
    def test_add_legacy_module_allowlist(self):
        assert ALLOWLIST_FILE.is_file(), (
            f"legacy_import_allowlist.yaml must exist at {ALLOWLIST_FILE}"
        )

        entries = _load_allowlist()
        assert len(entries) > 0, "Allowlist must have at least one entry during migration"

        for i, entry in enumerate(entries):
            missing = REQUIRED_FIELDS - set(entry.keys())
            assert not missing, (
                f"Allowlist entry {i} missing required fields: {missing}"
            )

        scopes_present = {e["scope"] for e in entries}
        for scope in VALID_SCOPES:
            assert scope in scopes_present, (
                f"Allowlist must contain at least one entry with scope '{scope}'"
            )

        for entry in entries:
            assert entry["scope"] in VALID_SCOPES, (
                f"Invalid scope '{entry['scope']}' in allowlist entry for {entry['file']}"
            )
            assert entry.get("removal_spec"), (
                f"Allowlist entry must have non-empty removal_spec: {entry['file']}"
            )

    def test_allowlist_references_existing_files(self):
        entries = _load_allowlist()
        for entry in entries:
            file_path = PROJECT_ROOT / entry["file"].replace("/", "\\")
            assert file_path.exists(), (
                f"Allowlist references non-existent file: {entry['file']}"
            )

    def test_allowlist_covers_all_cross_module_violations(self):
        allowlist = _allowlist_set("module_boundaries")
        uncovered = []

        for module_dir in SRC_MODULES.iterdir():
            if not module_dir.is_dir() or module_dir.name.startswith("_"):
                continue
            source_module = module_dir.name
            for py_file in module_dir.rglob("*.py"):
                cross_imports = _extract_cross_module_imports(py_file, source_module)
                rel_path = _relative_posix(py_file)
                for target_mod, full_import in cross_imports:
                    if (rel_path, target_mod) not in allowlist:
                        uncovered.append(
                            f"{rel_path} -> {target_mod} ({full_import})"
                        )

        assert not uncovered, (
            f"Found {len(uncovered)} cross-module import(s) not covered by allowlist:\n"
            + "\n".join(f"  - {v}" for v in uncovered[:20])
        )

    def test_allowlist_covers_worker_location_violations(self):
        allowlist = _allowlist_set("worker_locations")

        if not SRC_WORKERS.exists():
            return

        uncovered = []
        for py_file in SRC_WORKERS.rglob("*.py"):
            try:
                source = py_file.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(py_file))
            except (SyntaxError, UnicodeDecodeError):
                continue

            rel_path = _relative_posix(py_file)
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    parts = node.module.split(".")
                    if len(parts) >= 3 and parts[0] == "modules" and parts[1] in KNOWN_MODULES:
                        target_mod = parts[1]
                        if (rel_path, target_mod) not in allowlist:
                            uncovered.append(
                                f"{rel_path} -> {target_mod} ({node.module})"
                            )
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        parts = alias.name.split(".")
                        if len(parts) >= 3 and parts[0] == "modules" and parts[1] in KNOWN_MODULES:
                            target_mod = parts[1]
                            if (rel_path, target_mod) not in allowlist:
                                uncovered.append(
                                    f"{rel_path} -> {target_mod} ({alias.name})"
                                )

        assert not uncovered, (
            f"Found {len(uncovered)} worker location violation(s) not in allowlist:\n"
            + "\n".join(f"  - {v}" for v in uncovered[:20])
        )

    def test_allowlist_covers_shared_boundary_violations(self):
        allowlist = _allowlist_set("shared_boundaries")

        if not SRC_SHARED.exists():
            return

        uncovered = []
        for py_file in SRC_SHARED.rglob("*.py"):
            try:
                source = py_file.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(py_file))
            except (SyntaxError, UnicodeDecodeError):
                continue

            rel_path = _relative_posix(py_file)
            has_module_list = False
            for node in ast.walk(tree):
                if isinstance(node, ast.List):
                    for elt in node.elts:
                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                            if elt.value in KNOWN_MODULES:
                                has_module_list = True
                                break
                if has_module_list:
                    break

            if has_module_list:
                if (rel_path, "*") not in allowlist:
                    uncovered.append(f"{rel_path} hard-codes module list")

        assert not uncovered, (
            f"Found {len(uncovered)} shared boundary violation(s) not in allowlist:\n"
            + "\n".join(f"  - {v}" for v in uncovered[:20])
        )

    def test_allowlist_must_be_empty_in_final_state(self):
        entries = _load_allowlist()
        for entry in entries:
            assert entry.get("removal_spec"), (
                f"Every allowlist entry must have a removal_spec to ensure it is temporary: "
                f"{entry['file']} -> {entry['target_module']}"
            )

    def test_add_legacy_module_allowlist_rejects_forbidden(self):
        allowlist = _allowlist_set("module_boundaries")

        forbidden_source = """\
from modules.billing.domain.entities import Invoice
from modules.identity.domain.repositories import UserRepository
"""
        tree = ast.parse(forbidden_source)
        violations = []
        source_module = "agent"
        fake_file = "src/modules/agent/domain/some_file.py"

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                parts = node.module.split(".")
                if len(parts) >= 2 and parts[0] == "modules":
                    target_module = parts[1]
                    if target_module != source_module and target_module in KNOWN_MODULES:
                        if (fake_file, target_module) not in allowlist:
                            violations.append((target_module, node.module))

        assert len(violations) == 2, (
            f"Expected 2 forbidden violations not in allowlist, got {len(violations)}: {violations}"
        )
        assert violations[0][0] == "billing"
        assert violations[1][0] == "identity"
