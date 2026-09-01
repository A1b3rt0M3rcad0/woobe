import ast
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CORE_SRC = PROJECT_ROOT / "packages" / "woobe-core" / "src"
SRC_SHARED = CORE_SRC / "shared"
SRC_MODULES = CORE_SRC / "modules"
ALLOWLIST_FILE = Path(__file__).resolve().parent / "legacy_import_allowlist.yaml"

KNOWN_MODULES = {
    d.name
    for d in SRC_MODULES.iterdir()
    if d.is_dir() and not d.name.startswith("_")
}


def _load_allowlist(scope: str) -> set[str]:
    if not ALLOWLIST_FILE.exists():
        return set()
    with open(ALLOWLIST_FILE, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    entries = data.get("entries") or []
    return {
        e["file"].replace("\\", "/")
        for e in entries
        if e.get("scope") == scope
    }


def _relative_posix(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def _extract_module_imports(file_path: Path) -> list[str]:
    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(file_path))
    except (SyntaxError, UnicodeDecodeError):
        return []

    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module.startswith("modules."):
                violations.append(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("modules."):
                    violations.append(alias.name)
    return violations


def _detect_dynamic_module_references(file_path: Path) -> list[str]:
    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(file_path))
    except (SyntaxError, UnicodeDecodeError):
        return []

    references = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value in KNOWN_MODULES:
                references.append(node.value)
        elif isinstance(node, ast.JoinedStr):
            for value in node.values:
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    if "modules." in value.value:
                        references.append(value.value)
    return references


class TestSharedBoundaries:
    def test_no_static_module_imports_in_shared(self):
        violations = []
        if not SRC_SHARED.exists():
            return

        for py_file in SRC_SHARED.rglob("*.py"):
            module_imports = _extract_module_imports(py_file)
            if module_imports:
                rel_path = _relative_posix(py_file)
                for imp in module_imports:
                    violations.append(f"{rel_path} imports {imp}")

        assert not violations, (
            "Shared layer must not statically import from modules.*:\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    def test_no_domain_logic_in_shared(self):
        if not SRC_SHARED.exists():
            return

        forbidden_patterns = []
        for py_file in SRC_SHARED.rglob("*.py"):
            try:
                source = py_file.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(py_file))
            except (SyntaxError, UnicodeDecodeError):
                continue

            rel_path = _relative_posix(py_file)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    class_name_lower = node.name.lower()
                    if any(
                        keyword in class_name_lower
                        for keyword in ("usecase", "use_case", "handler", "aggregate")
                    ):
                        infra_indicators = ("base", "abstract", "transactional", "generic")
                        if not any(ind in class_name_lower for ind in infra_indicators):
                            forbidden_patterns.append(
                                f"{rel_path}: class {node.name} (domain logic in shared)"
                            )

        assert not forbidden_patterns, (
            "Shared layer must not contain domain logic:\n"
            + "\n".join(f"  - {v}" for v in forbidden_patterns)
        )

    def test_dynamic_module_references_in_shared_are_allowlisted(self):
        allowlist = _load_allowlist("shared_boundaries")
        unlisted = []

        if not SRC_SHARED.exists():
            return

        for py_file in SRC_SHARED.rglob("*.py"):
            refs = _detect_dynamic_module_references(py_file)
            if refs:
                rel_path = _relative_posix(py_file)
                if rel_path not in allowlist:
                    unlisted.append(
                        f"{rel_path} contains dynamic module references: {refs[:5]}"
                    )

        assert not unlisted, (
            "Shared files with dynamic module references must be in allowlist:\n"
            + "\n".join(f"  - {v}" for v in unlisted)
        )

    def test_detects_forbidden_module_import_in_shared(self):
        forbidden_source = """\
from modules.ai.domain.entities import Agent
from modules.billing.infra.repositories import InvoiceRepository
"""
        tree = ast.parse(forbidden_source)
        violations = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith("modules."):
                    violations.append(node.module)

        assert len(violations) == 2, (
            f"Expected 2 violations from fixture, got {len(violations)}"
        )
