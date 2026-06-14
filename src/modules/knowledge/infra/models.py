import warnings

warnings.warn(
    "modules.knowledge.infra.models is deprecated. Use modules.agent.infra.database.models instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.infra.database.models import (  # noqa: E402, F401
    AgentCollectionModel,
    DocumentChunkModel,
    DocumentCollectionModel,
    DocumentModel,
    KnowledgeOutboxEventModel as OutboxEventModel,
    KnowledgeInboxEventModel as InboxEventModel,
    KnowledgeVersionModel,
)
