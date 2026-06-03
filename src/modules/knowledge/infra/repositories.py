from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from modules.knowledge.domain.entities import (
    AgentCollection,
    Document,
    DocumentChunk,
    DocumentCollection,
)
from modules.knowledge.domain.errors import (
    ChunkNotFoundError,
    CollectionNotFoundError,
    DocumentNotFoundError,
)
from modules.knowledge.domain.repositories import (
    AgentCollectionRepository,
    DocumentChunkRepository,
    DocumentCollectionRepository,
    DocumentRepository,
)
from modules.knowledge.infra.mappers import (
    agent_collection_model_to_entity,
    agent_collection_to_model,
    chunk_to_model,
    collection_to_model,
    document_to_model,
    model_to_chunk,
    model_to_collection,
    model_to_document,
)
from modules.knowledge.infra.models import (
    AgentCollectionModel,
    DocumentChunkModel,
    DocumentCollectionModel,
    DocumentModel,
    OutboxEventModel,
)
from shared.domain.events import OutboxEventWriter
from shared.domain.objects import CursorPage
from shared.infra.repositories.base_repository import BaseSQLAlchemyRepository


class SQLAlchemyAgentCollectionRepository(AgentCollectionRepository):

    def __init__(self, session: AsyncSession) -> None:
        self._base = BaseSQLAlchemyRepository(session, AgentCollectionModel)
        self._session = session

    async def list_by_agent(self, agent_id: UUID) -> list[AgentCollection]:
        # TODO: Remove after pagination migration
        stmt = (
            select(AgentCollectionModel)
            .where(AgentCollectionModel.agent_id == agent_id)
            .order_by(AgentCollectionModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return [agent_collection_model_to_entity(m) for m in result.scalars().all()]

    async def paginate_by_agent(
        self, agent_id: UUID, *, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[AgentCollection]:
        stmt = (
            select(AgentCollectionModel)
            .where(AgentCollectionModel.agent_id == agent_id)
            .order_by(AgentCollectionModel.id.desc())
        )
        page = await self._base._paginate_models(stmt, limit=limit, cursor=cursor)
        return CursorPage(
            items=[agent_collection_model_to_entity(m) for m in page.items],
            cursor=page.cursor,
            next_cursor=page.next_cursor,
            has_next=page.has_next,
            total=page.total,
        )

    async def get_by_agent_and_collection(
        self, agent_id: UUID, collection_id: UUID
    ) -> AgentCollection | None:
        stmt = select(AgentCollectionModel).where(
            AgentCollectionModel.agent_id == agent_id,
            AgentCollectionModel.collection_id == collection_id,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return agent_collection_model_to_entity(model) if model else None

    async def create(self, link: AgentCollection) -> AgentCollection:
        model = agent_collection_to_model(link)
        await self._base._add_model(model)
        await self._base._flush()
        await self._base._refresh_model(model)
        return agent_collection_model_to_entity(model)

    async def delete(self, link_id: UUID) -> None:
        model = await self._base._get_model_by_id(link_id)
        if model is None:
            raise CollectionNotFoundError(link_id)
        await self._base._delete_model(model)


class SQLAlchemyDocumentCollectionRepository(DocumentCollectionRepository):

    def __init__(self, session: AsyncSession) -> None:
        self._base = BaseSQLAlchemyRepository(session, DocumentCollectionModel)
        self._session = session

    async def create(self, collection: DocumentCollection) -> DocumentCollection:
        model = collection_to_model(collection)
        await self._base._add_model(model)
        await self._base._flush()
        await self._base._refresh_model(model)
        return model_to_collection(model)

    async def get_by_id(self, collection_id: UUID) -> DocumentCollection:
        model = await self._base._get_model_by_id(collection_id)
        if model is None:
            raise CollectionNotFoundError(collection_id)
        return model_to_collection(model)

    async def list_by_project(
        self, project_id: UUID, status: str | None = None
    ) -> list[DocumentCollection]:
        # TODO: Remove after pagination migration
        stmt = select(DocumentCollectionModel).where(
            DocumentCollectionModel.project_id == project_id
        )
        if status:
            stmt = stmt.where(DocumentCollectionModel.status == status)
        stmt = stmt.order_by(DocumentCollectionModel.created_at.desc())
        result = await self._session.execute(stmt)
        return [model_to_collection(m) for m in result.scalars().all()]

    async def paginate_by_project(
        self, project_id: UUID, *, status: str | None = None, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[DocumentCollection]:
        stmt = select(DocumentCollectionModel).where(
            DocumentCollectionModel.project_id == project_id
        )
        if status:
            stmt = stmt.where(DocumentCollectionModel.status == status)
        stmt = stmt.order_by(DocumentCollectionModel.id.desc())
        page = await self._base._paginate_models(stmt, limit=limit, cursor=cursor)
        return CursorPage(
            items=[model_to_collection(m) for m in page.items],
            cursor=page.cursor,
            next_cursor=page.next_cursor,
            has_next=page.has_next,
            total=page.total,
        )

    async def update(self, collection: DocumentCollection) -> DocumentCollection:
        model = await self._base._get_model_by_id(collection.id)
        if model is None:
            raise CollectionNotFoundError(collection.id)
        model.name = collection.name
        model.description = collection.description
        model.status = collection.status
        return model_to_collection(model)

    async def delete(self, collection_id: UUID) -> None:
        model = await self._base._get_model_by_id(collection_id)
        if model is None:
            raise CollectionNotFoundError(collection_id)
        await self._base._delete_model(model)


class SQLAlchemyDocumentRepository(DocumentRepository):

    def __init__(self, session: AsyncSession) -> None:
        self._base = BaseSQLAlchemyRepository(session, DocumentModel)
        self._session = session

    async def create(self, document: Document) -> Document:
        model = document_to_model(document)
        await self._base._add_model(model)
        await self._base._flush()
        await self._base._refresh_model(model)
        return model_to_document(model)

    async def get_by_id(self, document_id: UUID) -> Document:
        model = await self._base._get_model_by_id(document_id)
        if model is None:
            raise DocumentNotFoundError(document_id)
        return model_to_document(model)

    async def list_by_collection(
        self, collection_id: UUID, status: str | None = None
    ) -> list[Document]:
        # TODO: Remove after pagination migration
        stmt = select(DocumentModel).where(
            DocumentModel.collection_id == collection_id
        )
        if status:
            stmt = stmt.where(DocumentModel.status == status)
        stmt = stmt.order_by(DocumentModel.created_at.desc())
        result = await self._session.execute(stmt)
        return [model_to_document(m) for m in result.scalars().all()]

    async def paginate_by_collection(
        self, collection_id: UUID, *, status: str | None = None, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[Document]:
        stmt = select(DocumentModel).where(
            DocumentModel.collection_id == collection_id
        )
        if status:
            stmt = stmt.where(DocumentModel.status == status)
        stmt = stmt.order_by(DocumentModel.id.desc())
        page = await self._base._paginate_models(stmt, limit=limit, cursor=cursor)
        return CursorPage(
            items=[model_to_document(m) for m in page.items],
            cursor=page.cursor,
            next_cursor=page.next_cursor,
            has_next=page.has_next,
            total=page.total,
        )

    async def update(self, document: Document) -> Document:
        model = await self._base._get_model_by_id(document.id)
        if model is None:
            raise DocumentNotFoundError(document.id)
        model.title = document.title
        model.file_name = document.file_name
        model.content_type = document.content_type
        model.size_bytes = document.size_bytes
        model.storage_key = document.storage_key
        model.parser = document.parser
        model.status = document.status
        model.error = document.error
        model.page_count = document.page_count
        model.chunk_count = document.chunk_count
        model.sha256 = document.sha256
        model.indexed_at = document.indexed_at
        return model_to_document(model)

    async def delete(self, document_id: UUID) -> None:
        model = await self._base._get_model_by_id(document_id)
        if model is None:
            raise DocumentNotFoundError(document_id)
        await self._base._delete_model(model)


class SQLAlchemyDocumentChunkRepository(DocumentChunkRepository):

    def __init__(self, session: AsyncSession) -> None:
        self._base = BaseSQLAlchemyRepository(session, DocumentChunkModel)
        self._session = session

    async def create_many(self, chunks: list[DocumentChunk]) -> list[DocumentChunk]:
        models = [chunk_to_model(c) for c in chunks]
        for m in models:
            await self._base._add_model(m)
        return [model_to_chunk(m) for m in models]

    async def get_by_id(self, chunk_id: UUID) -> DocumentChunk:
        model = await self._base._get_model_by_id(chunk_id)
        if model is None:
            raise ChunkNotFoundError(chunk_id)
        return model_to_chunk(model)

    async def list_by_document(
        self, document_id: UUID, offset: int = 0, limit: int = 100
    ) -> list[DocumentChunk]:
        # TODO: Remove after pagination migration
        stmt = (
            select(DocumentChunkModel)
            .where(DocumentChunkModel.document_id == document_id)
            .order_by(DocumentChunkModel.chunk_index)
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [model_to_chunk(m) for m in result.scalars().all()]

    async def paginate_by_document(
        self, document_id: UUID, *, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[DocumentChunk]:
        stmt = (
            select(DocumentChunkModel)
            .where(DocumentChunkModel.document_id == document_id)
            .order_by(DocumentChunkModel.id.desc())
        )
        page = await self._base._paginate_models(stmt, limit=limit, cursor=cursor)
        return CursorPage(
            items=[model_to_chunk(m) for m in page.items],
            cursor=page.cursor,
            next_cursor=page.next_cursor,
            has_next=page.has_next,
            total=page.total,
        )

    async def delete_by_document(self, document_id: UUID) -> None:
        stmt = select(DocumentChunkModel).where(
            DocumentChunkModel.document_id == document_id
        )
        result = await self._session.execute(stmt)
        for model in result.scalars().all():
            await self._base._delete_model(model)

    async def search_similar(
        self,
        embedding: list[float],
        collection_id: UUID,
        limit: int = 10,
        threshold: float = 0.7,
    ) -> list[tuple[DocumentChunk, float]]:
        emb_str = "[" + ",".join(str(v) for v in embedding) + "]"
        stmt = text(
            """
            SELECT id, 1 - (embedding <=> :embedding::vector) AS similarity
            FROM knowledge.document_chunks
            WHERE collection_id = :collection_id
              AND embedding IS NOT NULL
              AND 1 - (embedding <=> :embedding::vector) >= :threshold
            ORDER BY similarity DESC
            LIMIT :limit
            """
        )
        result = await self._session.execute(
            stmt,
            {
                "embedding": emb_str,
                "collection_id": collection_id,
                "threshold": threshold,
                "limit": limit,
            },
        )
        rows = result.fetchall()
        if not rows:
            return []

        chunk_ids = [row[0] for row in rows]
        similarity_map = {row[0]: row[1] for row in rows}

        chunks_stmt = select(DocumentChunkModel).where(
            DocumentChunkModel.id.in_(chunk_ids)
        )
        chunks_result = await self._session.execute(chunks_stmt)
        chunks = [model_to_chunk(m) for m in chunks_result.scalars().all()]
        chunks.sort(key=lambda c: similarity_map.get(c.id, 0), reverse=True)
        return [(c, similarity_map.get(c.id, 0.0)) for c in chunks]


class SQLAlchemyOutboxEventWriter(OutboxEventWriter):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def write(
        self,
        aggregate_type: str,
        aggregate_id: UUID,
        event_type: str,
        payload: dict[str, Any] | None = None,
        correlation_id: UUID | None = None,
        causation_id: UUID | None = None,
    ) -> None:
        event = OutboxEventModel(
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            event_type=event_type,
            payload=payload or {},
            correlation_id=correlation_id,
            causation_id=causation_id,
        )
        self._session.add(event)

