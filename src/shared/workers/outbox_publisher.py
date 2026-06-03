from datetime import datetime, UTC

from sqlalchemy import func, select

from shared.infra.database.session_manager import SessionManager
from shared.infra.rabbitmq import RabbitMQManager
from shared.workers.base_worker import BaseWorker


class OutboxPublisherWorker(BaseWorker):

    MODULES = [
        "identity", "core", "ai", "knowledge",
        "runtime", "tools", "metering", "billing", "observability",
    ]
    MAX_ATTEMPTS = 5
    BATCH_SIZE = 50

    def __init__(self, async_engine, rmq: RabbitMQManager) -> None:
        super().__init__(async_engine)
        self._rmq = rmq

    async def run(self) -> None:
        for module in self.MODULES:
            await self._publish_module_events(module)

    async def _publish_module_events(self, module: str) -> None:
        import importlib
        import json

        mod = importlib.import_module(f"modules.{module}.infra.models")
        OutboxEvent = mod.OutboxEventModel

        async with SessionManager(self._async_engine) as manager:
            result = await manager.session.execute(
                select(OutboxEvent)
                .where(OutboxEvent.status == "pending")
                .where(OutboxEvent.available_at <= func.now())
                .order_by(OutboxEvent.created_at.asc())
                .limit(self.BATCH_SIZE)
            )
            events = result.scalars().all()

            for event in events:
                try:
                    routing_key = event.event_type
                    payload = json.dumps({
                        "id": str(event.id),
                        "aggregate_type": event.aggregate_type,
                        "aggregate_id": str(event.aggregate_id),
                        "event_type": event.event_type,
                        "event_version": event.event_version,
                        "payload": event.payload,
                        "correlation_id": str(event.correlation_id) if event.correlation_id else None,
                        "causation_id": str(event.causation_id) if event.causation_id else None,
                    })
                    await self._rmq.publish(
                        routing_key=routing_key,
                        payload=payload,
                        correlation_id=str(event.correlation_id) if event.correlation_id else None,
                    )
                except Exception as exc:
                    event.attempts += 1
                    event.error = str(exc)
                    event.status = "dead" if event.attempts >= self.MAX_ATTEMPTS else "failed"
                else:
                    event.status = "published"
                    event.published_at = datetime.now(UTC)
