"""Deprecated: runtime infra mappers have moved to modules.agent.infra.database.mappers.

This shim exists for backward compatibility during migration.
Removal spec: 142.
"""
import warnings

warnings.warn(
    "modules.runtime.infra.mappers is deprecated. Use modules.agent.infra.database.mappers instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.infra.database.mappers import (  # noqa: F401, E402
    ask_job_to_model,
    message_to_model,
    model_to_ask_job,
    model_to_message,
    model_to_session,
    session_to_model,
)
