from typing import Protocol
from uuid import UUID

from modules.agent.domain.vector_snapshot_entities import (
    VectorSnapshot,
    VectorSnapshotChunk,
    VectorSnapshotDocument,
)


class VectorSnapshotRepository(Protocol):
    async def create(self, snapshot: VectorSnapshot) -> VectorSnapshot: ...

    async def get_by_id(self, snapshot_id: UUID) -> VectorSnapshot | None: ...

    async def get_by_collection_version(
        self,
        project_id: UUID,
        collection_id: UUID,
        version: str,
    ) -> VectorSnapshot | None: ...

    async def get_active_building_by_collection(
        self,
        project_id: UUID,
        collection_id: UUID,
    ) -> VectorSnapshot | None: ...

    async def list_by_collection(
        self,
        project_id: UUID,
        collection_id: UUID,
    ) -> list[VectorSnapshot]: ...

    async def list_building(self, limit: int = 3) -> list[VectorSnapshot]: ...

    async def mark_started(
        self,
        snapshot_id: UUID,
        *,
        locked_by: str | None = None,
    ) -> None: ...

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
    ) -> None: ...

    async def mark_ready(
        self,
        snapshot_id: UUID,
        *,
        snapshot_hash: str,
        document_count: int,
        chunk_count: int,
        vector_count: int | None = None,
    ) -> VectorSnapshot | None: ...

    async def mark_failed(self, snapshot_id: UUID, error: str) -> None: ...

    async def add_snapshot_documents(
        self,
        documents: list[VectorSnapshotDocument],
    ) -> None: ...

    async def list_snapshot_documents(
        self,
        snapshot_id: UUID,
    ) -> list[VectorSnapshotDocument]: ...

    async def update_snapshot_document_chunk_count(
        self,
        snapshot_id: UUID,
        document_id: UUID,
        chunk_count: int,
    ) -> None: ...

    async def delete_snapshot_chunks(self, snapshot_id: UUID) -> None: ...

    async def add_snapshot_chunks(
        self,
        chunks: list[VectorSnapshotChunk],
    ) -> None: ...

    async def search_similar(
        self,
        *,
        vector_snapshot_id: UUID,
        embedding: list[float],
        limit: int = 10,
        threshold: float = 0.7,
    ) -> list[tuple[VectorSnapshotChunk, float]]: ...
