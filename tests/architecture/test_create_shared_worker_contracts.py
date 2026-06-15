"""Architecture tests for spec 050 — create shared worker contracts."""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]


def test_create_shared_worker_contracts_success():
    """Verify worker contracts exist in shared/workers."""
    from shared.workers.contracts import WorkerProtocol, WorkerRegistryProtocol

    assert hasattr(WorkerProtocol, "run")
    assert hasattr(WorkerRegistryProtocol, "iter_workers")

    from shared.workers.base_worker import BaseWorker
    assert hasattr(BaseWorker, "run")


def test_create_shared_worker_contracts_rejects_forbidden_dependency():
    """Verify shared/workers/contracts.py does not import any module internals."""
    import ast

    contracts_file = ROOT / "src" / "shared" / "workers" / "contracts.py"
    source = contracts_file.read_text(encoding="utf-8")
    tree = ast.parse(source)

    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if "modules." in node.module:
                violations.append(node.module)

    assert violations == [], f"Shared worker contracts imports module internals: {violations}"


def test_shared_worker_contracts_protocol_runtime_checkable():
    """Verify protocols are runtime_checkable for isinstance checks."""
    from shared.workers.contracts import WorkerProtocol, WorkerRegistryProtocol

    class _FakeWorker:
        async def run(self) -> None: ...

    class _FakeRegistry:
        def iter_workers(self) -> list:
            return []

    assert isinstance(_FakeWorker(), WorkerProtocol)
    assert isinstance(_FakeRegistry(), WorkerRegistryProtocol)
