import warnings

warnings.warn(
    "modules.ai.application.composers.create_contract_version_composer is deprecated. "
    "Use modules.agent.application.composers.create_contract_version_composer instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.application.composers.create_contract_version_composer import create_contract_version_composer  # noqa: E402, F401

__all__ = ["create_contract_version_composer"]
