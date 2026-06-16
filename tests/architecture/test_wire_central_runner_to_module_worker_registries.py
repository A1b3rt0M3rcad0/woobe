"""Architecture tests for spec 063 — wire central runner to module worker registries."""
import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
SHARED_WORKERS = ROOT / "src" / "shared" / "workers"


def test_wire_central_runner_to_module_worker_registries_success():
    """Verify WorkerRunner.from_registries loads workers from registries."""
    from shared.workers.runner import WorkerRunner
    from shared.workers.contracts import WorkerProtocol, WorkerRegistryProtocol
    from modules.agent.infra.workers.registry import AgentWorkerRegistry

    class _FakeWorker:
        ran = False

        async def run(self) -> None:
            _FakeWorker.ran = True

    assert isinstance(_FakeWorker(), WorkerProtocol)

    registry = AgentWorkerRegistry(workers=[_FakeWorker(), _FakeWorker()])
    assert isinstance(registry, WorkerRegistryProtocol)

    runner = WorkerRunner.from_registries(registries=[registry])
    assert len(runner._workers) == 2
    assert all(isinstance(w, WorkerProtocol) for w in runner._workers)

    empty_runner = WorkerRunner.from_registries(registries=[])
    assert len(empty_runner._workers) == 0


def test_wire_central_runner_to_module_worker_registries_rejects_forbidden_dependency():
    """Verify shared runner does not import module internals."""
    runner_file = SHARED_WORKERS / "runner.py"
    source = runner_file.read_text(encoding="utf-8")
    tree = ast.parse(source)

    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module.startswith("modules."):
                violations.append(node.module)
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("modules."):
                    violations.append(alias.name)

    assert violations == [], (
        f"shared/workers/runner.py imports module internals: {violations}"
    )


def test_wire_central_runner_to_module_worker_registries_keeps_legacy_compatibility():
    """Verify WorkerRunner still works with direct worker list (pre-registry API)."""
    from shared.workers.runner import WorkerRunner
    from shared.workers.contracts import WorkerProtocol

    class _FakeWorker:
        async def run(self) -> None:
            pass

    assert isinstance(_FakeWorker(), WorkerProtocol)

    runner = WorkerRunner(workers=[_FakeWorker()])
    assert hasattr(runner, "run_once")
    assert hasattr(runner, "run_loop")
    assert hasattr(runner, "from_registries")
    assert len(runner._workers) == 1
