from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine

from modules.agent.infra.messaging.inbox_handlers import AgentInboxEventRouter
from modules.agent.infra.messaging.publishers import AgentRabbitMQPublisher
from modules.agent.infra.workers.ask_job_worker import AskJobWorker
from modules.agent.infra.workers.inbox_consumer import AgentInboxConsumerWorker
from modules.agent.infra.workers.inbox_processor import AgentInboxProcessorWorker
from modules.agent.infra.workers.outbox_dispatcher import AgentOutboxDispatcherWorker
from shared.infra.rabbitmq import RabbitMQManager
from shared.workers.contracts import WorkerProtocol, WorkerRegistryProtocol


class AgentWorkerRegistry:
    def __init__(self, workers: list[WorkerProtocol] | None = None) -> None:
        self._workers: list[WorkerProtocol] = workers or []

    def register(self, worker: WorkerProtocol) -> None:
        self._workers.append(worker)

    def iter_workers(self) -> list[WorkerProtocol]:
        return list(self._workers)


def register_agent_workers(
    registry: AgentWorkerRegistry,
    settings: Any,
    engine: AsyncEngine,
    rabbitmq_manager: RabbitMQManager | None = None,
) -> None:
    if rabbitmq_manager is None:
        return

    publisher = AgentRabbitMQPublisher(rabbitmq_manager)

    outbox_dispatcher = AgentOutboxDispatcherWorker(
        async_engine=engine,
        publisher=publisher,
    )
    registry.register(outbox_dispatcher)

    inbox_consumer = AgentInboxConsumerWorker(
        async_engine=engine,
        rabbitmq_manager=rabbitmq_manager,
    )
    registry.register(inbox_consumer)

    inbox_handler_router = AgentInboxEventRouter()
    inbox_processor = AgentInboxProcessorWorker(
        async_engine=engine,
        handler=inbox_handler_router,
    )
    registry.register(inbox_processor)

    ask_job_worker = AskJobWorker(async_engine=engine)
    registry.register(ask_job_worker)


assert isinstance(AgentWorkerRegistry, type)
_check: WorkerRegistryProtocol = AgentWorkerRegistry()
del _check
