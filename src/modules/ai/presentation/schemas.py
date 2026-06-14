import warnings

warnings.warn(
    "modules.ai.presentation.schemas is deprecated. "
    "Use modules.agent.presentation.schemas instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.presentation.schemas import *  # noqa: F401, F403, E402
