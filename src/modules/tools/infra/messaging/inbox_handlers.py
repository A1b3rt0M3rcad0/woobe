from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

HANDLED_EVENTS: dict[str, str] = {
    "tools.tool.created": "handle_tool_created",
    "tools.tool.updated": "handle_tool_updated",
    "tools.tool.status_changed": "handle_tool_status_changed",
    "tools.secret.created": "handle_secret_created",
}


class ToolsInboxEventRouter:
    async def handle(self, event_type: str, payload: dict[str, Any], **kwargs: Any) -> None:
        handler_name = HANDLED_EVENTS.get(event_type)
        if handler_name is None:
            logger.warning("No handler registered for event type: %s", event_type)
            return
        logger.info("Routing event %s to %s", event_type, handler_name)
