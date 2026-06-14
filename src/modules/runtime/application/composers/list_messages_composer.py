import warnings

warnings.warn(
    "modules.runtime.application.composers.list_messages_composer is deprecated. "
    "Use modules.agent.application.composers.list_messages_composer instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.application.composers.list_messages_composer import *  # noqa: E402, F401, F403
