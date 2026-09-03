"""Public host boundary for core background execution.

This module is the only supported surface through which external process hosts
may consume core background capabilities. It contains no worker
lifecycle, registry, polling, slot or process-bootstrap behavior.
"""

from modules.core.infra.database.models import (
    InboxEventModel,
    OutboxEventModel,
)
from modules.core.infra.messaging.event_mappers import (
    RabbitMQMessageEnvelope,
    outbox_to_rabbit_message,
    rabbit_message_to_inbox,
)
from modules.core.infra.messaging.publishers import (
    CoreRabbitMQPublisher,
)
