from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE_ROOT = ROOT / "packages/woobe-core/src"
BACKEND_CORE_ROOTS = (CORE_ROOT / "modules", CORE_ROOT / "shared")
FRONTEND_ROOT = ROOT / "packages/woobe-frontend/src"
FRONTEND_IMPORT_PATTERN = re.compile(
    r"(?:from\s+|import\s*\(\s*|import\s+)[\"']([^\"']+)[\"']"
)


def _backend_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
        elif isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
    return imported


def _is_enterprise_import(module_name: str) -> bool:
    return (
        module_name == "editions.enterprise"
        or module_name.startswith("editions.enterprise.")
        or module_name == "woobe_ee"
        or module_name.startswith("woobe_ee.")
    )


def test_core_backend_does_not_import_enterprise_implementation() -> None:
    violations: list[str] = []
    for root in BACKEND_CORE_ROOTS:
        for path in root.rglob("*.py"):
            for module_name in _backend_imports(path):
                if _is_enterprise_import(module_name):
                    violations.append(f"{path.relative_to(ROOT).as_posix()} -> {module_name}")

    assert not violations, (
        "Woobe Core backend code must not import Enterprise implementation. "
        "Only the neutral Core integration contract under editions/contracts.py is allowed.\n"
        + "\n".join(f"  - {violation}" for violation in violations)
    )


def test_core_frontend_does_not_import_enterprise_implementation() -> None:
    violations: list[str] = []
    for path in FRONTEND_ROOT.rglob("*"):
        if path.suffix not in {".ts", ".tsx", ".js", ".jsx"}:
            continue
        source = path.read_text(encoding="utf-8")
        for module_name in FRONTEND_IMPORT_PATTERN.findall(source):
            if (
                module_name.startswith("@/enterprise/")
                or "/enterprise/" in module_name
                or "woobe-ee" in module_name
            ):
                violations.append(f"{path.relative_to(ROOT).as_posix()} -> {module_name}")

    assert not violations, (
        "Woobe Core frontend code must not import Enterprise implementation.\n"
        + "\n".join(f"  - {violation}" for violation in violations)
    )


def test_enterprise_package_is_not_part_of_core_runtime_source() -> None:
    ee = ROOT / "packages/woobe-ee"
    assert ee.is_dir()
    assert (ee / "README.md").is_file()
    assert not (ee / "src").exists()
    assert (ROOT / "LICENSE_EE.md").is_file()
