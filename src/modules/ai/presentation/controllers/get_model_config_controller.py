import warnings

warnings.warn(
    "modules.ai.presentation.controllers.get_model_config_controller is deprecated. "
    "Use modules.agent.presentation.controllers.get_model_config_controller instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.presentation.controllers.get_model_config_controller import GetModelConfigController  # noqa: F401, E402
