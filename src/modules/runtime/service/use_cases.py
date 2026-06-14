import warnings

warnings.warn(
    "modules.runtime.service.use_cases is deprecated. Use modules.agent.application.use_cases.runtime_use_cases instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.application.use_cases.runtime_use_cases import *  # noqa: E402, F401, F403
