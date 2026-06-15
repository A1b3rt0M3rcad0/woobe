from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

HANDLED_EVENTS: dict[str, str] = {
    "billing.plan.created.v1": "handle_plan_created",
    "billing.customer.created.v1": "handle_customer_created",
    "billing.subscription.created.v1": "handle_subscription_created",
    "billing.payment_event.received.v1": "handle_payment_event_received",
}


class BillingInboxEventRouter:
    async def handle(self, event_type: str, payload: dict[str, Any], **kwargs: Any) -> None:
        handler_name = HANDLED_EVENTS.get(event_type)
        if handler_name is None:
            logger.warning("No handler registered for event type: %s", event_type)
            return
        logger.info("Routing event %s to %s", event_type, handler_name)
