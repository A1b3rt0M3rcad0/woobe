import warnings

warnings.warn(
    "modules.ai.application.composers.list_prompt_versions_composer is deprecated. "
    "Use modules.agent.application.composers.list_prompt_versions_composer instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.application.composers.list_prompt_versions_composer import list_prompt_versions_composer  # noqa: E402, F401

__all__ = ["list_prompt_versions_composer"]
