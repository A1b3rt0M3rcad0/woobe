import warnings

warnings.warn(
    "modules.ai.presentation.controllers.update_contract_version_controller is deprecated. "
    "Use modules.agent.presentation.controllers.update_contract_version_controller instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.presentation.controllers.update_contract_version_controller import UpdateContractVersionController  # noqa: F401, E402
