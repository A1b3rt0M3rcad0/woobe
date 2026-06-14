"""Knowledge module — DEPRECATED.

This module has been migrated to `src/modules/agent`. All functionality now
lives in the agent bounded context. Shim imports delegate to agent equivalents.

This module will be removed in spec 144.
"""
import warnings

warnings.warn(
    "modules.knowledge is deprecated. Use modules.agent instead. "
    "This module will be removed in spec 144.",
    DeprecationWarning,
    stacklevel=2,
)
