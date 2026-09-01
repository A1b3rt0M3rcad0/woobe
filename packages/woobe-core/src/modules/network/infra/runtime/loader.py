from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.network.application.runtime import (
    NetworkExecutionSnapshot,
    NetworkVersionSnapshot,
)
from modules.network.infra.database.models import (
    NetworkAgentContextModel,
    NetworkExecutionModel,
    NetworkVersionModel,
)


@dataclass(frozen=True, slots=True)
class LoadedNetworkExecution:
    execution: NetworkExecutionSnapshot
    version: NetworkVersionSnapshot | None
    agent_contexts: dict[str, str | None]


class NetworkRuntimeLoader:
    """Load detached immutable runtime snapshots in one short read-only scope."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    @staticmethod
    def _execution_snapshot(model: NetworkExecutionModel) -> NetworkExecutionSnapshot:
        return NetworkExecutionSnapshot(
            id=model.id,
            network_id=model.network_id,
            network_version_id=model.network_version_id,
            network_session_id=model.network_session_id,
            project_id=model.project_id,
            input_message=model.input_message,
            draft_revision=model.draft_revision,
            definition_snapshot=deepcopy(model.definition_snapshot),
            resolved_bindings_snapshot=deepcopy(model.resolved_bindings_snapshot),
            status=str(model.status),
        )

    @staticmethod
    def _version_snapshot(model: NetworkVersionModel) -> NetworkVersionSnapshot:
        return NetworkVersionSnapshot(
            id=model.id,
            kind=str(model.kind),
            definition=deepcopy(model.definition or {}),
            resolved_bindings=deepcopy(model.resolved_bindings or {}),
            version=str(model.version) if model.version is not None else None,
        )

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
                str(item.network_node_id): (
                    str(item.agent_session_id) if item.agent_session_id else None
                )
                for item in result.scalars()
            }
            return LoadedNetworkExecution(
                execution=self._execution_snapshot(execution),
                version=self._version_snapshot(version) if version is not None else None,
                agent_contexts=contexts,
            )

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
