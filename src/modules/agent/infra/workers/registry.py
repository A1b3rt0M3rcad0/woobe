from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine

from modules.agent.infra.messaging.publishers import AgentRabbitMQPublisher
from modules.agent.infra.workers.ask_job_worker import AskJobWorker
from modules.agent.infra.workers.outbox_dispatcher import AgentOutboxDispatcherWorker
from modules.agent.infra.workers.vector_snapshot_worker import VectorSnapshotWorker
from shared.infra.rabbitmq import RabbitMQManager
from shared.workers.contracts import WorkerProtocol, WorkerRegistryProtocol


class AgentWorkerRegistry:
    def __init__(self, workers: list[WorkerProtocol] | None = None) -> None:
        self._workers: list[WorkerProtocol] = workers or []

    def register(self, worker: WorkerProtocol) -> None:
        self._workers.append(worker)

    def iter_workers(self) -> list[WorkerProtocol]:
        return list(self._workers)


def register_agent_workers(
    registry: AgentWorkerRegistry,
    settings: Any,
    engine: AsyncEngine,
    rabbitmq_manager: RabbitMQManager | None = None,
) -> None:
    # Database-backed pollers must run even when RabbitMQ is disabled. Otherwise
    # Ask jobs and Vector Snapshot builds can remain queued forever.
    registry.register(AskJobWorker(async_engine=engine, settings=settings))
    registry.register(VectorSnapshotWorker(async_engine=engine))

    if rabbitmq_manager is None:
        return

    publisher = AgentRabbitMQPublisher(rabbitmq_manager)
    registry.register(
        AgentOutboxDispatcherWorker(
            async_engine=engine,
            publisher=publisher,
        )
    )


assert isinstance(AgentWorkerRegistry, type)
_check: WorkerRegistryProtocol = AgentWorkerRegistry()
del _check
