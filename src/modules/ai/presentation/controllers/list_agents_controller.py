import warnings

warnings.warn(
    "modules.ai.presentation.controllers.list_agents_controller is deprecated. "
    "Use modules.agent.presentation.controllers.list_agents_controller instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.presentation.controllers.list_agents_controller import ListAgentsController  # noqa: F401, E402
