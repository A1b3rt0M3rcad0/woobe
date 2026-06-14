"""Deprecated: use modules.agent.presentation.controllers.send_message_controller. Removal spec: 142."""
import warnings
warnings.warn("modules.runtime.presentation.controllers.send_message_controller is deprecated.", DeprecationWarning, stacklevel=2)
from modules.agent.presentation.controllers.send_message_controller import SendMessageController  # noqa: F401, E402
