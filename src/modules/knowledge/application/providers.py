from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from modules.knowledge.domain.repositories import (
    DocumentChunkRepository,
    DocumentCollectionRepository,
    DocumentRepository,
)
from modules.knowledge.infra.repositories import (
    SQLAlchemyDocumentChunkRepository,
    SQLAlchemyDocumentCollectionRepository,
    SQLAlchemyDocumentRepository,
)
from modules.knowledge.service.use_cases import (
    CreateCollectionUseCase,
    SearchChunksUseCase,
    UploadDocumentUseCase,
)


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
