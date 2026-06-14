import warnings

warnings.warn(
    "modules.knowledge.domain.entities is deprecated. "
    "Use modules.agent.domain.entities instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.domain.entities import (  # noqa: F401, E402
    AgentCollection,
    Document,
    DocumentChunk,
    DocumentCollection,
    KnowledgeVersion,
)
