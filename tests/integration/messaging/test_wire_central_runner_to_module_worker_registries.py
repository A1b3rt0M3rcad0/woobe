"""Spec 095: Wire central runner to module worker registries."""

from __future__ import annotations

from unittest.mock import MagicMock

from shared.infra.rabbitmq import RabbitMQManager
from shared.workers.contracts import WorkerRegistryProtocol
from shared.workers.discovery import (
    MODULE_WORKER_REGISTRIES,
    ModuleWorkerEntry,
    build_registries,
    discover_module_entries,
)
from shared.workers.runner import WorkerRunner


class TestDiscovery:
    """discover_module_entries must find all module registries."""

    def test_discover_returns_all_modules(self):
        entries = discover_module_entries()
        found = {e.module_name for e in entries}
        assert found == set(MODULE_WORKER_REGISTRIES), f"Missing: {set(MODULE_WORKER_REGISTRIES) - found}"

    def test_each_entry_has_registry_class(self):
        entries = discover_module_entries()
        for entry in entries:
            assert issubclass(entry.registry_class, WorkerRegistryProtocol) or hasattr(entry.registry_class, "iter_workers")

    def test_each_entry_has_callable_register(self):
        entries = discover_module_entries()
        for entry in entries:
            assert callable(entry.register_func)

    def test_module_worker_entry_is_domain_agnostic(self):
        entries = discover_module_entries()
        for entry in entries:
            assert isinstance(entry.module_name, str)
            assert isinstance(entry.registry_class, type)
            assert callable(entry.register_func)


class TestBuildRegistries:
    """build_registries must produce WorkerRegistryProtocol instances."""

    def test_build_all_registries_returns_list(self):
        entries = discover_module_entries()
        mock_engine = MagicMock()
        registries = build_registries(entries, engine=mock_engine, settings=MagicMock())
        assert len(registries) == len(MODULE_WORKER_REGISTRIES)

    def test_each_registry_conforms_to_protocol(self):
        entries = discover_module_entries()
        mock_engine = MagicMock()
        registries = build_registries(entries, engine=mock_engine, settings=MagicMock())
        for registry in registries:
            assert isinstance(registry, WorkerRegistryProtocol)

    def test_with_rabbitmq_agent_has_two_workers(self):
        entries = discover_module_entries()
        mock_engine = MagicMock()
        mock_rmq = MagicMock(spec=RabbitMQManager)
        registries = build_registries(
            [e for e in entries if e.module_name == "agent"],
            engine=mock_engine,
            settings=MagicMock(),
            rabbitmq_manager=mock_rmq,
        )
        assert len(registries) == 1
        agent_workers = registries[0].iter_workers()
        assert len(agent_workers) == 2

    def test_with_rabbitmq_billing_has_one_worker(self):
        entries = discover_module_entries()
        mock_engine = MagicMock()
        mock_rmq = MagicMock(spec=RabbitMQManager)
        registries = build_registries(
            [e for e in entries if e.module_name == "billing"],
            engine=mock_engine,
            settings=MagicMock(),
            rabbitmq_manager=mock_rmq,
        )
        assert len(registries) == 1
        billing_workers = registries[0].iter_workers()
        assert len(billing_workers) == 1

    def test_with_rabbitmq_core_has_one_worker(self):
        entries = discover_module_entries()
        mock_engine = MagicMock()
        mock_rmq = MagicMock(spec=RabbitMQManager)
        registries = build_registries(
            [e for e in entries if e.module_name == "core"],
            engine=mock_engine,
            settings=MagicMock(),
            rabbitmq_manager=mock_rmq,
        )
        assert len(registries) == 1
        core_workers = registries[0].iter_workers()
        assert len(core_workers) == 1

    def test_with_rabbitmq_identity_has_one_worker(self):
        entries = discover_module_entries()
        mock_engine = MagicMock()
        mock_rmq = MagicMock(spec=RabbitMQManager)
        registries = build_registries(
            [e for e in entries if e.module_name == "identity"],
            engine=mock_engine,
            settings=MagicMock(),
            rabbitmq_manager=mock_rmq,
        )
        assert len(registries) == 1
        identity_workers = registries[0].iter_workers()
        assert len(identity_workers) == 1

    def test_stub_modules_have_zero_workers(self):
        entries = discover_module_entries()
        mock_engine = MagicMock()
        for stub in ("metering", "observability", "tools"):
            stub_entries = [e for e in entries if e.module_name == stub]
            if not stub_entries:
                continue
            registries = build_registries(stub_entries, engine=mock_engine, settings=MagicMock())
            assert len(registries[0].iter_workers()) == 0

    def test_without_rabbitmq_all_modules_are_safe(self):
        entries = discover_module_entries()
        mock_engine = MagicMock()
        registries = build_registries(entries, engine=mock_engine, settings=MagicMock(), rabbitmq_manager=None)
        for registry in registries:
            assert isinstance(registry, WorkerRegistryProtocol)

    def test_without_rabbitmq_no_workers_are_registered(self):
        entries = discover_module_entries()
        mock_engine = MagicMock()
        registries = build_registries(entries, engine=mock_engine, settings=MagicMock(), rabbitmq_manager=None)
        for registry in registries:
            assert len(registry.iter_workers()) == 0


class TestWorkerRunnerWiring:
    """WorkerRunner.from_registries must wire discovered registries correctly."""

    def test_from_registries_creates_runner(self):
        entries = discover_module_entries()
        mock_engine = MagicMock()
        registries = build_registries(entries, engine=mock_engine, settings=MagicMock())
        runner = WorkerRunner.from_registries(registries)
        assert isinstance(runner, WorkerRunner)

    def test_run_once_does_not_raise_with_mock_workers(self):
        mock_registry = MagicMock(spec=WorkerRegistryProtocol)
        mock_worker = MagicMock()
        mock_worker.run = MagicMock()
        mock_registry.iter_workers.return_value = [mock_worker]
        runner = WorkerRunner.from_registries([mock_registry])
        import asyncio
        asyncio.run(runner.run_once())
        mock_worker.run.assert_called_once()

    def test_runner_contains_workers_from_all_registries(self):
        entries = discover_module_entries()
        mock_engine = MagicMock()
        mock_rmq = MagicMock(spec=RabbitMQManager)
        registries = build_registries(entries, engine=mock_engine, settings=MagicMock(), rabbitmq_manager=mock_rmq)
        runner = WorkerRunner.from_registries(registries)
        total_workers = sum(len(r.iter_workers()) for r in registries)
        assert len(runner._workers) == total_workers


class TestModuleWorkerEntry:
    """ModuleWorkerEntry must be constructable manually."""

    def test_manual_entry_construction(self):
        entry = ModuleWorkerEntry(
            module_name="test",
            registry_class=MagicMock,
            register_func=lambda *a, **kw: None,
        )
        assert entry.module_name == "test"
        assert entry.registry_class is MagicMock
        assert callable(entry.register_func)
