from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from modules.agent.application.interfaces.vector_snapshot_repository import (
    VectorSnapshotRepository,
)
from modules.agent.domain.vector_snapshot_entities import (
    VECTOR_SNAPSHOT_BUILDING,
    VECTOR_SNAPSHOT_FAILED,
    VECTOR_SNAPSHOT_READY,
    VECTOR_SNAPSHOT_STAGE_FAILED,
    VECTOR_SNAPSHOT_STAGE_PARSING,
    VECTOR_SNAPSHOT_STAGE_READY,
    VectorSnapshot,
    VectorSnapshotChunk,
    VectorSnapshotDocument,
)
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.infra.database.vector_snapshot_models import (
    VectorSnapshotChunkModel,
    VectorSnapshotDocumentModel,
    VectorSnapshotModel,
)
from shared.contracts.time import utc_now


def _snapshot_model_to_entity(model: VectorSnapshotModel) -> VectorSnapshot:
    return VectorSnapshot(
        id=model.id,
        project_id=model.project_id,
        collection_id=model.collection_id,
        version=model.version,
        description=model.description,
        status=model.status,
        build_stage=model.build_stage,
        embedding_provider_model_id=model.embedding_provider_model_id,
        embedding_provider=model.embedding_provider,
        embedding_model=model.embedding_model,
        embedding_dimensions=model.embedding_dimensions,
        chunk_size=model.chunk_size,
        chunk_overlap=model.chunk_overlap,
        chunking_strategy=model.chunking_strategy,
        parser_config=model.parser_config,
        build_config=model.build_config,
        snapshot_hash=model.snapshot_hash,
        build_config_hash=model.build_config_hash,
        document_count=model.document_count,
        chunk_count=model.chunk_count,
        vector_count=model.vector_count,
        total_document_count=model.total_document_count,
        processed_document_count=model.processed_document_count,
        total_chunk_count=model.total_chunk_count,
        processed_chunk_count=model.processed_chunk_count,
        embedded_chunk_count=model.embedded_chunk_count,
        current_document_id=model.current_document_id,
        locked_at=model.locked_at,
        locked_by=model.locked_by,
        attempt_count=model.attempt_count,
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
        build_stage=entity.build_stage,
        embedding_provider_model_id=entity.embedding_provider_model_id,
        embedding_provider=entity.embedding_provider,
        embedding_model=entity.embedding_model,
        embedding_dimensions=entity.embedding_dimensions,
        chunk_size=entity.chunk_size,
        chunk_overlap=entity.chunk_overlap,
        chunking_strategy=entity.chunking_strategy,
        parser_config=entity.parser_config,
        build_config=entity.build_config,
        snapshot_hash=entity.snapshot_hash,
        build_config_hash=entity.build_config_hash,
        document_count=entity.document_count,
        chunk_count=entity.chunk_count,
        vector_count=entity.vector_count,
        total_document_count=entity.total_document_count,
        processed_document_count=entity.processed_document_count,
        total_chunk_count=entity.total_chunk_count,
        processed_chunk_count=entity.processed_chunk_count,
        embedded_chunk_count=entity.embedded_chunk_count,
        current_document_id=entity.current_document_id,
        locked_at=entity.locked_at,
        locked_by=entity.locked_by,
        attempt_count=entity.attempt_count,
        error_message=entity.error_message,
        created_by=entity.created_by,
        started_at=entity.started_at,
        completed_at=entity.completed_at,
    )


def _snapshot_document_to_model(
    entity: VectorSnapshotDocument,
) -> VectorSnapshotDocumentModel:
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


def _snapshot_document_model_to_entity(
    model: VectorSnapshotDocumentModel,
) -> VectorSnapshotDocument:
    return VectorSnapshotDocument(
        id=model.id,
        vector_snapshot_id=model.vector_snapshot_id,
        document_id=model.document_id,
        document_sha256=model.document_sha256,
        document_title=model.document_title,
        file_name=model.file_name,
        parser=model.parser,
        status_at_build=model.status_at_build,
        chunk_count=model.chunk_count,
        created_at=model.created_at,
        updated_at=model.updated_at,
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


def _snapshot_chunk_model_to_entity(
    model: VectorSnapshotChunkModel,
) -> VectorSnapshotChunk:
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


class SQLAlchemyVectorSnapshotRepository(VectorSnapshotRepository):
    def __init__(self, uow: AgentUnitOfWork) -> None:
        self._uow = uow

    @property
    def _session(self) -> AsyncSession:
        return self._uow.session

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

    async def get_active_building_by_collection(
        self, project_id: UUID, collection_id: UUID
    ) -> VectorSnapshot | None:
        result = await self._session.execute(
            select(VectorSnapshotModel)
            .where(
                VectorSnapshotModel.project_id == project_id,
                VectorSnapshotModel.collection_id == collection_id,
                VectorSnapshotModel.status == VECTOR_SNAPSHOT_BUILDING,
            )
            .order_by(VectorSnapshotModel.created_at.desc())
            .limit(1)
        )
        model = result.scalar_one_or_none()
        return _snapshot_model_to_entity(model) if model else None

    async def list_by_collection(
        self,
        project_id: UUID,
        collection_id: UUID,
    ) -> list[VectorSnapshot]:
        result = await self._session.execute(
            select(VectorSnapshotModel)
            .where(
                VectorSnapshotModel.project_id == project_id,
                VectorSnapshotModel.collection_id == collection_id,
                VectorSnapshotModel.status != "DELETED",
            )
            .order_by(VectorSnapshotModel.created_at.desc())
        )
        return [
            _snapshot_model_to_entity(model) for model in result.scalars().all()
        ]

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
        return [
            _snapshot_model_to_entity(model) for model in result.scalars().all()
        ]

    async def mark_started(
        self,
        snapshot_id: UUID,
        *,
        locked_by: str | None = None,
    ) -> None:
        model = await self._session.get(VectorSnapshotModel, snapshot_id)
        if model is None:
            return
        now = utc_now()
        model.started_at = model.started_at or now
        model.locked_at = now
        model.locked_by = locked_by
        model.attempt_count = (model.attempt_count or 0) + 1
        model.build_stage = VECTOR_SNAPSHOT_STAGE_PARSING
        model.error_message = None
        await self._session.flush()

    async def update_build_progress(
        self,
        snapshot_id: UUID,
        *,
        build_stage: str | None = None,
        total_document_count: int | None = None,
        processed_document_count: int | None = None,
        total_chunk_count: int | None = None,
        processed_chunk_count: int | None = None,
        embedded_chunk_count: int | None = None,
        current_document_id: UUID | None = None,
    ) -> None:
        model = await self._session.get(VectorSnapshotModel, snapshot_id)
        if model is None:
            return
        if build_stage is not None:
            model.build_stage = build_stage
        if total_document_count is not None:
            model.total_document_count = total_document_count
        if processed_document_count is not None:
            model.processed_document_count = processed_document_count
        if total_chunk_count is not None:
            model.total_chunk_count = total_chunk_count
        if processed_chunk_count is not None:
            model.processed_chunk_count = processed_chunk_count
        if embedded_chunk_count is not None:
            model.embedded_chunk_count = embedded_chunk_count
        model.current_document_id = current_document_id
        await self._session.flush()

    async def mark_ready(
        self,
        snapshot_id: UUID,
        *,
        snapshot_hash: str,
        document_count: int,
        chunk_count: int,
        vector_count: int | None = None,
    ) -> VectorSnapshot | None:
        model = await self._session.get(VectorSnapshotModel, snapshot_id)
        if model is None:
            return None
        model.status = VECTOR_SNAPSHOT_READY
        model.build_stage = VECTOR_SNAPSHOT_STAGE_READY
        model.snapshot_hash = snapshot_hash
        model.document_count = document_count
        model.chunk_count = chunk_count
        model.vector_count = vector_count if vector_count is not None else chunk_count
        model.total_document_count = document_count
        model.processed_document_count = document_count
        model.total_chunk_count = chunk_count
        model.processed_chunk_count = chunk_count
        model.embedded_chunk_count = model.vector_count
        model.completed_at = utc_now()
        model.locked_at = None
        model.locked_by = None
        model.current_document_id = None
        model.error_message = None
        await self._session.flush()
        await self._session.refresh(model)
        return _snapshot_model_to_entity(model)

    async def mark_failed(self, snapshot_id: UUID, error: str) -> None:
        model = await self._session.get(VectorSnapshotModel, snapshot_id)
        if model is None:
            return
        model.status = VECTOR_SNAPSHOT_FAILED
        model.build_stage = VECTOR_SNAPSHOT_STAGE_FAILED
        model.error_message = error[:4000]
        model.completed_at = utc_now()
        model.locked_at = None
        model.locked_by = None
        await self._session.flush()

    async def add_snapshot_documents(
        self,
        documents: list[VectorSnapshotDocument],
    ) -> None:
        self._session.add_all(
            [_snapshot_document_to_model(document) for document in documents]
        )
        await self._session.flush()

    async def list_snapshot_documents(
        self,
        snapshot_id: UUID,
    ) -> list[VectorSnapshotDocument]:
        result = await self._session.execute(
            select(VectorSnapshotDocumentModel)
            .where(VectorSnapshotDocumentModel.vector_snapshot_id == snapshot_id)
            .order_by(VectorSnapshotDocumentModel.created_at.asc())
        )
        return [
            _snapshot_document_model_to_entity(model)
            for model in result.scalars().all()
        ]

    async def update_snapshot_document_chunk_count(
        self,
        snapshot_id: UUID,
        document_id: UUID,
        chunk_count: int,
    ) -> None:
        await self._session.execute(
            update(VectorSnapshotDocumentModel)
            .where(
                VectorSnapshotDocumentModel.vector_snapshot_id == snapshot_id,
                VectorSnapshotDocumentModel.document_id == document_id,
            )
            .values(chunk_count=chunk_count)
        )
        await self._session.flush()

    async def delete_snapshot_chunks(self, snapshot_id: UUID) -> None:
        await self._session.execute(
            delete(VectorSnapshotChunkModel).where(
                VectorSnapshotChunkModel.vector_snapshot_id == snapshot_id
            )
        )
        await self._session.flush()

    async def add_snapshot_chunks(
        self,
        chunks: list[VectorSnapshotChunk],
    ) -> None:
        self._session.add_all(
            [_snapshot_chunk_to_model(chunk) for chunk in chunks]
        )
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
            SELECT id, 1 - (embedding <=> CAST(:embedding AS vector)) AS similarity
            FROM agent.vector_snapshot_chunks
            WHERE vector_snapshot_id = :vector_snapshot_id
              AND embedding IS NOT NULL
              AND 1 - (embedding <=> CAST(:embedding AS vector)) >= :threshold
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
            select(VectorSnapshotChunkModel).where(
                VectorSnapshotChunkModel.id.in_(chunk_ids)
            )
        )
        chunks = [
            _snapshot_chunk_model_to_entity(model)
            for model in chunks_result.scalars().all()
        ]
        chunks.sort(
            key=lambda chunk: similarity_map.get(chunk.id, 0),
            reverse=True,
        )
        return [
            (chunk, similarity_map.get(chunk.id, 0.0)) for chunk in chunks
        ]
