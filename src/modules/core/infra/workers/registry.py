from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine

from modules.core.infra.messaging.publishers import CoreRabbitMQPublisher
from modules.core.infra.workers.outbox_dispatcher import CoreOutboxDispatcherWorker
from shared.infra.rabbitmq import RabbitMQManager
from shared.workers.contracts import WorkerProtocol, WorkerRegistryProtocol


class CoreWorkerRegistry:
    def __init__(self, workers: list[WorkerProtocol] | None = None) -> None:
        self._workers: list[WorkerProtocol] = workers or []

    def register(self, worker: WorkerProtocol) -> None:
        self._workers.append(worker)

    def iter_workers(self) -> list[WorkerProtocol]:
        return list(self._workers)


def register_core_workers(
    registry: CoreWorkerRegistry,
    settings: Any,
    engine: AsyncEngine,
    rabbitmq_manager: RabbitMQManager | None = None,
) -> None:
    if rabbitmq_manager is None:
        return

    publisher = CoreRabbitMQPublisher(rabbitmq_manager)

    outbox_dispatcher = CoreOutboxDispatcherWorker(
        async_engine=engine,
        publisher=publisher,
    )
    registry.register(outbox_dispatcher)


assert isinstance(CoreWorkerRegistry, type)
_check: WorkerRegistryProtocol = CoreWorkerRegistry()
del _check
