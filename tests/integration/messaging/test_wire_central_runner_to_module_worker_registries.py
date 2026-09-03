from unittest.mock import MagicMock

from woobe_workers.composition.registries import build_registries, discover_module_entries
from woobe_workers.consumers.agent.run_recovery_worker import AgentRunRecoveryWorker
from woobe_workers.consumers.agent.vector_snapshot_worker import VectorSnapshotWorker
from shared.infra.rabbitmq import RabbitMQManager


def test_agent_registry_includes_vector_snapshot_and_run_recovery_workers():
    entries = [entry for entry in discover_module_entries() if entry.module_name == "agent"]
    registries = build_registries(
        entries,
        engine=MagicMock(),
        settings=MagicMock(),
        rabbitmq_manager=MagicMock(spec=RabbitMQManager),
    )
    assert len(registries) == 1
    workers = registries[0].iter_workers()
    assert len(workers) == 4
    assert any(isinstance(worker, VectorSnapshotWorker) for worker in workers)
    assert any(isinstance(worker, AgentRunRecoveryWorker) for worker in workers)
