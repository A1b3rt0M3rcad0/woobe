import json

from aio_pika import IncomingMessage

from shared.infra.database.session_manager import SessionManager
from shared.infra.rabbitmq import RabbitMQManager
from shared.workers.base_worker import BaseWorker


def _module_for_event_type(event_type: str) -> str:
    return event_type.split(".", 1)[0]


class InboxConsumerWorker(BaseWorker):

    def __init__(self, async_engine, rmq: RabbitMQManager, queue_name: str = "projectrai.inbox") -> None:
        super().__init__(async_engine)
        self._rmq = rmq
        self._queue_name = queue_name

    async def run(self) -> None:
        await self._rmq.consume(
            queue_name=self._queue_name,
            routing_keys=["#"],
            callback=self._on_message,
        )

    async def _on_message(self, message: IncomingMessage) -> None:
        import importlib

        async with message.process(requeue=True):
            body = json.loads(message.body.decode())
            event_type = body["event_type"]
            module = _module_for_event_type(event_type)

            try:
                mod = importlib.import_module(f"modules.{module}.infra.models")
                InboxEvent = mod.InboxEventModel
            except (ImportError, AttributeError):
                return

            async with SessionManager(self._async_engine) as manager:
                inbox_event = InboxEvent(
                    outbox_origin_id=body["id"],
                    aggregate_type=body["aggregate_type"],
                    event_type=event_type,
                    event_version=body.get("event_version", 1),
                    payload=body["payload"],
                    correlation_id=body.get("correlation_id"),
                    causation_id=body.get("causation_id"),
                )
                manager.session.add(inbox_event)
