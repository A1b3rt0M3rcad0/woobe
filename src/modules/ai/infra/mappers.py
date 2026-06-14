import warnings

warnings.warn(
    "modules.ai.infra.mappers is deprecated. "
    "Use modules.agent.infra.database.mappers instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.infra.database.mappers import *  # noqa: F401, F403, E402
