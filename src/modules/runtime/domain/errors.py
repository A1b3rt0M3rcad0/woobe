import warnings

warnings.warn(
    "modules.runtime.domain.errors is deprecated. Use modules.agent.domain.errors instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.domain.errors import (  # noqa: E402, F401
    AskJobNotFoundError,
    MessageNotFoundError,
    SessionNotFoundError,
)
