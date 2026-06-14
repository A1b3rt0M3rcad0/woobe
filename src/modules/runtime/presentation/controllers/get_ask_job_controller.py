"""Deprecated: use modules.agent.presentation.controllers.get_ask_job_controller. Removal spec: 142."""
import warnings
warnings.warn("modules.runtime.presentation.controllers.get_ask_job_controller is deprecated.", DeprecationWarning, stacklevel=2)
from modules.agent.presentation.controllers.get_ask_job_controller import GetAskJobController  # noqa: F401, E402
