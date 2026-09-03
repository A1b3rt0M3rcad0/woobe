"""Public host boundary for observability background execution.

This module is the only supported surface through which external process hosts
may consume observability background capabilities. It contains no worker
lifecycle, registry, polling, slot or process-bootstrap behavior.
"""

from modules.observability.infra.database.models import (
    InboxEventModel,
    OutboxEventModel,
)
from modules.observability.infra.database.repositories import (
    OBSERVABILITY_DEFAULT_BATCH_SIZE,
    SQLAlchemyObservabilityInboxRepository,
)
from modules.observability.infra.messaging.event_mappers import (
    RabbitMQMessageEnvelope,
    outbox_to_rabbit_message,
    rabbit_message_to_inbox,
)
from modules.observability.infra.messaging.inbox_handlers import (
    ObservabilityInboxEventRouter,
)
from modules.observability.infra.messaging.publishers import (
    ObservabilityRabbitMQPublisher,
)
