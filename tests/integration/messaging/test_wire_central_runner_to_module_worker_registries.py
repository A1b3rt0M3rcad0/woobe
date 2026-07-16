from unittest.mock import MagicMock

from shared.infra.rabbitmq import RabbitMQManager
from shared.workers.discovery import build_registries, discover_module_entries


def test_agent_registry_includes_vector_snapshot_worker():
    entries = [entry for entry in discover_module_entries() if entry.module_name == "agent"]
    registries = build_registries(
        entries,
        engine=MagicMock(),
        settings=MagicMock(),
        rabbitmq_manager=MagicMock(spec=RabbitMQManager),
    )
    assert len(registries) == 1
    assert len(registries[0].iter_workers()) == 3
