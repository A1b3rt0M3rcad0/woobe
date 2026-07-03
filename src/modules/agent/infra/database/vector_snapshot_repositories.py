from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from modules.agent.domain.vector_snapshot_entities import (
    VECTOR_SNAPSHOT_BUILDING,
    VECTOR_SNAPSHOT_FAILED,
    VECTOR_SNAPSHOT_READY,
    VectorSnapshot,
    VectorSnapshotChunk,
    VectorSnapshotDocument,
)
from modules.agent.infra.database.vector_snapshot_models import (
    VectorSnapshotChunkModel,
    VectorSnapshotDocumentModel,
    VectorSnapshotModel,
)
from shared.infra.config.interface.unit_of_work import UnitOfWork
from shared.infra.time import utc_now


def _snapshot_model_to_entity(model: VectorSnapshotModel) -> VectorSnapshot:
    return VectorSnapshot(
        id=model.id,
        project_id=model.project_id,
        collection_id=model.collection_id,
        version=model.version,
        description=model.description,
        status=model.status,
        embedding_provider_model_id=model.embedding_provider_model_id,
        embedding_provider=model.embedding_provider,
        embedding_model=model.embedding_model,
        embedding_dimensions=model.embedding_dimensions,
        chunk_size=model.chunk_size,
        chunk_overlap=model.chunk_overlap,
        chunking_strategy=model.chunking_strategy,
        parser_config=model.parser_config,
        snapshot_hash=model.snapshot_hash,
        document_count=model.document_count,
        chunk_count=model.chunk_count,
        error_message=model.error_message,
        created_by=model.created_by,
        started_at=model.started_at,
        completed_at=model.completed_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def _snapshot_entity_to_model(entity: VectorSnapshot) -> VectorSnapshotModel:
    return VectorSnapshotModel(
        id=entity.id,
        project_id=entity.project_id,
        collection_id=entity.collection_id,
        version=entity.version,
        description=entity.description,
        status=entity.status,
        embedding_provider_model_id=entity.embedding_provider_model_id,
        embedding_provider=entity.embedding_provider,
        embedding_model=entity.embedding_model,
        embedding_dimensions=entity.embedding_dimensions,
        chunk_size=entity.chunk_size,
        chunk_overlap=entity.chunk_overlap,
        chunking_strategy=entity.chunking_strategy,
        parser_config=entity.parser_config,
        snapshot_hash=entity.snapshot_hash,
        document_count=entity.document_count,
        chunk_count=entity.chunk_count,
        error_message=entity.error_message,
        created_by=entity.created_by,
        started_at=entity.started_at,
        completed_at=entity.completed_at,
    )


def _snapshot_document_to_model(entity: VectorSnapshotDocument) -> VectorSnapshotDocumentModel:
    return VectorSnapshotDocumentModel(
        id=entity.id,
        vector_snapshot_id=entity.vector_snapshot_id,
        document_id=entity.document_id,
        document_sha256=entity.document_sha256,
        document_title=entity.document_title,
        file_name=entity.file_name,
        parser=entity.parser,
        status_at_build=entity.status_at_build,
        chunk_count=entity.chunk_count,
    )


def _snapshot_chunk_to_model(entity: VectorSnapshotChunk) -> VectorSnapshotChunkModel:
    return VectorSnapshotChunkModel(
        id=entity.id,
        vector_snapshot_id=entity.vector_snapshot_id,
        project_id=entity.project_id,
        collection_id=entity.collection_id,
        document_id=entity.document_id,
        content=entity.content,
        content_hash=entity.content_hash,
        chunk_index=entity.chunk_index,
        token_count=entity.token_count,
        page_number=entity.page_number,
        section_title=entity.section_title,
        data=entity.data,
        embedding=entity.embedding,
    )


def _snapshot_chunk_model_to_entity(model: VectorSnapshotChunkModel) -> VectorSnapshotChunk:
    return VectorSnapshotChunk(
        id=model.id,
        vector_snapshot_id=model.vector_snapshot_id,
        project_id=model.project_id,
        collection_id=model.collection_id,
        document_id=model.document_id,
        content=model.content,
        content_hash=model.content_hash,
        chunk_index=model.chunk_index,
        token_count=model.token_count,
        page_number=model.page_number,
        section_title=model.section_title,
        data=model.data,
        embedding=model.embedding,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SQLAlchemyVectorSnapshotRepository:
    def __init__(self, session: AsyncSession | UnitOfWork) -> None:
        self._session_or_uow = session

    @property
    def _session(self) -> AsyncSession:
        if isinstance(self._session_or_uow, UnitOfWork):
            return self._session_or_uow.session
        return self._session_or_uow

    async def create(self, snapshot: VectorSnapshot) -> VectorSnapshot:
        model = _snapshot_entity_to_model(snapshot)
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return _snapshot_model_to_entity(model)

    async def get_by_id(self, snapshot_id: UUID) -> VectorSnapshot | None:
        model = await self._session.get(VectorSnapshotModel, snapshot_id)
        return _snapshot_model_to_entity(model) if model else None

    async def get_by_collection_version(
        self, project_id: UUID, collection_id: UUID, version: str
    ) -> VectorSnapshot | None:
        result = await self._session.execute(
            select(VectorSnapshotModel).where(
                VectorSnapshotModel.project_id == project_id,
                VectorSnapshotModel.collection_id == collection_id,
                VectorSnapshotModel.version == version,
            )
        )
        model = result.scalar_one_or_none()
        return _snapshot_model_to_entity(model) if model else None

    async def list_by_collection(self, project_id: UUID, collection_id: UUID) -> list[VectorSnapshot]:
        result = await self._session.execute(
            select(VectorSnapshotModel)
            .where(
                VectorSnapshotModel.project_id == project_id,
                VectorSnapshotModel.collection_id == collection_id,
                VectorSnapshotModel.status != "DELETED",
            )
            .order_by(VectorSnapshotModel.created_at.desc())
        )
        return [_snapshot_model_to_entity(model) for model in result.scalars().all()]

    async def list_building(self, limit: int = 3) -> list[VectorSnapshot]:
        result = await self._session.execute(
            select(VectorSnapshotModel)
            .where(
                VectorSnapshotModel.status == VECTOR_SNAPSHOT_BUILDING,
                VectorSnapshotModel.started_at.is_(None),
            )
            .order_by(VectorSnapshotModel.created_at.asc())
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        return [_snapshot_model_to_entity(model) for model in result.scalars().all()]

    async def mark_started(self, snapshot_id: UUID) -> None:
        model = await self._session.get(VectorSnapshotModel, snapshot_id)
        if model is None:
            return
        model.started_at = utc_now()
        model.error_message = None
        await self._session.flush()

    async def mark_ready(
        self,
        snapshot_id: UUID,
        *,
        snapshot_hash: str,
        document_count: int,
        chunk_count: int,
    ) -> VectorSnapshot | None:
        model = await self._session.get(VectorSnapshotModel, snapshot_id)
        if model is None:
            return None
        model.status = VECTOR_SNAPSHOT_READY
        model.snapshot_hash = snapshot_hash
        model.document_count = document_count
        model.chunk_count = chunk_count
        model.completed_at = utc_now()
        model.error_message = None
        await self._session.flush()
        await self._session.refresh(model)
        return _snapshot_model_to_entity(model)

    async def mark_failed(self, snapshot_id: UUID, error: str) -> None:
        model = await self._session.get(VectorSnapshotModel, snapshot_id)
        if model is None:
            return
        model.status = VECTOR_SNAPSHOT_FAILED
        model.error_message = error[:4000]
        model.completed_at = utc_now()
        await self._session.flush()

    async def add_snapshot_documents(self, documents: list[VectorSnapshotDocument]) -> None:
        self._session.add_all([_snapshot_document_to_model(document) for document in documents])
        await self._session.flush()

    async def add_snapshot_chunks(self, chunks: list[VectorSnapshotChunk]) -> None:
        self._session.add_all([_snapshot_chunk_to_model(chunk) for chunk in chunks])
        await self._session.flush()

    async def search_similar(
        self,
        *,
        vector_snapshot_id: UUID,
        embedding: list[float],
        limit: int = 10,
        threshold: float = 0.7,
    ) -> list[tuple[VectorSnapshotChunk, float]]:
        emb_str = "[" + ",".join(str(value) for value in embedding) + "]"
        stmt = text(
            """
            SELECT id, 1 - (embedding <=> :embedding::vector) AS similarity
            FROM agent.vector_snapshot_chunks
            WHERE vector_snapshot_id = :vector_snapshot_id
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
                "vector_snapshot_id": vector_snapshot_id,
                "threshold": threshold,
                "limit": limit,
            },
        )
        rows = result.fetchall()
        if not rows:
            return []
        chunk_ids = [row[0] for row in rows]
        similarity_map = {row[0]: row[1] for row in rows}
        chunks_result = await self._session.execute(
            select(VectorSnapshotChunkModel).where(VectorSnapshotChunkModel.id.in_(chunk_ids))
        )
        chunks = [_snapshot_chunk_model_to_entity(model) for model in chunks_result.scalars().all()]
        chunks.sort(key=lambda chunk: similarity_map.get(chunk.id, 0), reverse=True)
        return [(chunk, similarity_map.get(chunk.id, 0.0)) for chunk in chunks]
