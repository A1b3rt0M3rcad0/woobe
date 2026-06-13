import warnings

warnings.warn(
    "modules.ai.application.composers.create_agent_composer is deprecated. "
    "Use modules.agent.application.composers.create_agent_composer instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.application.composers.create_agent_composer import create_agent_composer  # noqa: E402, F401

__all__ = ["create_agent_composer"]
