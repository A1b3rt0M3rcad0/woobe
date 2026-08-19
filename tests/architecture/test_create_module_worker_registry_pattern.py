"""Architecture tests for spec 062 — create module worker registry pattern."""
import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
AGENT_WORKERS = ROOT / "src" / "modules" / "agent" / "infra" / "workers"


def test_create_module_worker_registry_pattern_success():
    """Verify agent module exposes a WorkerRegistryProtocol-conformant registry."""
    registry_file = AGENT_WORKERS / "registry.py"
    assert registry_file.exists(), "src/modules/agent/infra/workers/registry.py must exist"

    from modules.agent.composition.worker_runtime.registry import AgentWorkerRegistry
    from shared.workers.contracts import WorkerRegistryProtocol, WorkerProtocol

    assert isinstance(AgentWorkerRegistry(), WorkerRegistryProtocol)

    class _FakeWorker:
        ran = False

        async def run(self) -> None:
            _FakeWorker.ran = True

    assert isinstance(_FakeWorker(), WorkerProtocol)

    registry = AgentWorkerRegistry()
    registry.register(_FakeWorker())
    workers = registry.iter_workers()
    assert len(workers) == 1
    assert isinstance(workers[0], WorkerProtocol)


def test_create_module_worker_registry_pattern_rejects_forbidden_dependency():
    """Verify agent worker registry does not import other module internals."""
    registry_file = AGENT_WORKERS / "registry.py"
    source = registry_file.read_text(encoding="utf-8")
    tree = ast.parse(source)

    forbidden_modules = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module.startswith("modules.") and not node.module.startswith("modules.agent"):
                forbidden_modules.append(node.module)
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("modules.") and not alias.name.startswith("modules.agent"):
                    forbidden_modules.append(alias.name)

    assert forbidden_modules == [], (
        f"Agent worker registry imports other module internals: {forbidden_modules}"
    )


def test_create_module_worker_registry_pattern_keeps_legacy_compatibility():
    """Verify the registry pattern is protocol-compatible and extensible."""
    from modules.agent.composition.worker_runtime.registry import AgentWorkerRegistry
    from shared.workers.contracts import WorkerRegistryProtocol

    registry = AgentWorkerRegistry()
    assert hasattr(registry, "iter_workers")
    assert hasattr(registry, "register")

    workers = registry.iter_workers()
    assert isinstance(workers, list)
    assert isinstance(registry, WorkerRegistryProtocol)
