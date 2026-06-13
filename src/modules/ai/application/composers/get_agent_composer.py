import warnings

warnings.warn(
    "modules.ai.application.composers.get_agent_composer is deprecated. "
    "Use modules.agent.application.composers.get_agent_composer instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.application.composers.get_agent_composer import get_agent_composer  # noqa: E402, F401

__all__ = ["get_agent_composer"]
