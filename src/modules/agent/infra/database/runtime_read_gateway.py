from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.domain.vector_snapshot_entities import VectorSnapshotChunk
from modules.agent.infra.database.vector_snapshot_models import VectorSnapshotChunkModel
from modules.agent.infra.database.vector_snapshot_repositories import (
    _snapshot_chunk_model_to_entity,
)


class AgentRuntimeReadGateway:
    """Short read-only SQL access for data only knowable after external I/O."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def search_vector_snapshot(
        self,
        *,
        vector_snapshot_id: UUID,
        embedding: list[float],
        limit: int,
        threshold: float,
    ) -> list[tuple[VectorSnapshotChunk, float]]:
        embedding_value = "[" + ",".join(str(value) for value in embedding) + "]"
        statement = text(
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
        async with self._session_factory() as session:
            result = await session.execute(
                statement,
                {
                    "embedding": embedding_value,
                    "vector_snapshot_id": vector_snapshot_id,
                    "threshold": threshold,
                    "limit": limit,
                },
            )
            rows = result.fetchall()
            if not rows:
                return []
            chunk_ids = [row[0] for row in rows]
            similarity_map = {row[0]: float(row[1]) for row in rows}
            chunks_result = await session.execute(
                select(VectorSnapshotChunkModel).where(
                    VectorSnapshotChunkModel.id.in_(chunk_ids)
                )
            )
            chunks = [
                _snapshot_chunk_model_to_entity(model)
                for model in chunks_result.scalars().all()
            ]
        chunks.sort(
            key=lambda chunk: similarity_map.get(chunk.id, 0.0),
            reverse=True,
        )
        return [(chunk, similarity_map.get(chunk.id, 0.0)) for chunk in chunks]
