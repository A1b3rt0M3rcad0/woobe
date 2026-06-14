import warnings

warnings.warn(
    "modules.knowledge.infra.repositories is deprecated. Use modules.agent.infra.database.repositories instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.infra.database.repositories import (  # noqa: E402, F401
    SQLAlchemyAgentCollectionRepository,
    SQLAlchemyDocumentChunkRepository,
    SQLAlchemyDocumentCollectionRepository,
    SQLAlchemyDocumentRepository,
    SQLAlchemyKnowledgeOutboxEventWriter as SQLAlchemyOutboxEventWriter,
    SQLAlchemyKnowledgeVersionRepository,
)
