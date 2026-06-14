import warnings

warnings.warn(
    "modules.ai.presentation.controllers.get_agent_controller is deprecated. "
    "Use modules.agent.presentation.controllers.get_agent_controller instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.presentation.controllers.get_agent_controller import GetAgentController  # noqa: F401, E402
