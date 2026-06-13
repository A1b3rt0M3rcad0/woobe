import warnings

warnings.warn(
    "modules.ai.application.composers.list_provider_credentials_composer is deprecated. "
    "Use modules.agent.application.composers.list_provider_credentials_composer instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.application.composers.list_provider_credentials_composer import list_provider_credentials_composer  # noqa: E402, F401

__all__ = ["list_provider_credentials_composer"]
