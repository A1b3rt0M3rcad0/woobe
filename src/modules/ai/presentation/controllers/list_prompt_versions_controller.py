import warnings

warnings.warn(
    "modules.ai.presentation.controllers.list_prompt_versions_controller is deprecated. "
    "Use modules.agent.presentation.controllers.list_prompt_versions_controller instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.presentation.controllers.list_prompt_versions_controller import ListPromptVersionsController  # noqa: F401, E402
