"""AI module — DEPRECATED.

This module has been migrated to `src/modules/agent`. All functionality now
lives in the agent bounded context. Shim imports delegate to agent equivalents.

This module will be removed in spec 143.
"""
import warnings

warnings.warn(
    "modules.ai is deprecated. Use modules.agent instead. "
    "This module will be removed in spec 143.",
    DeprecationWarning,
    stacklevel=2,
)