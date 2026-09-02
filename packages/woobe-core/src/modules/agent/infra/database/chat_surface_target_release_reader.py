from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select

from modules.agent.infra.database.models import AgentModel, AgentReleaseModel
from modules.agent.infra.database.release_activation_repository import (
    AgentReleaseActivationModel,
)
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from shared.contracts.errors import ConflictError, NotFoundError
from shared.runtime_environment import assert_runtime_environment_enabled


@dataclass(frozen=True, slots=True)
class AgentChatSurfaceTargetRelease:
    id: UUID
    version: str


class AgentChatSurfaceTargetReleaseReader:
    def __init__(self, uow: AgentUnitOfWork) -> None:
        self._uow = uow

    async def current(
        self,
        *,
        project_id: UUID,
        target_id: UUID,
    ) -> AgentChatSurfaceTargetRelease:
        async with self._uow:
            session = self._uow.session
            target = await session.get(AgentModel, target_id)
            if target is None or target.project_id != project_id:
                raise NotFoundError("Agent not found")

            await assert_runtime_environment_enabled(
                session,
                target_type="agent",
                target_id=target_id,
                project_id=project_id,
                environment="production",
            )

            release_id = await session.scalar(
                select(AgentReleaseActivationModel.release_id)
                .where(
                    AgentReleaseActivationModel.project_id == project_id,
                    AgentReleaseActivationModel.agent_id == target_id,
                )
                .order_by(
                    AgentReleaseActivationModel.created_at.desc(),
                    AgentReleaseActivationModel.id.desc(),
                )
                .limit(1)
            )
            if release_id is None:
                release_id = await session.scalar(
                    select(AgentReleaseModel.id)
                    .where(
                        AgentReleaseModel.project_id == project_id,
                        AgentReleaseModel.agent_id == target_id,
                        AgentReleaseModel.status == "production",
                    )
                    .order_by(
                        AgentReleaseModel.updated_at.desc(),
                        AgentReleaseModel.created_at.desc(),
                        AgentReleaseModel.id.desc(),
                    )
                    .limit(1)
                )
            if release_id is None:
                raise ConflictError("Agent Production is not ready")

            release = await session.get(AgentReleaseModel, release_id)
            if (
                release is None
                or release.project_id != project_id
                or release.agent_id != target_id
            ):
                raise ConflictError("Agent Production release was not found")
            return AgentChatSurfaceTargetRelease(
                id=release.id,
                version=release.version,
            )

    async def validate(
        self,
        *,
        project_id: UUID,
        target_id: UUID,
        release_id: UUID,
    ) -> AgentChatSurfaceTargetRelease:
        async with self._uow:
            session = self._uow.session
            await assert_runtime_environment_enabled(
                session,
                target_type="agent",
                target_id=target_id,
                project_id=project_id,
                environment="production",
            )
            release = await session.get(AgentReleaseModel, release_id)
            if (
                release is None
                or release.project_id != project_id
                or release.agent_id != target_id
                or release.status in {"draft", "staging"}
            ):
                raise ConflictError("Pinned Agent Release is unavailable")
            return AgentChatSurfaceTargetRelease(
                id=release.id,
                version=release.version,
            )


__all__ = [
    "AgentChatSurfaceTargetRelease",
    "AgentChatSurfaceTargetReleaseReader",
]
