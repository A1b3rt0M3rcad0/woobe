"""Background workers — deprecated (spec 061).

Use shared.workers.runner.WorkerRunner with module registries instead.
"""
import warnings

from shared.workers.outbox_publisher import OutboxPublisherWorker
from shared.workers.inbox_consumer import InboxConsumerWorker

warnings.warn(
    "workers package is deprecated. Use shared.workers and module registries.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = [
    "OutboxPublisherWorker",
    "InboxConsumerWorker",
]
