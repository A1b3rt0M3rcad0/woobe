"""Architecture tests for spec 061 — remove domain worker implementation from src/workers.

Updated for spec 152: src/workers/ has been fully removed. Verifies that no
concrete workers or domain implementations exist at the root workers path.
"""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC_WORKERS = ROOT / "src" / "workers"


def test_remove_domain_worker_implementation_from_src_workers_success():
    """Verify src/workers/ directory no longer exists (fully removed in spec 152)."""
    assert not SRC_WORKERS.exists(), (
        "src/workers/ must not exist after spec 152 removal. "
        "Concrete workers belong in src/modules/<module>/infra/workers/."
    )


def test_remove_domain_worker_implementation_from_src_workers_rejects_forbidden_dependency():
    """Verify no module imports from the (now removed) workers package."""
    import ast

    violations = []
    for py_file in pathlib.Path("src").rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        try:
            source = py_file.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module == "workers" or node.module.startswith("workers."):
                    violations.append(f"{py_file}: from {node.module}")
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "workers" or alias.name.startswith("workers."):
                        violations.append(f"{py_file}: import {alias.name}")

    assert violations == [], (
        f"Live imports from removed workers package found: {violations}"
    )


def test_remove_domain_worker_implementation_from_src_workers_keeps_legacy_compatibility():
    """Verify shared.workers.runner is still available as the central runner."""
    shared_runner = ROOT / "src" / "shared" / "workers" / "runner.py"
    assert shared_runner.is_file(), (
        "shared.workers.runner must exist after src/workers removal"
    )
