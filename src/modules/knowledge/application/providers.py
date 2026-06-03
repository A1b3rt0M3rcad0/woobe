from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from modules.knowledge.domain.repositories import (
    AgentCollectionRepository,
    DocumentChunkRepository,
    DocumentCollectionRepository,
    DocumentRepository,
)
from modules.knowledge.infra.repositories import (
    SQLAlchemyAgentCollectionRepository,
    SQLAlchemyDocumentChunkRepository,
    SQLAlchemyDocumentCollectionRepository,
    SQLAlchemyDocumentRepository,
)
from modules.knowledge.service.use_cases import (
    AttachCollectionUseCase,
    CreateCollectionUseCase,
    DetachCollectionUseCase,
    ListAgentCollectionsUseCase,
    SearchChunksUseCase,
    UploadDocumentUseCase,
)


def provide_list_agent_collections_uc(session: AsyncSession) -> ListAgentCollectionsUseCase:
    repo: AgentCollectionRepository = SQLAlchemyAgentCollectionRepository(session)
    return ListAgentCollectionsUseCase(repo)


def provide_attach_collection_uc(session: AsyncSession) -> AttachCollectionUseCase:
    repo: AgentCollectionRepository = SQLAlchemyAgentCollectionRepository(session)
    return AttachCollectionUseCase(session, repo)


def provide_detach_collection_uc(session: AsyncSession) -> DetachCollectionUseCase:
    repo: AgentCollectionRepository = SQLAlchemyAgentCollectionRepository(session)
    return DetachCollectionUseCase(repo)


def provide_create_collection_uc(session: AsyncSession) -> CreateCollectionUseCase:
    repo: DocumentCollectionRepository = SQLAlchemyDocumentCollectionRepository(session)
    return CreateCollectionUseCase(session, repo)


async def provide_get_collection(session: AsyncSession, collection_id: UUID):
    repo = SQLAlchemyDocumentCollectionRepository(session)
    return await repo.get_by_id(collection_id)


async def provide_get_document(session: AsyncSession, document_id: UUID):
    repo = SQLAlchemyDocumentRepository(session)
    return await repo.get_by_id(document_id)


def provide_search_chunks_uc(session: AsyncSession) -> SearchChunksUseCase:
    repo: DocumentChunkRepository = SQLAlchemyDocumentChunkRepository(session)
    return SearchChunksUseCase(repo)


def provide_upload_document_uc(session: AsyncSession) -> UploadDocumentUseCase:
    doc_repo: DocumentRepository = SQLAlchemyDocumentRepository(session)
    collection_repo: DocumentCollectionRepository = SQLAlchemyDocumentCollectionRepository(session)
    return UploadDocumentUseCase(session, doc_repo, collection_repo)
