from __future__ import annotations

from uuid import UUID

from modules.agent.infra.database.runtime_transaction_runner import AgentRuntimeTransactionRunner


class AgentRuntimeVectorSearchReader:
    """Short read-only pgvector access behind the runtime persistence boundary."""

    def __init__(self, transactions: AgentRuntimeTransactionRunner) -> None:
        self._transactions = transactions

    async def search(
        self,
        *,
        vector_snapshot_id: UUID,
        embedding: list[float],
        limit: int,
        threshold: float,
    ):
        async def read(repositories, _outbox):
            return await repositories.vector_snapshots.search_similar(
                vector_snapshot_id=vector_snapshot_id,
                embedding=embedding,
                limit=limit,
                threshold=threshold,
            )

        return await self._transactions.read(read)
