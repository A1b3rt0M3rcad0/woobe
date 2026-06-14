import warnings

warnings.warn(
    "modules.ai.presentation.controllers.create_agent_controller is deprecated. "
    "Use modules.agent.presentation.controllers.create_agent_controller instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.presentation.controllers.create_agent_controller import CreateAgentController  # noqa: F401, E402
