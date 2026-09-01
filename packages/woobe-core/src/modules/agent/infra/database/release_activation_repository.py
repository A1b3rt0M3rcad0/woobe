from __future__ import annotations

from uuid import UUID

from sqlalchemy import ForeignKey, Index, String, Text, select
from sqlalchemy.orm import Mapped, mapped_column

from modules.agent.application.interfaces.release_activation_repository import (
    AgentReleaseActivationRepository,
)
from modules.agent.domain.release_activation import AgentReleaseActivation
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from shared.infra.database.base import BaseModel
from shared.infra.repositories.base_repository import BaseSQLAlchemyRepository


class AgentReleaseActivationModel(BaseModel):
    __tablename__ = "agent_release_activations"
    __table_args__ = (
        Index(
            "ix_agent_release_activations_agent_created_at",
            "agent_id",
            "created_at",
        ),
        {"schema": "agent"},
    )

    project_id: Mapped[UUID]
    agent_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent.agents.id", ondelete="CASCADE")
    )
    release_id: Mapped[UUID] = mapped_column(
        ForeignKey("agent.agent_releases.id", ondelete="RESTRICT")
    )
    previous_release_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("agent.agent_releases.id", ondelete="SET NULL"),
        nullable=True,
    )
    action: Mapped[str] = mapped_column(String(32))
    change_description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_by: Mapped[UUID | None] = mapped_column(nullable=True)


def _to_entity(model: AgentReleaseActivationModel) -> AgentReleaseActivation:
    return AgentReleaseActivation(
        id=model.id,
        project_id=model.project_id,
        agent_id=model.agent_id,
        release_id=model.release_id,
        previous_release_id=model.previous_release_id,
        action=model.action,
        change_description=model.change_description,
        created_by=model.created_by,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


class SQLAlchemyAgentReleaseActivationRepository(
    BaseSQLAlchemyRepository[AgentReleaseActivationModel],
    AgentReleaseActivationRepository,
):
    def __init__(self, uow: AgentUnitOfWork) -> None:
        super().__init__(uow, AgentReleaseActivationModel)

    async def save(
        self,
        activation: AgentReleaseActivation,
    ) -> AgentReleaseActivation:
        model = AgentReleaseActivationModel(
            id=activation.id,
            project_id=activation.project_id,
            agent_id=activation.agent_id,
            release_id=activation.release_id,
            previous_release_id=activation.previous_release_id,
            action=activation.action,
            change_description=activation.change_description,
            created_by=activation.created_by,
        )
        await self._add_model(model)
        await self._flush()
        await self._refresh_model(model)
        return _to_entity(model)

    async def list_by_agent(
        self,
        agent_id: UUID,
    ) -> list[AgentReleaseActivation]:
        result = await self._session.execute(
            select(AgentReleaseActivationModel)
            .where(AgentReleaseActivationModel.agent_id == agent_id)
            .order_by(AgentReleaseActivationModel.created_at.desc())
        )
        return [_to_entity(item) for item in result.scalars().all()]
