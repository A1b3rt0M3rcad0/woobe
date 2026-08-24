from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine

from modules.agent.infra.adapters.http_tool_runtime import get_http_tool_executor
from modules.network.infra.runtime.finalizer import NetworkRuntimeFinalizer
from modules.network.infra.runtime.loader import NetworkRuntimeLoader
from modules.network.infra.runtime.redis_store import RedisNetworkExecutionStore
from modules.network.infra.workers.execution_worker import (
    NetworkExecutionConsumer,
    NetworkExecutionProcessor,
    NetworkLeaseRecoveryWorker,
)
from modules.network.infra.workers.outbox_dispatcher import NetworkOutboxDispatcherWorker
from shared.composition_resources import EXECUTION_STATE_STORE, SESSION_FACTORY
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

    loader = NetworkRuntimeLoader(SESSION_FACTORY)
    finalizer = NetworkRuntimeFinalizer(SESSION_FACTORY)
    state_store = RedisNetworkExecutionStore(EXECUTION_STATE_STORE)
    processor = NetworkExecutionProcessor(
        loader=loader,
        store=state_store,
        finalizer=finalizer,
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
