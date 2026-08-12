from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from modules.agent.infra.adapters.http_tool_runtime import get_http_tool_executor
from modules.network.infra.workers.execution_worker import (
    NetworkExecutionConsumer,
    NetworkExecutionProcessor,
    NetworkLeaseRecoveryWorker,
)
from modules.network.infra.workers.outbox_dispatcher import (
    NetworkOutboxDispatcherWorker,
)
from shared.infra.config import Settings
from shared.infra.rabbitmq import RabbitMQManager
from shared.workers.contracts import WorkerProtocol, WorkerRegistryProtocol


class NetworkWorkerRegistry:
    def __init__(self) -> None:
        self._workers: list[WorkerProtocol] = []

    def register(self, worker: WorkerProtocol) -> None:
        self._workers.append(worker)

    def iter_workers(self) -> list[WorkerProtocol]:
        return list(self._workers)


def register_network_workers(
    registry: NetworkWorkerRegistry,
    settings: Settings,
    engine: AsyncEngine,
    rabbitmq_manager: RabbitMQManager | None = None,
) -> None:
    if rabbitmq_manager is None or not settings.network_runtime_enabled:
        return
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    processor = NetworkExecutionProcessor(
        session_factory,
        settings=settings,
        http_executor=get_http_tool_executor(),
        lease_ttl_seconds=settings.network_execution_lease_ttl_seconds,
        heartbeat_seconds=settings.network_execution_lease_heartbeat_seconds,
    )
    registry.register(
        NetworkOutboxDispatcherWorker(
            engine,
            rabbitmq_manager,
            batch_size=settings.outbox_batch_size,
        )
    )
    registry.register(
        NetworkExecutionConsumer(
            rabbitmq_manager,
            processor,
            prefetch_count=settings.network_worker_prefetch,
            worker_slots=settings.network_worker_slots,
        )
    )
    registry.register(NetworkLeaseRecoveryWorker(engine))


_check: WorkerRegistryProtocol = NetworkWorkerRegistry()
del _check
