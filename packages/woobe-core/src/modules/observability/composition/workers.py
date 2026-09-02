from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine

from modules.observability.infra.messaging.inbox_handlers import ObservabilityInboxEventRouter
from modules.observability.infra.messaging.publishers import ObservabilityRabbitMQPublisher
from modules.observability.infra.workers.inbox_consumer import ObservabilityInboxConsumerWorker
from modules.observability.infra.workers.inbox_processor import ObservabilityInboxProcessorWorker
from modules.observability.infra.workers.outbox_dispatcher import ObservabilityOutboxDispatcherWorker
from modules.observability.infra.workers.registry import ObservabilityWorkerRegistry
from shared.infra.rabbitmq import RabbitMQManager
from shared.workers.contracts import WorkerRegistryProtocol


def register_observability_workers(
    registry: WorkerRegistryProtocol,
    settings: Any | None = None,
    engine: AsyncEngine | None = None,
    rabbitmq_manager: RabbitMQManager | None = None,
) -> None:
    del settings
    if engine is None or rabbitmq_manager is None:
        return
    publisher = ObservabilityRabbitMQPublisher(rabbitmq_manager)
    registry.register(
        ObservabilityOutboxDispatcherWorker(
            async_engine=engine,
            publisher=publisher,
        )
    )
    registry.register(
        ObservabilityInboxConsumerWorker(
            async_engine=engine,
            rabbitmq_manager=rabbitmq_manager,
        )
    )
    registry.register(
        ObservabilityInboxProcessorWorker(
            async_engine=engine,
            handler=ObservabilityInboxEventRouter(),
        )
    )


__all__ = ["ObservabilityWorkerRegistry", "register_observability_workers"]
