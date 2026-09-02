from __future__ import annotations

from typing import Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.agent.application.use_cases.network_snapshot_lifecycle import (
    NetworkAgentSnapshotLifecycle,
)
from modules.agent.domain.entities import AgentRelease
from modules.agent.domain.release_snapshot import (
    release_snapshot_hash,
    release_snapshots_equal,
)
from modules.agent.infra.database.mappers import agent_release_model_to_entity
from modules.agent.infra.database.models import AgentModel, AgentReleaseModel
from modules.agent.infra.database.repositories import SQLAlchemyAgentReleaseRepository


class _SessionOwner(Protocol):
    @property
    def session(self) -> AsyncSession: ...


class NetworkAgentPromotionGateway:
    """Agent persistence boundary shared with one caller-owned SQL transaction."""

    def __init__(self, transaction: _SessionOwner) -> None:
        self._transaction = transaction

    @property
    def _session(self) -> AsyncSession:
        return self._transaction.session

    async def is_active_agent(self, *, project_id: UUID, agent_id: UUID) -> bool:
        value = await self._session.scalar(
            select(AgentModel.id).where(
                AgentModel.id == agent_id,
                AgentModel.project_id == project_id,
                AgentModel.status == "active",
            )
        )
        return value is not None

    async def latest_draft(
        self,
        *,
        project_id: UUID,
        agent_id: UUID,
        lock: bool,
    ) -> AgentRelease | None:
        statement = (
            select(AgentReleaseModel)
            .where(
                AgentReleaseModel.project_id == project_id,
                AgentReleaseModel.agent_id == agent_id,
                AgentReleaseModel.status == "draft",
                AgentReleaseModel.snapshot_kind == "draft",
            )
            .order_by(
                AgentReleaseModel.updated_at.desc(),
                AgentReleaseModel.created_at.desc(),
            )
            .limit(1)
        )
        if lock:
            statement = statement.with_for_update()
        model = await self._session.scalar(statement)
        return agent_release_model_to_entity(model) if model is not None else None

    async def snapshot_by_id(
        self,
        *,
        release_id: UUID | None,
        project_id: UUID,
        agent_id: UUID,
        lock: bool,
    ) -> AgentRelease | None:
        if release_id is None:
            return None
        statement = select(AgentReleaseModel).where(
            AgentReleaseModel.id == release_id,
            AgentReleaseModel.project_id == project_id,
            AgentReleaseModel.agent_id == agent_id,
        )
        if lock:
            statement = statement.with_for_update()
        model = await self._session.scalar(statement)
        return agent_release_model_to_entity(model) if model is not None else None

    async def equivalent_snapshot(
        self,
        *,
        source: AgentRelease,
        target_kind: str,
        active_only: bool,
        lock: bool,
    ) -> AgentRelease | None:
        statement = select(AgentReleaseModel).where(
            AgentReleaseModel.project_id == source.project_id,
            AgentReleaseModel.agent_id == source.agent_id,
            AgentReleaseModel.snapshot_kind == target_kind,
            AgentReleaseModel.id != source.id,
        )
        if active_only:
            statement = statement.where(AgentReleaseModel.status == target_kind)
        statement = statement.order_by(AgentReleaseModel.created_at.desc())
        if lock:
            statement = statement.with_for_update()
        result = await self._session.scalars(statement)
        for model in result.all():
            candidate = agent_release_model_to_entity(model)
            if release_snapshots_equal(candidate, source):
                return candidate
        return None

    async def promote_draft_to_staging(
        self,
        source: AgentRelease,
        *,
        user_id: UUID | None,
    ) -> AgentRelease:
        repository = SQLAlchemyAgentReleaseRepository(self._session)  # type: ignore[arg-type]
        lifecycle = NetworkAgentSnapshotLifecycle(repository)
        resolution = await lifecycle.promote_draft_to_staging(source, user_id=user_id)
        return resolution.release

    async def publish_staging_for_network(
        self,
        source: AgentRelease,
        *,
        user_id: UUID | None,
    ) -> AgentRelease:
        repository = SQLAlchemyAgentReleaseRepository(self._session)  # type: ignore[arg-type]
        lifecycle = NetworkAgentSnapshotLifecycle(repository)
        resolution = await lifecycle.publish_staging_for_network(source, user_id=user_id)
        return resolution.release

    @staticmethod
    def snapshot_hash(snapshot: AgentRelease) -> str:
        return release_snapshot_hash(snapshot)

    @staticmethod
    def snapshots_equal(left: AgentRelease, right: AgentRelease) -> bool:
        return release_snapshots_equal(left, right)
