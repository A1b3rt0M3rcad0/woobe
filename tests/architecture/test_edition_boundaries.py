from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND_CORE_ROOTS = (ROOT / "src/modules", ROOT / "src/shared")
FRONTEND_ROOT = ROOT / "web/src"
FRONTEND_COMPOSITION_ROOT = FRONTEND_ROOT / "app"
FRONTEND_EDITION_ROOT = FRONTEND_ROOT / "editions"
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


def _is_edition_import(module_name: str) -> bool:
    return module_name == "editions" or module_name.startswith("editions.") or module_name.startswith("src.editions.")


def test_backend_community_core_does_not_import_edition_packages() -> None:
    violations: list[str] = []
    for root in BACKEND_CORE_ROOTS:
        for path in root.rglob("*.py"):
            for module_name in _backend_imports(path):
                if _is_edition_import(module_name):
                    violations.append(f"{path.relative_to(ROOT).as_posix()} -> {module_name}")

    assert not violations, (
        "Community/Core backend code must not import edition-specific packages. "
        "Edition composition belongs in application composition roots.\n"
        + "\n".join(f"  - {violation}" for violation in violations)
    )


def test_frontend_community_core_does_not_import_edition_packages() -> None:
    violations: list[str] = []
    for path in FRONTEND_ROOT.rglob("*"):
        if path.suffix not in {".ts", ".tsx", ".js", ".jsx"}:
            continue
        if path.is_relative_to(FRONTEND_EDITION_ROOT):
            continue
        if path.is_relative_to(FRONTEND_COMPOSITION_ROOT):
            continue

        source = path.read_text(encoding="utf-8")
        for module_name in FRONTEND_IMPORT_PATTERN.findall(source):
            if module_name.startswith("@/editions/") or "/editions/" in module_name:
                violations.append(f"{path.relative_to(ROOT).as_posix()} -> {module_name}")

    assert not violations, (
        "Community/Core frontend code must not import edition-specific UI. "
        "Edition composition belongs under web/src/app or inside the edition itself.\n"
        + "\n".join(f"  - {violation}" for violation in violations)
    )
