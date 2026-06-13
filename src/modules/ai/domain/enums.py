import warnings

warnings.warn(
    "modules.ai.domain.enums is deprecated. Use modules.agent.domain.enums instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.domain.enums import (  # noqa: E402, F401
    AgentStatus,
    AgentType,
    ContractStatus,
    CredentialStatus,
    KnowledgeVersionStatus,
    ModelConfigStatus,
    PromptStatus,
    Provider,
    ReleaseStatus,
    ReleaseTestStatus,
    SessionMode,
    ValidationMode,
)

__all__ = [
    "AgentStatus",
    "AgentType",
    "ContractStatus",
    "CredentialStatus",
    "KnowledgeVersionStatus",
    "ModelConfigStatus",
    "PromptStatus",
    "Provider",
    "ReleaseStatus",
    "ReleaseTestStatus",
    "SessionMode",
    "ValidationMode",
]
