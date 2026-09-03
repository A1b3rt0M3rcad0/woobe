from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine

from modules.agent.background_boundary import AgentRabbitMQPublisher
from woobe_workers.consumers.agent.ask_job_worker import AskJobWorker
from woobe_workers.consumers.agent.outbox_dispatcher import AgentOutboxDispatcherWorker
from woobe_workers.consumers.agent.run_recovery_worker import AgentRunRecoveryWorker
from woobe_workers.consumers.agent.vector_snapshot_worker import VectorSnapshotWorker
from shared.composition_resources import EXECUTION_STATE_STORE
from shared.infra.rabbitmq import RabbitMQManager
from woobe_workers.contracts import WorkerProtocol, WorkerRegistryProtocol


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
    # Ask jobs, Vector Snapshot builds and orphan Run recovery can remain pending.
    registry.register(AskJobWorker(async_engine=engine, settings=settings))
    registry.register(VectorSnapshotWorker(async_engine=engine))
    registry.register(
        AgentRunRecoveryWorker(
            async_engine=engine,
            state_store=EXECUTION_STATE_STORE,
            stale_after_seconds=max(
                900.0,
                float(getattr(settings, "runtime_total_timeout_seconds", 120.0)) * 3,
            ),
        )
    )

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
