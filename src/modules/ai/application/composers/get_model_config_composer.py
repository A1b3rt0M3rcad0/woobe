import warnings

warnings.warn(
    "modules.ai.application.composers.get_model_config_composer is deprecated. "
    "Use modules.agent.application.composers.get_model_config_composer instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.application.composers.get_model_config_composer import get_model_config_composer  # noqa: E402, F401

__all__ = ["get_model_config_composer"]
