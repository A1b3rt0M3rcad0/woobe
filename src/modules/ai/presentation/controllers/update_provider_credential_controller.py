import warnings

warnings.warn(
    "modules.ai.presentation.controllers.update_provider_credential_controller is deprecated. "
    "Use modules.agent.presentation.controllers.update_provider_credential_controller instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.presentation.controllers.update_provider_credential_controller import UpdateProviderCredentialController  # noqa: F401, E402
