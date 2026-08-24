from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.network.infra.database.models import (
    NetworkAgentContextModel,
    NetworkExecutionModel,
    NetworkVersionModel,
)


@dataclass(frozen=True, slots=True)
class LoadedNetworkExecution:
    execution: NetworkExecutionModel
    version: NetworkVersionModel | None
    agent_contexts: dict[str, str | None]


class NetworkRuntimeLoader:
    """Short read-only database loader used outside the execution hot path."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def load(self, execution_id: UUID) -> LoadedNetworkExecution | None:
        async with self._session_factory() as session:
            execution = await session.get(NetworkExecutionModel, execution_id)
            if execution is None:
                return None
            version = (
                await session.get(NetworkVersionModel, execution.network_version_id)
                if execution.network_version_id
                else None
            )
            result = await session.execute(
                select(NetworkAgentContextModel).where(
                    NetworkAgentContextModel.network_session_id
                    == execution.network_session_id
                )
            )
            contexts = {
                str(item.network_node_id): str(item.agent_session_id)
                if item.agent_session_id
                else None
                for item in result.scalars()
            }
            session.expunge(execution)
            if version is not None:
                session.expunge(version)
            return LoadedNetworkExecution(execution, version, contexts)

    async def recovery_candidates(
        self,
        *,
        older_than_seconds: int,
        limit: int = 50,
    ) -> list[UUID]:
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=older_than_seconds)
        async with self._session_factory() as session:
            result = await session.execute(
                select(NetworkExecutionModel.id)
                .where(
                    NetworkExecutionModel.status.in_([
                        "queued",
                        "running",
                        "cancel_requested",
                    ]),
                    NetworkExecutionModel.created_at < cutoff,
                )
                .order_by(NetworkExecutionModel.created_at.asc())
                .limit(limit)
            )
            return list(result.scalars())
