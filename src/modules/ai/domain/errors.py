import warnings

warnings.warn(
    "modules.ai.domain.errors is deprecated. Use modules.agent.domain.errors instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.domain.errors import (  # noqa: E402, F401
    AgentNotFoundError,
    ContractNotFoundError,
    CredentialNotFoundError,
    ModelConfigNotFoundError,
    PromptNotFoundError,
    ReleaseNotFoundError,
    ReleaseTestNotFoundError,
)

__all__ = [
    "AgentNotFoundError",
    "ContractNotFoundError",
    "CredentialNotFoundError",
    "ModelConfigNotFoundError",
    "PromptNotFoundError",
    "ReleaseNotFoundError",
    "ReleaseTestNotFoundError",
]
