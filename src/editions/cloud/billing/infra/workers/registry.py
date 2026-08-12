from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine

from editions.cloud.billing.infra.messaging.publishers import BillingRabbitMQPublisher
from editions.cloud.billing.infra.workers.outbox_dispatcher import BillingOutboxDispatcherWorker
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


assert isinstance(BillingWorkerRegistry, type)
_check: WorkerRegistryProtocol = BillingWorkerRegistry()
del _check
