from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.metering.domain.entities import UsageDailyAgent, UsageDailyProject, UsageEvent
from modules.metering.domain.repositories import (
    UsageDailyAgentRepository,
    UsageDailyProjectRepository,
    UsageEventRepository,
)
from modules.metering.infra.mappers import (
    usage_daily_agent_entity_to_model,
    usage_daily_agent_model_to_entity,
    usage_daily_project_entity_to_model,
    usage_daily_project_model_to_entity,
    usage_event_entity_to_model,
    usage_event_model_to_entity,
)
from modules.metering.infra.models import (
    OutboxEventModel,
    UsageDailyAgentModel,
    UsageDailyProjectModel,
    UsageEventModel,
)
from shared.domain.events import OutboxEventWriter
from shared.infra.repositories.base_repository import BaseRepository


class SQLAlchemyUsageEventRepository(BaseRepository[UsageEventModel], UsageEventRepository):

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, UsageEventModel)

    async def save(self, event: UsageEvent) -> UsageEvent:
        model = usage_event_entity_to_model(event)
        self.session.add(model)
        return usage_event_model_to_entity(model)

    async def get_by_id(self, event_id: UUID) -> UsageEvent | None:
        model = await self.session.get(UsageEventModel, event_id)
        if model is None:
            return None
        return usage_event_model_to_entity(model)

    async def list_by_project(
        self, project_id: UUID, limit: int = 100, offset: int = 0
    ) -> list[UsageEvent]:
        stmt = (
            select(UsageEventModel)
            .where(UsageEventModel.project_id == project_id)
            .order_by(UsageEventModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return [usage_event_model_to_entity(m) for m in result.scalars().all()]

    async def delete(self, event_id: UUID) -> None:
        model = await self.session.get(UsageEventModel, event_id)
        if model:
            await self.session.delete(model)


class SQLAlchemyUsageDailyProjectRepository(UsageDailyProjectRepository):

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save(self, daily: UsageDailyProject) -> UsageDailyProject:
        model = usage_daily_project_entity_to_model(daily)
        merged = await self.session.merge(model)
        return usage_daily_project_model_to_entity(merged)

    async def get_by_project_and_day(
        self, project_id: UUID, day: str
    ) -> UsageDailyProject | None:
        stmt = select(UsageDailyProjectModel).where(
            UsageDailyProjectModel.project_id == project_id,
            UsageDailyProjectModel.day == day,
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return usage_daily_project_model_to_entity(model)

    async def list_by_project(
        self, project_id: UUID, limit: int = 100, offset: int = 0
    ) -> list[UsageDailyProject]:
        stmt = (
            select(UsageDailyProjectModel)
            .where(UsageDailyProjectModel.project_id == project_id)
            .order_by(UsageDailyProjectModel.day.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return [usage_daily_project_model_to_entity(m) for m in result.scalars().all()]


class SQLAlchemyUsageDailyAgentRepository(UsageDailyAgentRepository):

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save(self, daily: UsageDailyAgent) -> UsageDailyAgent:
        model = usage_daily_agent_entity_to_model(daily)
        merged = await self.session.merge(model)
        return usage_daily_agent_model_to_entity(merged)

    async def get_by_agent_and_day(
        self, agent_id: UUID, day: str
    ) -> UsageDailyAgent | None:
        stmt = select(UsageDailyAgentModel).where(
            UsageDailyAgentModel.agent_id == agent_id,
            UsageDailyAgentModel.day == day,
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return usage_daily_agent_model_to_entity(model)

    async def list_by_agent(
        self, agent_id: UUID, limit: int = 100, offset: int = 0
    ) -> list[UsageDailyAgent]:
        stmt = (
            select(UsageDailyAgentModel)
            .where(UsageDailyAgentModel.agent_id == agent_id)
            .order_by(UsageDailyAgentModel.day.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return [usage_daily_agent_model_to_entity(m) for m in result.scalars().all()]


class SQLAlchemyOutboxEventWriter(OutboxEventWriter):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def write(
        self,
        aggregate_type: str,
        aggregate_id: UUID,
        event_type: str,
        payload: dict[str, Any] | None = None,
        correlation_id: UUID | None = None,
        causation_id: UUID | None = None,
    ) -> None:
        event = OutboxEventModel(
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            event_type=event_type,
            payload=payload or {},
            correlation_id=correlation_id,
            causation_id=causation_id,
        )
        self._session.add(event)
