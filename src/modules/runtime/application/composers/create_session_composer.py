import warnings

warnings.warn(
    "modules.runtime.application.composers.create_session_composer is deprecated. "
    "Use modules.agent.application.composers.create_session_composer instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.application.composers.create_session_composer import *  # noqa: E402, F401, F403
