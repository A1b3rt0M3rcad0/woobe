"""Identity inbox event router — routes inbox events to domain handlers."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

HANDLED_EVENTS: dict[str, str] = {
    "identity.user.created.v1": "handle_user_created",
    "identity.workspace.created.v1": "handle_workspace_created",
    "identity.workspace.member_added.v1": "handle_member_added",
}


class IdentityInboxEventRouter:
    async def handle(self, event_type: str, payload: dict[str, Any], **kwargs: Any) -> None:
        handler_name = HANDLED_EVENTS.get(event_type)
        if handler_name is None:
            logger.warning("No handler registered for event type: %s", event_type)
            return
        logger.info("Routing event %s to %s", event_type, handler_name)
