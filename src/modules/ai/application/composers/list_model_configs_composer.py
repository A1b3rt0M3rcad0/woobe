import warnings

warnings.warn(
    "modules.ai.application.composers.list_model_configs_composer is deprecated. "
    "Use modules.agent.application.composers.list_model_configs_composer instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.application.composers.list_model_configs_composer import list_model_configs_composer  # noqa: E402, F401

__all__ = ["list_model_configs_composer"]
