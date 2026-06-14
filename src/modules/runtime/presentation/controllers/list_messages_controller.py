"""Deprecated: use modules.agent.presentation.controllers.list_messages_controller. Removal spec: 142."""
import warnings
warnings.warn("modules.runtime.presentation.controllers.list_messages_controller is deprecated.", DeprecationWarning, stacklevel=2)
from modules.agent.presentation.controllers.list_messages_controller import ListMessagesController  # noqa: F401, E402
