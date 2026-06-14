"""Deprecated: use modules.agent.presentation.controllers.ask_agent_controller. Removal spec: 142."""
import warnings
warnings.warn("modules.runtime.presentation.controllers.ask_agent_controller is deprecated.", DeprecationWarning, stacklevel=2)
from modules.agent.presentation.controllers.ask_agent_controller import AskAgentController  # noqa: F401, E402
