import warnings

warnings.warn(
    "modules.ai.presentation.controllers.create_contract_version_controller is deprecated. "
    "Use modules.agent.presentation.controllers.create_contract_version_controller instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.presentation.controllers.create_contract_version_controller import CreateContractVersionController  # noqa: F401, E402
