from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine

from modules.metering.background_boundary import MeteringInboxEventRouter
from modules.metering.background_boundary import MeteringRabbitMQPublisher
from woobe_workers.consumers.metering.inbox_consumer import MeteringInboxConsumerWorker
from woobe_workers.consumers.metering.inbox_processor import MeteringInboxProcessorWorker
from woobe_workers.consumers.metering.outbox_dispatcher import MeteringOutboxDispatcherWorker
from shared.infra.rabbitmq import RabbitMQManager
from woobe_workers.contracts import WorkerProtocol, WorkerRegistryProtocol


class MeteringWorkerRegistry:
    def __init__(self, workers: list[WorkerProtocol] | None = None) -> None:
        self._workers: list[WorkerProtocol] = workers or []

    def register(self, worker: WorkerProtocol) -> None:
        self._workers.append(worker)

    def iter_workers(self) -> list[WorkerProtocol]:
        return list(self._workers)


def register_metering_workers(
    registry: WorkerRegistryProtocol,
    settings: Any | None = None,
    engine: AsyncEngine | None = None,
    rabbitmq_manager: RabbitMQManager | None = None,
) -> None:
    if engine is None or rabbitmq_manager is None:
        return

    publisher = MeteringRabbitMQPublisher(rabbitmq_manager)

    outbox_dispatcher = MeteringOutboxDispatcherWorker(
        async_engine=engine,
        publisher=publisher,
    )
    registry.register(outbox_dispatcher)

    inbox_consumer = MeteringInboxConsumerWorker(
        async_engine=engine,
        rabbitmq_manager=rabbitmq_manager,
    )
    registry.register(inbox_consumer)

    inbox_handler_router = MeteringInboxEventRouter()
    inbox_processor = MeteringInboxProcessorWorker(
        async_engine=engine,
        handler=inbox_handler_router,
    )
    registry.register(inbox_processor)


assert isinstance(MeteringWorkerRegistry, type)
_check: WorkerRegistryProtocol = MeteringWorkerRegistry()
del _check
