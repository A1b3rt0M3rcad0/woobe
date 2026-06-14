import warnings

warnings.warn(
    "modules.knowledge.service.dtos is deprecated. Use modules.agent.application.dtos.knowledge_dtos instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.application.dtos.knowledge_dtos import (  # noqa: E402, F401
    AgentCollectionOutput,
    AttachCollectionInput,
    AttachCollectionOutput,
    CreateCollectionInput,
    CreateCollectionOutput,
    CreateKnowledgeVersionInput,
    CreateKnowledgeVersionOutput,
    DocumentChunkOutput,
    GetCollectionInput,
    GetDocumentInput,
    ListCollectionsInput,
    ListDocumentsInput,
    ListKnowledgeVersionsOutput,
    SearchChunksInput,
    SearchChunksOutput,
    UploadDocumentInput,
    UploadDocumentOutput,
)
