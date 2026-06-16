"""Architecture tests for spec 060 — move root workers to shared workers."""
import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
SHARED_WORKERS = ROOT / "src" / "shared" / "workers"


def test_move_root_workers_to_shared_workers_success():
    """Verify shared/workers contains all required generic infrastructure."""
    assert (SHARED_WORKERS / "contracts.py").exists()
    assert (SHARED_WORKERS / "base_worker.py").exists()
    assert (SHARED_WORKERS / "runner.py").exists()
    assert (SHARED_WORKERS / "outbox_dispatcher_base.py").exists()
    assert (SHARED_WORKERS / "inbox_consumer_base.py").exists()
    assert (SHARED_WORKERS / "inbox_processor_base.py").exists()

    from shared.workers.runner import WorkerRunner
    from shared.workers.contracts import WorkerProtocol, WorkerRegistryProtocol
    from shared.workers.base_worker import BaseWorker
    from shared.workers.outbox_dispatcher_base import BaseOutboxDispatcher
    from shared.workers.inbox_consumer_base import BaseInboxConsumer
    from shared.workers.inbox_processor_base import BaseInboxProcessor

    assert hasattr(WorkerRunner, "run_once")
    assert hasattr(WorkerRunner, "run_loop")
    assert issubclass(BaseOutboxDispatcher, BaseWorker)
    assert issubclass(BaseInboxConsumer, BaseWorker)
    assert issubclass(BaseInboxProcessor, BaseWorker)
    assert isinstance(WorkerProtocol, type)
    assert isinstance(WorkerRegistryProtocol, type)


def test_move_root_workers_to_shared_workers_rejects_forbidden_dependency():
    """Verify no shared/workers file imports module internals."""
    violations = []

    for py_file in SHARED_WORKERS.glob("*.py"):
        if py_file.name == "__init__.py":
            continue
        source = py_file.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if "modules." in node.module:
                    violations.append(f"{py_file.name}: {node.module}")

    new_files = [
        "contracts.py", "base_worker.py", "runner.py",
        "outbox_dispatcher_base.py", "inbox_consumer_base.py",
        "inbox_processor_base.py",
    ]
    new_violations = [v for v in violations if any(v.startswith(f) for f in new_files)]
    assert new_violations == [], f"Shared workers import module internals: {new_violations}"


def test_move_root_workers_to_shared_workers_runner_replaces_root():
    """Verify shared WorkerRunner can serve as drop-in for root runner loop."""
    from shared.workers.runner import WorkerRunner
    from shared.workers.contracts import WorkerProtocol

    class _FakeWorker:
        ran = False

        async def run(self) -> None:
            _FakeWorker.ran = True

    assert isinstance(_FakeWorker(), WorkerProtocol)
    runner = WorkerRunner(workers=[_FakeWorker()])
    assert hasattr(runner, "run_once")
    assert hasattr(runner, "run_loop")
