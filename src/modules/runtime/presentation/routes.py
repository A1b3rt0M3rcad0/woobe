"""Deprecated: runtime presentation routes have moved to modules.agent.presentation.routes.

This shim exists for backward compatibility during migration.
Removal spec: 142.
"""
import warnings

warnings.warn(
    "modules.runtime.presentation.routes is deprecated. Use modules.agent.presentation.routes.runtime_router instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.presentation.routes import runtime_router as router  # noqa: F401, E402
