import warnings

warnings.warn(
    "modules.knowledge.service.use_cases is deprecated. Use modules.agent.application.use_cases.knowledge_use_cases instead.",
    DeprecationWarning,
    stacklevel=2,
)

from modules.agent.application.use_cases.knowledge_use_cases import (  # noqa: E402, F401
    AttachCollectionUseCase,
    CreateCollectionUseCase,
    CreateKnowledgeVersionUseCase,
    DetachCollectionUseCase,
    GetCollectionUseCase,
    GetDocumentUseCase,
    ListAgentCollectionsUseCase,
    ListCollectionsUseCase,
    ListDocumentsUseCase,
    ListKnowledgeVersionsUseCase,
    SearchChunksUseCase,
    UploadDocumentUseCase,
)
