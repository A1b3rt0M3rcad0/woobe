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
from shared.domain.objects import CursorPage
from shared.infra.repositories.base_repository import BaseSQLAlchemyRepository


class SQLAlchemyUsageEventRepository(BaseSQLAlchemyRepository[UsageEventModel], UsageEventRepository):

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, UsageEventModel)

    async def save(self, event: UsageEvent) -> UsageEvent:
        model = usage_event_entity_to_model(event)
        await self._add_model(model)
        await self._flush()
        await self._refresh_model(model)
        return usage_event_model_to_entity(model)

    async def get_by_id(self, event_id: UUID) -> UsageEvent | None:
        model = await self._get_model_by_id(event_id)
        if model is None:
            return None
        return usage_event_model_to_entity(model)

    async def list_by_project(
        self, project_id: UUID, limit: int = 100, offset: int = 0
    ) -> list[UsageEvent]:
        # TODO: Remove after pagination migration
        stmt = (
            select(UsageEventModel)
            .where(UsageEventModel.project_id == project_id)
            .order_by(UsageEventModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [usage_event_model_to_entity(m) for m in result.scalars().all()]

    async def paginate_by_project(
        self, project_id: UUID, *, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[UsageEvent]:
        stmt = (
            select(UsageEventModel)
            .where(UsageEventModel.project_id == project_id)
            .order_by(UsageEventModel.id.desc())
        )
        page = await self._paginate_models(stmt, limit=limit, cursor=cursor)
        return CursorPage(
            items=[usage_event_model_to_entity(m) for m in page.items],
            cursor=page.cursor,
            next_cursor=page.next_cursor,
            has_next=page.has_next,
            total=page.total,
        )

    async def delete(self, event_id: UUID) -> None:
        model = await self._get_model_by_id(event_id)
        if model:
            await self._delete_model(model)


class SQLAlchemyUsageDailyProjectRepository(UsageDailyProjectRepository):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, daily: UsageDailyProject) -> UsageDailyProject:
        model = usage_daily_project_entity_to_model(daily)
        merged = await self._session.merge(model)
        return usage_daily_project_model_to_entity(merged)

    async def get_by_project_and_day(
        self, project_id: UUID, day: str
    ) -> UsageDailyProject | None:
        stmt = select(UsageDailyProjectModel).where(
            UsageDailyProjectModel.project_id == project_id,
            UsageDailyProjectModel.day == day,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return usage_daily_project_model_to_entity(model)

    async def list_by_project(
        self, project_id: UUID, limit: int = 100, offset: int = 0
    ) -> list[UsageDailyProject]:
        # TODO: Remove after pagination migration
        stmt = (
            select(UsageDailyProjectModel)
            .where(UsageDailyProjectModel.project_id == project_id)
            .order_by(UsageDailyProjectModel.day.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [usage_daily_project_model_to_entity(m) for m in result.scalars().all()]

    async def paginate_by_project(
        self, project_id: UUID, *, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[UsageDailyProject]:
        from datetime import date as _date
        stmt = (
            select(UsageDailyProjectModel)
            .where(UsageDailyProjectModel.project_id == project_id)
            .order_by(UsageDailyProjectModel.day.desc())
        )
        if cursor:
            try:
                cursor_date = _date.fromisoformat(cursor)
            except (ValueError, TypeError):
                cursor_date = None
            if cursor_date is not None:
                stmt = stmt.where(UsageDailyProjectModel.day < cursor_date)

        fetch_limit = limit + 1
        stmt = stmt.limit(fetch_limit)
        result = await self._session.execute(stmt)
        rows = list(result.scalars().all())

        has_next = len(rows) > limit
        items = rows[:limit]
        next_cursor = items[-1].day.isoformat() if items and has_next else None

        return CursorPage(
            items=[usage_daily_project_model_to_entity(m) for m in items],
            cursor=cursor,
            next_cursor=next_cursor,
            has_next=has_next,
        )


class SQLAlchemyUsageDailyAgentRepository(UsageDailyAgentRepository):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, daily: UsageDailyAgent) -> UsageDailyAgent:
        model = usage_daily_agent_entity_to_model(daily)
        merged = await self._session.merge(model)
        return usage_daily_agent_model_to_entity(merged)

    async def get_by_agent_and_day(
        self, agent_id: UUID, day: str
    ) -> UsageDailyAgent | None:
        stmt = select(UsageDailyAgentModel).where(
            UsageDailyAgentModel.agent_id == agent_id,
            UsageDailyAgentModel.day == day,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return usage_daily_agent_model_to_entity(model)

    async def list_by_agent(
        self, agent_id: UUID, limit: int = 100, offset: int = 0
    ) -> list[UsageDailyAgent]:
        # TODO: Remove after pagination migration
        stmt = (
            select(UsageDailyAgentModel)
            .where(UsageDailyAgentModel.agent_id == agent_id)
            .order_by(UsageDailyAgentModel.day.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [usage_daily_agent_model_to_entity(m) for m in result.scalars().all()]

    async def paginate_by_agent(
        self, agent_id: UUID, *, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[UsageDailyAgent]:
        from datetime import date as _date
        stmt = (
            select(UsageDailyAgentModel)
            .where(UsageDailyAgentModel.agent_id == agent_id)
            .order_by(UsageDailyAgentModel.day.desc())
        )
        if cursor:
            try:
                cursor_date = _date.fromisoformat(cursor)
            except (ValueError, TypeError):
                cursor_date = None
            if cursor_date is not None:
                stmt = stmt.where(UsageDailyAgentModel.day < cursor_date)

        fetch_limit = limit + 1
        stmt = stmt.limit(fetch_limit)
        result = await self._session.execute(stmt)
        rows = list(result.scalars().all())

        has_next = len(rows) > limit
        items = rows[:limit]
        next_cursor = items[-1].day.isoformat() if items and has_next else None

        return CursorPage(
            items=[usage_daily_agent_model_to_entity(m) for m in items],
            cursor=cursor,
            next_cursor=next_cursor,
            has_next=has_next,
        )


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
