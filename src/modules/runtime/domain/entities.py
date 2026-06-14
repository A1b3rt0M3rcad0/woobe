import warnings

warnings.warn(
    "modules.runtime.domain.entities is deprecated. Use modules.agent.domain.entities instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.domain.entities import (  # noqa: E402, F401
    AskJob,
    Message,
    Session,
)
