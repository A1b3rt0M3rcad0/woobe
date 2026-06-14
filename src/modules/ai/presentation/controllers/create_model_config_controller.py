import warnings

warnings.warn(
    "modules.ai.presentation.controllers.create_model_config_controller is deprecated. "
    "Use modules.agent.presentation.controllers.create_model_config_controller instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.presentation.controllers.create_model_config_controller import CreateModelConfigController  # noqa: F401, E402
