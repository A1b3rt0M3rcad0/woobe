from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from modules.knowledge.domain.entities import Document, DocumentCollection
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
    repo = SQLAlchemyDocumentCollectionRepository(session)
    return CreateCollectionUseCase(session=session, repo=repo)


def provide_upload_document_uc(session: AsyncSession) -> UploadDocumentUseCase:
    doc_repo = SQLAlchemyDocumentRepository(session)
    collection_repo = SQLAlchemyDocumentCollectionRepository(session)
    return UploadDocumentUseCase(
        session=session, doc_repo=doc_repo, collection_repo=collection_repo
    )


def provide_search_chunks_uc(session: AsyncSession) -> SearchChunksUseCase:
    repo = SQLAlchemyDocumentChunkRepository(session)
    return SearchChunksUseCase(repo=repo)


async def provide_get_collection(
    session: AsyncSession, collection_id: UUID
) -> DocumentCollection:
    repo = SQLAlchemyDocumentCollectionRepository(session)
    return await repo.get_by_id(collection_id)


async def provide_get_document(
    session: AsyncSession, document_id: UUID
) -> Document:
    repo = SQLAlchemyDocumentRepository(session)
    return await repo.get_by_id(document_id)

