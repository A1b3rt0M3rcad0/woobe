from __future__ import annotations

import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CORE_MODULES = PROJECT_ROOT / "src" / "modules"
CLOUD_BILLING = PROJECT_ROOT / "src" / "editions" / "cloud" / "billing"


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    result: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            result.append(node.module)
        elif isinstance(node, ast.Import):
            result.extend(alias.name for alias in node.names)
    return result


def test_cloud_billing_has_no_community_compatibility_shim() -> None:
    assert not (CORE_MODULES / "billing.py").exists()
    assert not (CORE_MODULES / "billing").exists()


def test_cloud_billing_uses_only_canonical_billing_namespace() -> None:
    violations: list[str] = []
    for path in CLOUD_BILLING.rglob("*.py"):
        for imported in _imports(path):
            if imported == "modules.billing" or imported.startswith("modules.billing."):
                violations.append(f"{path.relative_to(PROJECT_ROOT)} -> {imported}")
    assert not violations, "Legacy Billing imports found:\n" + "\n".join(violations)
