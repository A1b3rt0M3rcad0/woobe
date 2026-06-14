"""Deprecated: runtime infra models have moved to modules.agent.infra.database.models.

This shim exists for backward compatibility during migration.
Removal spec: 142.
"""
import warnings

warnings.warn(
    "modules.runtime.infra.models is deprecated. Use modules.agent.infra.database.models instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.infra.database.models import (  # noqa: F401, E402
    AskJobModel,
    MessageModel,
    RuntimeInboxEventModel as InboxEventModel,
    RuntimeOutboxEventModel as OutboxEventModel,
    SessionModel,
)
