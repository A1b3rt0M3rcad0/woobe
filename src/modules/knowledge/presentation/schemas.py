import warnings

warnings.warn(
    "modules.knowledge.presentation.schemas is deprecated. Use modules.agent.presentation.schemas instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.presentation.schemas import (  # noqa: E402, F401
    AgentCollectionResponse,
    AttachCollectionRequest,
    ChunkResponse,
    CollectionResponse,
    CreateCollectionRequest,
    CreateKnowledgeVersionRequest,
    DocumentResponse,
    KnowledgeVersionResponse,
    ListKnowledgeVersionsResponse,
    SearchRequest,
    UploadDocumentRequest,
)
