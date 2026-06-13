import warnings

warnings.warn(
    "modules.ai.application.composers.promote_release_composer is deprecated. "
    "Use modules.agent.application.composers.promote_release_composer instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.application.composers.promote_release_composer import promote_release_composer  # noqa: E402, F401

__all__ = ["promote_release_composer"]
