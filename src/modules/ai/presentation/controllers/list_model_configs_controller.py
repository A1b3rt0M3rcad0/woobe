import warnings

warnings.warn(
    "modules.ai.presentation.controllers.list_model_configs_controller is deprecated. "
    "Use modules.agent.presentation.controllers.list_model_configs_controller instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.presentation.controllers.list_model_configs_controller import ListModelConfigsController  # noqa: F401, E402
