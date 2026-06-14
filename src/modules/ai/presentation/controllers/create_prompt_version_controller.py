import warnings

warnings.warn(
    "modules.ai.presentation.controllers.create_prompt_version_controller is deprecated. "
    "Use modules.agent.presentation.controllers.create_prompt_version_controller instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.presentation.controllers.create_prompt_version_controller import CreatePromptVersionController  # noqa: F401, E402
