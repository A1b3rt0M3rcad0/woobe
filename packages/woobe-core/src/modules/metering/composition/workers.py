from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine

from modules.metering.infra.messaging.inbox_handlers import MeteringInboxEventRouter
from modules.metering.infra.messaging.publishers import MeteringRabbitMQPublisher
from modules.metering.infra.workers.inbox_consumer import MeteringInboxConsumerWorker
from modules.metering.infra.workers.inbox_processor import MeteringInboxProcessorWorker
from modules.metering.infra.workers.outbox_dispatcher import MeteringOutboxDispatcherWorker
from modules.metering.infra.workers.registry import MeteringWorkerRegistry
from shared.infra.rabbitmq import RabbitMQManager
from shared.workers.contracts import WorkerRegistryProtocol


def register_metering_workers(
    registry: WorkerRegistryProtocol,
    settings: Any | None = None,
    engine: AsyncEngine | None = None,
    rabbitmq_manager: RabbitMQManager | None = None,
) -> None:
    del settings
    if engine is None or rabbitmq_manager is None:
        return

    publisher = MeteringRabbitMQPublisher(rabbitmq_manager)
    registry.register(
        MeteringOutboxDispatcherWorker(
            async_engine=engine,
            publisher=publisher,
        )
    )
    registry.register(
        MeteringInboxConsumerWorker(
            async_engine=engine,
            rabbitmq_manager=rabbitmq_manager,
        )
    )
    registry.register(
        MeteringInboxProcessorWorker(
            async_engine=engine,
            handler=MeteringInboxEventRouter(),
        )
    )


__all__ = ["MeteringWorkerRegistry", "register_metering_workers"]
