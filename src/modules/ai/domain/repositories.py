import warnings

warnings.warn(
    "modules.ai.domain.repositories is deprecated. Use modules.agent.domain.repositories instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.domain.repositories import (  # noqa: E402, F401
    AgentContractRepository,
    AgentModelConfigRepository,
    AgentPromptRepository,
    AgentReleaseRepository,
    AgentReleaseTestRepository,
    AgentRepository,
    ProviderCredentialRepository,
)

__all__ = [
    "AgentContractRepository",
    "AgentModelConfigRepository",
    "AgentPromptRepository",
    "AgentReleaseRepository",
    "AgentReleaseTestRepository",
    "AgentRepository",
    "ProviderCredentialRepository",
]
