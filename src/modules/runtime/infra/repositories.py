"""Deprecated: runtime infra repositories have moved to modules.agent.infra.database.repositories.

This shim exists for backward compatibility during migration.
Removal spec: 142.
"""
import warnings

warnings.warn(
    "modules.runtime.infra.repositories is deprecated. Use modules.agent.infra.database.repositories instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.infra.database.repositories import (  # noqa: F401, E402
    SQLAlchemyAskJobRepository,
    SQLAlchemyMessageRepository,
    SQLAlchemyRuntimeOutboxEventWriter as SQLAlchemyOutboxEventWriter,
    SQLAlchemySessionRepository,
)
