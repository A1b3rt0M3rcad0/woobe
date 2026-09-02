from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine

from modules.network.application.runtime import AgentInvoker
from modules.network.infra.database.unit_of_work import NetworkUnitOfWork
from modules.network.infra.runtime.finalizer import (
    AgentRunMaterializer,
    NetworkRuntimeFinalizer,
)
from modules.network.infra.runtime.loader import NetworkRuntimeLoader
from modules.network.infra.runtime.redis_store import RedisNetworkExecutionStore
from modules.network.infra.workers.execution_worker import (
    NetworkExecutionConsumer,
    NetworkExecutionProcessor,
    NetworkLeaseRecoveryWorker,
)
from modules.network.infra.workers.outbox_dispatcher import NetworkOutboxDispatcherWorker
from shared.composition_resources import EXECUTION_STATE_STORE
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
    *,
    agent_invoker: AgentInvoker,
    agent_materializer: AgentRunMaterializer,
) -> None:
    if rabbitmq_manager is None or not settings.network_runtime_enabled:
        return

    uow_factory = lambda: NetworkUnitOfWork(engine)
    loader = NetworkRuntimeLoader(uow_factory)
    finalizer = NetworkRuntimeFinalizer(
        uow_factory,
        agent_materializer,
    )
    state_store = RedisNetworkExecutionStore(EXECUTION_STATE_STORE)
    processor = NetworkExecutionProcessor(
        loader=loader,
        store=state_store,
        finalizer=finalizer,
        agent_invoker=agent_invoker,
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
    registry.register(
        NetworkLeaseRecoveryWorker(
            loader=loader,
            store=state_store,
            finalizer=finalizer,
            lease_ttl_seconds=settings.network_execution_lease_ttl_seconds,
        )
    )


_check: WorkerRegistryProtocol = NetworkWorkerRegistry()
del _check


__all__ = ["NetworkWorkerRegistry", "register_network_workers"]
