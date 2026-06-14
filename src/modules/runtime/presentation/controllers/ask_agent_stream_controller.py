"""Deprecated: use modules.agent.presentation.controllers.ask_agent_stream_controller. Removal spec: 142."""
import warnings
warnings.warn("modules.runtime.presentation.controllers.ask_agent_stream_controller is deprecated.", DeprecationWarning, stacklevel=2)
from modules.agent.presentation.controllers.ask_agent_stream_controller import handle_ask_stream  # noqa: F401, E402
