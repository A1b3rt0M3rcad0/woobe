import warnings

warnings.warn(
    "modules.knowledge.domain.repositories is deprecated. "
    "Use modules.agent.domain.repositories instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.domain.repositories import (  # noqa: F401, E402
    AgentCollectionRepository,
    DocumentChunkRepository,
    DocumentCollectionRepository,
    DocumentRepository,
    KnowledgeVersionRepository,
)
