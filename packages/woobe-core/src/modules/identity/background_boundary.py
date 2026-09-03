"""Public host boundary for identity background execution.

This module is the only supported surface through which external process hosts
may consume identity background capabilities. It contains no worker
lifecycle, registry, polling, slot or process-bootstrap behavior.
"""

from modules.identity.infra.database.models import (
    InboxEventModel,
    OutboxEventModel,
)
from modules.identity.infra.messaging.event_mappers import (
    RabbitMQMessageEnvelope,
    outbox_to_rabbit_message,
    rabbit_message_to_inbox,
)
from modules.identity.infra.messaging.publishers import (
    IdentityRabbitMQPublisher,
)
