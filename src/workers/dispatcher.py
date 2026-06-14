"""Deprecated — domain event handlers removed (spec 061).

Event dispatch is now the responsibility of each module's own worker registry.
See src/modules/<module>/infra/workers/registry.py (specs 062-063).
"""
import warnings

warnings.warn(
    "workers.dispatcher is deprecated. Use module-specific worker registries.",
    DeprecationWarning,
    stacklevel=2,
)
