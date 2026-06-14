import warnings

warnings.warn(
    "modules.runtime.service.ask_agent_stream_service is deprecated. Use modules.agent.application.use_cases.ask_agent_stream_service instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.application.use_cases.ask_agent_stream_service import *  # noqa: E402, F401, F403
