import warnings

warnings.warn(
    "modules.ai.domain.entities is deprecated. Use modules.agent.domain.entities instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.domain.entities import (  # noqa: E402, F401
    Agent,
    AgentContract,
    AgentModelConfig,
    AgentPrompt,
    AgentRelease,
    AgentReleaseTest,
    ProviderCredential,
)

__all__ = [
    "Agent",
    "AgentContract",
    "AgentModelConfig",
    "AgentPrompt",
    "AgentRelease",
    "AgentReleaseTest",
    "ProviderCredential",
]
