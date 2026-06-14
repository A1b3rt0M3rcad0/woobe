import warnings

warnings.warn(
    "modules.runtime.domain.repositories is deprecated. Use modules.agent.domain.repositories instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.domain.repositories import (  # noqa: E402, F401
    AskJobRepository,
    MessageRepository,
    SessionRepository,
)
