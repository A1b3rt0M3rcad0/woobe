"""Architecture tests for spec 055 — create shared worker registry contract."""
import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]


def test_create_shared_worker_registry_contract_success():
    """Verify WorkerRegistryProtocol exists with iter_workers method."""
    from shared.workers.contracts import WorkerProtocol, WorkerRegistryProtocol

    assert hasattr(WorkerRegistryProtocol, "iter_workers")

    class _FakeRegistry:
        def iter_workers(self) -> list[WorkerProtocol]:
            return []

    assert isinstance(_FakeRegistry(), WorkerRegistryProtocol)


def test_create_shared_worker_registry_contract_rejects_forbidden_dependency():
    """Verify contracts.py does not import any module internals."""
    source_file = ROOT / "src" / "shared" / "workers" / "contracts.py"
    source = source_file.read_text(encoding="utf-8")
    tree = ast.parse(source)

    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if "modules." in node.module:
                violations.append(node.module)

    assert violations == [], f"Shared contracts imports module internals: {violations}"


def test_create_shared_worker_registry_contract_is_runtime_checkable():
    """Verify WorkerRegistryProtocol is runtime-checkable."""
    from shared.workers.contracts import WorkerRegistryProtocol

    assert isinstance(WorkerRegistryProtocol, type)

    class _NotARegistry:
        pass

    assert not isinstance(_NotARegistry(), WorkerRegistryProtocol)
