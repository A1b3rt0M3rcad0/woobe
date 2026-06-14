import warnings

warnings.warn(
    "modules.ai.infra.repositories is deprecated. "
    "Use modules.agent.infra.database.repositories instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.infra.database.repositories import *  # noqa: F401, F403, E402
