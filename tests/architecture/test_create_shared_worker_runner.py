"""Architecture tests for spec 054 — create shared worker runner."""
import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]


def test_create_shared_worker_runner_success():
    """Verify WorkerRunner exists with run_once and run_loop methods."""
    from shared.workers.runner import WorkerRunner

    assert hasattr(WorkerRunner, "run_once")
    assert hasattr(WorkerRunner, "run_loop")

    runner = WorkerRunner(workers=[])
    assert runner._workers == []


def test_create_shared_worker_runner_rejects_forbidden_dependency():
    """Verify runner.py does not import any module internals."""
    source_file = ROOT / "src" / "shared" / "workers" / "runner.py"
    source = source_file.read_text(encoding="utf-8")
    tree = ast.parse(source)

    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if "modules." in node.module:
                violations.append(node.module)

    assert violations == [], f"Shared worker runner imports module internals: {violations}"


def test_create_shared_worker_runner_accepts_worker_protocol():
    """Verify WorkerRunner accepts WorkerProtocol instances."""
    from shared.workers.runner import WorkerRunner
    import inspect

    init_sig = inspect.signature(WorkerRunner.__init__)
    params = list(init_sig.parameters.keys())
    assert "workers" in params
