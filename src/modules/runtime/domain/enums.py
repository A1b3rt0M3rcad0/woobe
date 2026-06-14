import warnings

warnings.warn(
    "modules.runtime.domain.enums is deprecated. Use modules.agent.domain.enums instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.domain.enums import (  # noqa: E402, F401
    MessageRole,
    RuntimeSessionMode as SessionMode,
    SessionStatus,
)
