from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine

from modules.core.infra.messaging.publishers import CoreRabbitMQPublisher
from modules.core.infra.workers.outbox_dispatcher import CoreOutboxDispatcherWorker
from modules.core.infra.workers.registry import CoreWorkerRegistry
from shared.infra.rabbitmq import RabbitMQManager
from shared.workers.contracts import WorkerRegistryProtocol


def register_core_workers(
    registry: WorkerRegistryProtocol,
    settings: Any | None = None,
    engine: AsyncEngine | None = None,
    rabbitmq_manager: RabbitMQManager | None = None,
) -> None:
    del settings
    if engine is None or rabbitmq_manager is None:
        return
    publisher = CoreRabbitMQPublisher(rabbitmq_manager)
    registry.register(
        CoreOutboxDispatcherWorker(
            async_engine=engine,
            publisher=publisher,
        )
    )


__all__ = ["CoreWorkerRegistry", "register_core_workers"]
