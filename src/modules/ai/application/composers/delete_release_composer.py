import warnings

warnings.warn(
    "modules.ai.application.composers.delete_release_composer is deprecated. "
    "Use modules.agent.application.composers.delete_release_composer instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.application.composers.delete_release_composer import delete_release_composer  # noqa: E402, F401

__all__ = ["delete_release_composer"]
