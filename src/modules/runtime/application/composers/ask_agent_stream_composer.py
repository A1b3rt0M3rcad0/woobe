import warnings

warnings.warn(
    "modules.runtime.application.composers.ask_agent_stream_composer is deprecated. "
    "Use modules.agent.application.composers.ask_agent_stream_composer instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.application.composers.ask_agent_stream_composer import *  # noqa: E402, F401, F403
