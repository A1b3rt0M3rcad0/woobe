from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from modules.observability.infra.database.models import InboxEventModel
from modules.observability.infra.messaging.inbox_handlers import ObservabilityInboxEventRouter

logger = logging.getLogger(__name__)


class ObservabilityInboxConsumerWorker:
    def __init__(self, async_engine: AsyncEngine, router: ObservabilityInboxEventRouter) -> None:
        self._async_engine = async_engine
        self._router = router

    async def run(self) -> None:
        async with AsyncSession(self._async_engine) as session:
            stmt = (
                select(InboxEventModel)
                .where(InboxEventModel.status == "pending")
                .order_by(InboxEventModel.created_at.asc())
                .limit(50)
                .with_for_update(skip_locked=True)
            )
            result = await self._execute(session, stmt)
            events = list(result.scalars().all())

            for event in events:
                try:
                    await self._router.handle(
                        event_type=event.event_type,
                        payload=event.payload,
                    )
                    event.status = "processed"
                except Exception:
                    logger.exception("Failed to process inbox event %s", event.id)
                    event.status = "failed"

            await session.commit()

    @staticmethod
    async def _execute(session: AsyncSession, stmt: Any) -> Any:
        return await session.execute(stmt)
