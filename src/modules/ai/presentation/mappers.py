import warnings

warnings.warn(
    "modules.ai.presentation.mappers is deprecated. "
    "Use modules.agent.presentation.mappers instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.presentation.mappers import *  # noqa: F401, F403, E402
