"""Architecture tests for spec 061 — remove domain worker implementation from src/workers."""
import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC_WORKERS = ROOT / "src" / "workers"


def test_remove_domain_worker_implementation_from_src_workers_success():
    """Verify src/workers/ contains no domain event handlers or business routing."""
    dispatcher = SRC_WORKERS / "dispatcher.py"
    assert dispatcher.exists()

    source = dispatcher.read_text(encoding="utf-8")
    tree = ast.parse(source)

    function_names = [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]

    domain_handlers = [
        name for name in function_names
        if name.startswith("handle_") or name == "build_dispatcher"
    ]
    assert domain_handlers == [], (
        f"src/workers/dispatcher.py still contains domain handlers: {domain_handlers}"
    )

    runner = SRC_WORKERS / "runner.py"
    assert runner.exists()
    runner_source = runner.read_text(encoding="utf-8")
    assert "AskJobWorker" not in runner_source, (
        "src/workers/runner.py still references AskJobWorker"
    )
    assert "build_dispatcher" not in runner_source, (
        "src/workers/runner.py still references build_dispatcher"
    )


def test_remove_domain_worker_implementation_from_src_workers_rejects_forbidden_dependency():
    """Verify no src/workers/ file imports module internals."""
    violations = []

    for py_file in SRC_WORKERS.glob("*.py"):
        if py_file.name == "__init__.py":
            continue
        source = py_file.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith("modules."):
                    violations.append(f"{py_file.name}: {node.module}")
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("modules."):
                        violations.append(f"{py_file.name}: {alias.name}")

    assert violations == [], (
        f"src/workers/ files import module internals: {violations}"
    )


def test_remove_domain_worker_implementation_from_src_workers_keeps_legacy_compatibility():
    """Verify the deprecated shim emits warnings and delegates to shared runner."""
    runner = SRC_WORKERS / "runner.py"
    source = runner.read_text(encoding="utf-8")

    assert "DeprecationWarning" in source or "deprecated" in source.lower(), (
        "src/workers/runner.py should emit deprecation warning"
    )
    assert "WorkerRunner" in source, (
        "src/workers/runner.py should delegate to shared.workers.runner.WorkerRunner"
    )

    dispatcher = SRC_WORKERS / "dispatcher.py"
    dispatcher_source = dispatcher.read_text(encoding="utf-8")
    assert "deprecated" in dispatcher_source.lower(), (
        "src/workers/dispatcher.py should indicate deprecation"
    )
