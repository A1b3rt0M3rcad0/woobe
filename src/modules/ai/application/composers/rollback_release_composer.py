import warnings

warnings.warn(
    "modules.ai.application.composers.rollback_release_composer is deprecated. "
    "Use modules.agent.application.composers.rollback_release_composer instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.application.composers.rollback_release_composer import rollback_release_composer  # noqa: E402, F401

__all__ = ["rollback_release_composer"]
