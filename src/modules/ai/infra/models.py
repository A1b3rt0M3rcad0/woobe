import warnings

warnings.warn(
    "modules.ai.infra.models is deprecated. "
    "Use modules.agent.infra.database.models instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.infra.database.models import *  # noqa: F401, F403, E402
