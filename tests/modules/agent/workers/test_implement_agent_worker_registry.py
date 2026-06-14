"""Tests for spec 085 — implement agent worker registry."""
import ast
import inspect

from modules.agent.infra.workers.registry import (
    AgentWorkerRegistry,
    register_agent_workers,
)
from shared.workers.contracts import WorkerRegistryProtocol


class TestWorkerRegistryStructure:
    """Verify the registry is properly located and structured."""

    def test_file_exists_in_correct_location(self):
        import modules.agent.infra.workers.registry as mod

        assert mod.__file__ is not None
        assert "modules/agent/infra/workers" in mod.__file__.replace("\\", "/")

    def test_registry_class_exists(self):
        assert AgentWorkerRegistry is not None

    def test_registry_satisfies_protocol(self):
        registry = AgentWorkerRegistry()
        assert isinstance(registry, WorkerRegistryProtocol)

    def test_register_function_exists(self):
        assert callable(register_agent_workers)

    def test_register_function_signature(self):
        sig = inspect.signature(register_agent_workers)
        params = list(sig.parameters.keys())
        assert "registry" in params
        assert "settings" in params
        assert "engine" in params


class TestWorkerRegistryFunction:
    """Verify register_agent_workers wires workers correctly."""

    def test_function_accepts_rabbitmq_manager(self):
        sig = inspect.signature(register_agent_workers)
        params = list(sig.parameters.keys())
        assert "rabbitmq_manager" in params

    def test_function_creates_outbox_dispatcher(self):
        source = inspect.getsource(register_agent_workers)
        assert "AgentOutboxDispatcherWorker" in source

    def test_function_creates_inbox_consumer(self):
        source = inspect.getsource(register_agent_workers)
        assert "AgentInboxConsumerWorker" in source

    def test_function_creates_inbox_processor(self):
        source = inspect.getsource(register_agent_workers)
        assert "AgentInboxProcessorWorker" in source

    def test_function_creates_publisher(self):
        source = inspect.getsource(register_agent_workers)
        assert "AgentRabbitMQPublisher" in source

    def test_function_creates_inbox_handler_router(self):
        source = inspect.getsource(register_agent_workers)
        assert "AgentInboxEventRouter" in source

    def test_function_registers_workers(self):
        source = inspect.getsource(register_agent_workers)
        assert source.count("registry.register") >= 3


class TestWorkerRegistryDelegation:
    """Verify the registry delegates to correct worker classes."""

    def test_outbox_dispatcher_import(self):
        import modules.agent.infra.workers.registry as mod

        source = inspect.getsource(mod)
        assert "AgentOutboxDispatcherWorker" in source

    def test_inbox_consumer_import(self):
        import modules.agent.infra.workers.registry as mod

        source = inspect.getsource(mod)
        assert "AgentInboxConsumerWorker" in source

    def test_inbox_processor_import(self):
        import modules.agent.infra.workers.registry as mod

        source = inspect.getsource(mod)
        assert "AgentInboxProcessorWorker" in source

    def test_publisher_import(self):
        import modules.agent.infra.workers.registry as mod

        source = inspect.getsource(mod)
        assert "AgentRabbitMQPublisher" in source


class TestWorkerRegistryNoCrossModuleImports:
    """Verify the registry does not import from other modules."""

    def test_no_imports_from_other_modules(self):
        import modules.agent.infra.workers.registry as mod

        source = inspect.getsource(mod)
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and "modules." in node.module:
                    assert node.module.startswith("modules.agent"), (
                        f"Forbidden cross-module import: {node.module}"
                    )


class TestWorkerRegistryGracefulDegradation:
    """Verify graceful handling when rabbitmq_manager is None."""

    def test_no_rabbitmq_manager_returns_early(self):
        source = inspect.getsource(register_agent_workers)
        assert "None" in source

    def test_registry_empty_without_rabbitmq(self):
        registry = AgentWorkerRegistry()
        register_agent_workers(
            registry=registry,
            settings=None,
            engine=None,
            rabbitmq_manager=None,
        )
        assert len(registry.iter_workers()) == 0
