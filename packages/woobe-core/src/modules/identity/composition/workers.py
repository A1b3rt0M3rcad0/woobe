from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine

from modules.identity.infra.messaging.publishers import IdentityRabbitMQPublisher
from modules.identity.infra.workers.outbox_dispatcher import IdentityOutboxDispatcherWorker
from shared.infra.rabbitmq import RabbitMQManager
from shared.workers.contracts import WorkerProtocol, WorkerRegistryProtocol


class IdentityWorkerRegistry:
    def __init__(self, workers: list[WorkerProtocol] | None = None) -> None:
        self._workers: list[WorkerProtocol] = workers or []

    def register(self, worker: WorkerProtocol) -> None:
        self._workers.append(worker)

    def iter_workers(self) -> list[WorkerProtocol]:
        return list(self._workers)


def register_identity_workers(
    registry: IdentityWorkerRegistry,
    settings: Any,
    engine: AsyncEngine,
    rabbitmq_manager: RabbitMQManager | None = None,
) -> None:
    del settings
    if rabbitmq_manager is None:
        return

    publisher = IdentityRabbitMQPublisher(rabbitmq_manager)
    registry.register(
        IdentityOutboxDispatcherWorker(
            async_engine=engine,
            publisher=publisher,
        )
    )


_check: WorkerRegistryProtocol = IdentityWorkerRegistry()
del _check


__all__ = ["IdentityWorkerRegistry", "register_identity_workers"]
