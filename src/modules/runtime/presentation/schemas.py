"""Deprecated: runtime presentation schemas have moved to modules.agent.presentation.schemas.

This shim exists for backward compatibility during migration.
Removal spec: 142.
"""
import warnings

warnings.warn(
    "modules.runtime.presentation.schemas is deprecated. Use modules.agent.presentation.schemas instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.presentation.schemas import (  # noqa: F401, E402
    AskRequest,
    AskResponse,
    CreateSessionRequest,
    MessageResponse,
    SendMessageRequest,
    SessionResponse,
    SourceResponse,
    ToolCallResponse,
    UsageResponse,
)
