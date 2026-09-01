"""Tests for spec 091 — create metering worker structure."""
import ast
import inspect
from pathlib import Path

from modules.metering.infra.workers.registry import MeteringWorkerRegistry
from shared.workers.contracts import WorkerRegistryProtocol


ROOT = Path(__file__).resolve().parents[2]
WORKERS_DIR = (
    ROOT
    / "packages"
    / "woobe-core"
    / "src"
    / "modules"
    / "metering"
    / "infra"
    / "workers"
)


class TestMeteringWorkerStructure:
    """Verify the metering worker structure exists."""

    def test_workers_directory_exists(self):
        assert WORKERS_DIR.exists()
        assert WORKERS_DIR.is_dir()

    def test_init_file_exists(self):
        path = WORKERS_DIR / "__init__.py"
        assert path.exists()

    def test_registry_file_exists(self):
        path = WORKERS_DIR / "registry.py"
        assert path.exists()

    def test_registry_class_exists(self):
        assert MeteringWorkerRegistry is not None

    def test_registry_satisfies_protocol(self):
        registry = MeteringWorkerRegistry()
        assert isinstance(registry, WorkerRegistryProtocol)

    def test_registry_has_iter_workers(self):
        registry = MeteringWorkerRegistry()
        assert hasattr(registry, "iter_workers")
        assert callable(registry.iter_workers)

    def test_registry_has_register(self):
        registry = MeteringWorkerRegistry()
        assert hasattr(registry, "register")
        assert callable(registry.register)


class TestMeteringWorkerStructureRejectsForbiddenDependency:
    """Verify metering does not import agent internals."""

    def test_no_agent_imports_in_registry(self):
        import modules.metering.infra.workers.registry as mod

        source = inspect.getsource(mod)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module:
                    assert "modules.agent" not in node.module, (
                        f"Forbidden import from agent: {node.module}"
                    )
                    assert "modules.ai" not in node.module, (
                        f"Forbidden import from ai: {node.module}"
                    )
                    assert "modules.knowledge" not in node.module, (
                        f"Forbidden import from knowledge: {node.module}"
                    )
                    assert "modules.runtime" not in node.module, (
                        f"Forbidden import from runtime: {node.module}"
                    )

    def test_no_agent_imports_in_init(self):
        import modules.metering.infra.workers as mod

        source = inspect.getsource(mod)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module:
                    assert "modules.agent" not in node.module, (
                        f"Forbidden import from agent: {node.module}"
                    )