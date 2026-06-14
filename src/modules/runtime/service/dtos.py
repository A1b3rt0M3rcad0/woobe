import warnings

warnings.warn(
    "modules.runtime.service.dtos is deprecated. Use modules.agent.application.dtos.runtime_dtos instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.application.dtos.runtime_dtos import *  # noqa: E402, F401, F403
