from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from modules.tools.infra.messaging.event_mappers import rabbit_message_to_inbox
from shared.workers.inbox_processor_base import BaseInboxProcessor

logger = logging.getLogger(__name__)


class ToolsInboxProcessorWorker(BaseInboxProcessor):
    def __init__(self, async_engine: AsyncEngine) -> None:
        super().__init__(async_engine)

    async def process_message(self, message_body: bytes) -> None:
        inbox_event = rabbit_message_to_inbox(message_body)
        async with AsyncSession(self._async_engine) as session:
            session.add(inbox_event)
            await session.commit()
        logger.debug("Processed inbox event: %s", inbox_event.event_type)
