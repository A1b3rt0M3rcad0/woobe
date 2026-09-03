from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine

from modules.observability.background_boundary import ObservabilityInboxEventRouter
from modules.observability.background_boundary import ObservabilityRabbitMQPublisher
from woobe_workers.consumers.observability.inbox_consumer import ObservabilityInboxConsumerWorker
from woobe_workers.consumers.observability.inbox_processor import ObservabilityInboxProcessorWorker
from woobe_workers.consumers.observability.outbox_dispatcher import ObservabilityOutboxDispatcherWorker
from shared.infra.rabbitmq import RabbitMQManager
from woobe_workers.contracts import WorkerProtocol, WorkerRegistryProtocol


class ObservabilityWorkerRegistry:
    def __init__(self, workers: list[WorkerProtocol] | None = None) -> None:
        self._workers: list[WorkerProtocol] = workers or []

    def register(self, worker: WorkerProtocol) -> None:
        self._workers.append(worker)

    def iter_workers(self) -> list[WorkerProtocol]:
        return list(self._workers)


def register_observability_workers(
    registry: WorkerRegistryProtocol,
    settings: Any | None = None,
    engine: AsyncEngine | None = None,
    rabbitmq_manager: RabbitMQManager | None = None,
) -> None:
    if engine is None or rabbitmq_manager is None:
        return

    publisher = ObservabilityRabbitMQPublisher(rabbitmq_manager)

    outbox_dispatcher = ObservabilityOutboxDispatcherWorker(
        async_engine=engine,
        publisher=publisher,
    )
    registry.register(outbox_dispatcher)

    inbox_consumer = ObservabilityInboxConsumerWorker(
        async_engine=engine,
        rabbitmq_manager=rabbitmq_manager,
    )
    registry.register(inbox_consumer)

    inbox_handler_router = ObservabilityInboxEventRouter()
    inbox_processor = ObservabilityInboxProcessorWorker(
        async_engine=engine,
        handler=inbox_handler_router,
    )
    registry.register(inbox_processor)


assert isinstance(ObservabilityWorkerRegistry, type)
_check: WorkerRegistryProtocol = ObservabilityWorkerRegistry()
del _check
