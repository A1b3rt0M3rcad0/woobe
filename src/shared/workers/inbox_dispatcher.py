from datetime import datetime, UTC
from typing import Any, Callable, Coroutine

from sqlalchemy import func, select

from shared.infra.database.session_manager import SessionManager
from shared.workers.base_worker import BaseWorker

EventHandler = Callable[[Any], Coroutine[Any, Any, None]]


class InboxDispatcherWorker(BaseWorker):

    MODULES = [
        "identity", "core", "ai", "knowledge",
        "runtime", "tools", "metering", "billing", "observability",
    ]
    MAX_ATTEMPTS = 5
    BATCH_SIZE = 50
    CONSUMER_NAME = "default"

    def __init__(self, async_engine, handlers: dict[str, EventHandler] | None = None) -> None:
        super().__init__(async_engine)
        self._handlers: dict[str, EventHandler] = handlers or {}

    def register_handler(self, event_type: str, handler: EventHandler) -> None:
        self._handlers[event_type] = handler

    async def run(self) -> None:
        for module in self.MODULES:
            await self._dispatch_module_events(module)

    async def _dispatch_module_events(self, module: str) -> None:
        import importlib

        mod = importlib.import_module(f"modules.{module}.infra.models")
        InboxEvent = mod.InboxEventModel

        async with SessionManager(self._async_engine) as manager:
            result = await manager.session.execute(
                select(InboxEvent)
                .where(InboxEvent.status == "pending")
                .where(InboxEvent.available_at <= func.now())
                .order_by(InboxEvent.created_at.asc())
                .limit(self.BATCH_SIZE)
            )
            events = result.scalars().all()

            for event in events:
                handler = self._handlers.get(event.event_type)
                if handler is None:
                    continue

                try:
                    await handler(event)
                except Exception as exc:
                    event.attempts += 1
                    event.error = str(exc)
                    event.status = "dead" if event.attempts >= self.MAX_ATTEMPTS else "failed"
                else:
                    event.status = "processed"
                    event.processed_at = datetime.now(UTC)
                    event.consumer_name = self.CONSUMER_NAME
