import warnings

warnings.warn(
    "modules.ai.application.composers.list_agents_composer is deprecated. "
    "Use modules.agent.application.composers.list_agents_composer instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.application.composers.list_agents_composer import list_agents_composer  # noqa: E402, F401

__all__ = ["list_agents_composer"]
