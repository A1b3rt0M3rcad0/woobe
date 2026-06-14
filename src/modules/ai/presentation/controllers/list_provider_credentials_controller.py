import warnings

warnings.warn(
    "modules.ai.presentation.controllers.list_provider_credentials_controller is deprecated. "
    "Use modules.agent.presentation.controllers.list_provider_credentials_controller instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.presentation.controllers.list_provider_credentials_controller import ListProviderCredentialsController  # noqa: F401, E402
