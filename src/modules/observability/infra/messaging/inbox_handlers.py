from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

HANDLED_EVENTS: dict[str, str] = {
    "observability.trace.started.v1": "handle_trace_started",
    "observability.trace.completed.v1": "handle_trace_completed",
    "observability.trace.failed.v1": "handle_trace_failed",
}


class ObservabilityInboxEventRouter:
    async def handle(self, event_type: str, payload: dict[str, Any], **kwargs: Any) -> None:
        handler_name = HANDLED_EVENTS.get(event_type)
        if handler_name is None:
            logger.warning("No handler registered for event type: %s", event_type)
            return
        logger.info("Routing event %s to %s", event_type, handler_name)
