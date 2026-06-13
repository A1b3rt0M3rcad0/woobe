import warnings

warnings.warn(
    "modules.ai.application.composers.update_provider_credential_composer is deprecated. "
    "Use modules.agent.application.composers.update_provider_credential_composer instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.application.composers.update_provider_credential_composer import update_provider_credential_composer  # noqa: E402, F401

__all__ = ["update_provider_credential_composer"]
