from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, text

from modules.metering.application.interfaces.outbox import OutboxEventWriter
from modules.metering.application.interfaces.repositories import (
    UsageDailyAgentRepository,
    UsageDailyProjectRepository,
    UsageEventRepository,
)
from modules.metering.domain.entities import UsageDailyAgent, UsageDailyProject, UsageEvent
from modules.metering.infra.database.mappers import (
    usage_daily_agent_entity_to_model,
    usage_daily_agent_model_to_entity,
    usage_daily_project_entity_to_model,
    usage_daily_project_model_to_entity,
    usage_event_entity_to_model,
    usage_event_model_to_entity,
)
from modules.metering.infra.database.models import (
    InboxEventModel,
    OutboxEventModel,
    UsageDailyAgentModel,
    UsageDailyProjectModel,
    UsageEventModel,
)
from modules.metering.infra.database.unit_of_work import MeteringUnitOfWork
from shared.contracts.pagination import CursorPage
from shared.infra.repositories.base_repository import BaseSQLAlchemyRepository

METERING_DEFAULT_BATCH_SIZE: int = 50
METERING_INBOX_LOCK_TIMEOUT_SECONDS: int = 60


class SQLAlchemyUsageEventRepository(
    BaseSQLAlchemyRepository[UsageEventModel],
    UsageEventRepository,
):
    def __init__(self, uow: MeteringUnitOfWork) -> None:
        super().__init__(uow, UsageEventModel)

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
    def __init__(self, uow: MeteringUnitOfWork) -> None:
        self._uow = uow

    async def save(self, daily: UsageDailyProject) -> UsageDailyProject:
        model = usage_daily_project_entity_to_model(daily)
        merged = await self._uow.session.merge(model)
        return usage_daily_project_model_to_entity(merged)

    async def get_by_project_and_day(
        self, project_id: UUID, day: str
    ) -> UsageDailyProject | None:
        stmt = select(UsageDailyProjectModel).where(
            UsageDailyProjectModel.project_id == project_id,
            UsageDailyProjectModel.day == day,
        )
        result = await self._uow.session.execute(stmt)
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
        result = await self._uow.session.execute(stmt)
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
        result = await self._uow.session.execute(stmt)
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
    def __init__(self, uow: MeteringUnitOfWork) -> None:
        self._uow = uow

    async def save(self, daily: UsageDailyAgent) -> UsageDailyAgent:
        model = usage_daily_agent_entity_to_model(daily)
        merged = await self._uow.session.merge(model)
        return usage_daily_agent_model_to_entity(merged)

    async def get_by_agent_and_day(
        self, agent_id: UUID, day: str
    ) -> UsageDailyAgent | None:
        stmt = select(UsageDailyAgentModel).where(
            UsageDailyAgentModel.agent_id == agent_id,
            UsageDailyAgentModel.day == day,
        )
        result = await self._uow.session.execute(stmt)
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
        result = await self._uow.session.execute(stmt)
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
        result = await self._uow.session.execute(stmt)
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
    def __init__(self, uow: MeteringUnitOfWork) -> None:
        self._uow = uow

    async def write(
        self,
        aggregate_type: str,
        aggregate_id: UUID,
        event_type: str,
        payload: dict[str, Any],
        routing_key: str,
        idempotency_key: str,
        event_version: int = 1,
        correlation_id: UUID | None = None,
        causation_id: UUID | None = None,
    ) -> None:
        event = OutboxEventModel(
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            event_type=event_type,
            event_version=event_version,
            routing_key=routing_key,
            payload=payload,
            idempotency_key=idempotency_key,
            correlation_id=correlation_id,
            causation_id=causation_id,
        )
        self._uow.session.add(event)


class SQLAlchemyMeteringInboxStore:
    def __init__(self, uow: MeteringUnitOfWork) -> None:
        self._uow = uow

    async def save_received(self, event: InboxEventModel) -> InboxEventModel:
        self._uow.session.add(event)
        await self._uow.session.flush()
        return event

    async def claim_batch(
        self,
        batch_size: int = METERING_DEFAULT_BATCH_SIZE,
        locked_by: str = "",
        lock_timeout_seconds: int = METERING_INBOX_LOCK_TIMEOUT_SECONDS,
    ) -> list[InboxEventModel]:
        now = datetime.now(timezone.utc)
        stmt = (
            select(InboxEventModel)
            .where(InboxEventModel.status.in_(["received", "retryable"]))
            .where(InboxEventModel.available_at <= func.now())
            .where(
                (InboxEventModel.locked_at.is_(None))
                | (
                    InboxEventModel.locked_at
                    < func.now() - text(f"INTERVAL '{lock_timeout_seconds} seconds'")
                )
            )
            .order_by(InboxEventModel.created_at.asc())
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        )
        result = await self._uow.session.execute(stmt)
        events = list(result.scalars().all())
        for event in events:
            event.locked_at = now
            event.locked_by = locked_by
        return events

    async def mark_processed(self, event_id: UUID) -> None:
        stmt = select(InboxEventModel).where(InboxEventModel.id == event_id)
        result = await self._uow.session.execute(stmt)
        event = result.scalar_one_or_none()
        if event:
            event.status = "processed"
            event.processed_at = datetime.now(timezone.utc)
            event.locked_at = None
            event.locked_by = None

    async def mark_failed(self, event_id: UUID, error: str) -> None:
        stmt = select(InboxEventModel).where(InboxEventModel.id == event_id)
        result = await self._uow.session.execute(stmt)
        event = result.scalar_one_or_none()
        if event:
            event.status = "failed"
            event.error = error
            event.locked_at = None
            event.locked_by = None

    async def mark_dead(self, event_id: UUID, error: str) -> None:
        stmt = select(InboxEventModel).where(InboxEventModel.id == event_id)
        result = await self._uow.session.execute(stmt)
        event = result.scalar_one_or_none()
        if event:
            event.status = "dead"
            event.error = error
            event.locked_at = None
            event.locked_by = None

    async def mark_retryable(
        self,
        event_id: UUID,
        error: str,
        available_at: datetime,
    ) -> None:
        stmt = select(InboxEventModel).where(InboxEventModel.id == event_id)
        result = await self._uow.session.execute(stmt)
        event = result.scalar_one_or_none()
        if event:
            event.status = "retryable"
            event.error = error
            event.available_at = available_at
            event.attempts = (event.attempts or 0) + 1
            event.locked_at = None
            event.locked_by = None
