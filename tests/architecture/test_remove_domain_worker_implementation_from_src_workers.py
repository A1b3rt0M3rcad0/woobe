"""Architecture tests for the worker package cutover.

The legacy root src/workers package stays removed. Process bootstrap lives in
packages/woobe-workers, while concrete domain workers remain owned by Core
modules under modules/<module>/infra/workers.
"""
import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
CORE_SRC = ROOT / "packages" / "woobe-core" / "src"
API_SRC = ROOT / "packages" / "woobe-api" / "src"
WORKER_SRC = ROOT / "packages" / "woobe-workers" / "src"
PRODUCTION_ROOTS = (CORE_SRC, API_SRC, WORKER_SRC)
LEGACY_SRC_WORKERS = ROOT / "src" / "workers"


def test_legacy_root_worker_package_is_removed():
    assert not LEGACY_SRC_WORKERS.exists(), (
        "Legacy src/workers must remain removed. Process bootstrap belongs to "
        "packages/woobe-workers and concrete workers belong to woobe-core modules."
    )


def test_worker_process_package_exists():
    assert WORKER_SRC.is_dir(), "packages/woobe-workers/src must exist"
    assert (WORKER_SRC / "worker_main.py").is_file(), (
        "woobe-workers must own the worker process composition root"
    )


def test_no_production_package_imports_removed_workers_namespace():
    violations = []
    for base in PRODUCTION_ROOTS:
        if not base.is_dir():
            continue
        for py_file in base.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            try:
                tree = ast.parse(
                    py_file.read_text(encoding="utf-8", errors="replace")
                )
            except (OSError, SyntaxError):
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    if node.module == "workers" or node.module.startswith("workers."):
                        violations.append(
                            f"{py_file.relative_to(ROOT)}: from {node.module}"
                        )
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name == "workers" or alias.name.startswith("workers."):
                            violations.append(
                                f"{py_file.relative_to(ROOT)}: import {alias.name}"
                            )

    assert violations == [], (
        f"Live imports from removed workers namespace found: {violations}"
    )


def test_shared_worker_runner_remains_in_core():
    shared_runner = CORE_SRC / "shared" / "workers" / "runner.py"
    assert shared_runner.is_file(), (
        "shared.workers.runner must remain available from woobe-core"
    )
