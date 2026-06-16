from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

HANDLED_EVENTS: dict[str, str] = {
    "metering.usage.recorded.v1": "handle_usage_recorded",
    "metering.usage.daily_aggregated.v1": "handle_daily_aggregated",
}


class MeteringInboxEventRouter:
    async def handle(self, event_type: str, payload: dict[str, Any], **kwargs: Any) -> None:
        handler_name = HANDLED_EVENTS.get(event_type)
        if handler_name is None:
            logger.warning("No handler registered for event type: %s", event_type)
            return
        logger.info("Routing event %s to %s", event_type, handler_name)
