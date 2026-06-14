import warnings

warnings.warn(
    "modules.knowledge.domain.errors is deprecated. "
    "Use modules.agent.domain.errors instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.domain.errors import (  # noqa: F401, E402
    ChunkNotFoundError,
    CollectionNotFoundError,
    DocumentNotFoundError,
    DuplicateCollectionError,
    KnowledgeVersionNotFoundError,
)
