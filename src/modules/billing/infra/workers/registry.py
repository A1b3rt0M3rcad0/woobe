from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine

from modules.billing.infra.messaging.inbox_handlers import BillingInboxEventRouter
from modules.billing.infra.messaging.publishers import BillingRabbitMQPublisher
from modules.billing.infra.workers.inbox_consumer import BillingInboxConsumerWorker
from modules.billing.infra.workers.inbox_processor import BillingInboxProcessorWorker
from modules.billing.infra.workers.outbox_dispatcher import BillingOutboxDispatcherWorker
from shared.infra.rabbitmq import RabbitMQManager
from shared.workers.contracts import WorkerProtocol, WorkerRegistryProtocol


class BillingWorkerRegistry:
    def __init__(self, workers: list[WorkerProtocol] | None = None) -> None:
        self._workers: list[WorkerProtocol] = workers or []

    def register(self, worker: WorkerProtocol) -> None:
        self._workers.append(worker)

    def iter_workers(self) -> list[WorkerProtocol]:
        return list(self._workers)


def register_billing_workers(
    registry: BillingWorkerRegistry,
    settings: Any,
    engine: AsyncEngine,
    rabbitmq_manager: RabbitMQManager | None = None,
) -> None:
    if rabbitmq_manager is None:
        return

    publisher = BillingRabbitMQPublisher(rabbitmq_manager)

    outbox_dispatcher = BillingOutboxDispatcherWorker(
        async_engine=engine,
        publisher=publisher,
    )
    registry.register(outbox_dispatcher)

    inbox_consumer = BillingInboxConsumerWorker(
        async_engine=engine,
        rabbitmq_manager=rabbitmq_manager,
    )
    registry.register(inbox_consumer)

    inbox_handler_router = BillingInboxEventRouter()
    inbox_processor = BillingInboxProcessorWorker(
        async_engine=engine,
        handler=inbox_handler_router,
    )
    registry.register(inbox_processor)


assert isinstance(BillingWorkerRegistry, type)
_check: WorkerRegistryProtocol = BillingWorkerRegistry()
del _check
