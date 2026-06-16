"""Tests for spec 090 — create billing worker structure."""
import ast
import inspect
from pathlib import Path

from modules.billing.infra.workers.registry import BillingWorkerRegistry
from shared.workers.contracts import WorkerRegistryProtocol


class TestBillingWorkerStructure:
    """Verify the billing worker structure exists."""

    def test_workers_directory_exists(self):
        path = Path("src/modules/billing/infra/workers")
        assert path.exists()
        assert path.is_dir()

    def test_init_file_exists(self):
        path = Path("src/modules/billing/infra/workers/__init__.py")
        assert path.exists()

    def test_registry_file_exists(self):
        path = Path("src/modules/billing/infra/workers/registry.py")
        assert path.exists()

    def test_registry_class_exists(self):
        assert BillingWorkerRegistry is not None

    def test_registry_satisfies_protocol(self):
        registry = BillingWorkerRegistry()
        assert isinstance(registry, WorkerRegistryProtocol)

    def test_registry_has_iter_workers(self):
        registry = BillingWorkerRegistry()
        assert hasattr(registry, "iter_workers")
        assert callable(registry.iter_workers)

    def test_registry_has_register(self):
        registry = BillingWorkerRegistry()
        assert hasattr(registry, "register")
        assert callable(registry.register)


class TestBillingWorkerStructureRejectsForbiddenDependency:
    """Verify billing does not import agent internals."""

    def test_no_agent_imports_in_registry(self):
        import modules.billing.infra.workers.registry as mod

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
        import modules.billing.infra.workers as mod

        source = inspect.getsource(mod)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module:
                    assert "modules.agent" not in node.module, (
                        f"Forbidden import from agent: {node.module}"
                    )
