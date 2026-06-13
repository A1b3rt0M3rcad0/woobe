import warnings

warnings.warn(
    "modules.ai.application.composers.list_releases_composer is deprecated. "
    "Use modules.agent.application.composers.list_releases_composer instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.application.composers.list_releases_composer import list_releases_composer  # noqa: E402, F401

__all__ = ["list_releases_composer"]
