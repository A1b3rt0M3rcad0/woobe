import warnings

warnings.warn(
    "modules.ai.presentation.controllers.get_prompt_version_controller is deprecated. "
    "Use modules.agent.presentation.controllers.get_prompt_version_controller instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.presentation.controllers.get_prompt_version_controller import GetPromptVersionController  # noqa: F401, E402
