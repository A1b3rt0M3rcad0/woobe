import warnings

warnings.warn(
    "modules.runtime.service.ask_use_case is deprecated. Use modules.agent.application.use_cases.ask_use_case instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.application.use_cases.ask_use_case import *  # noqa: E402, F401, F403
