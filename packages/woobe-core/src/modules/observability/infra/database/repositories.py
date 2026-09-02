from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, inspect, select, text

from modules.observability.application.interfaces.outbox import OutboxEventWriter
from modules.observability.application.interfaces.repositories import (
    TraceEventRepository,
    TraceRepository,
)
from modules.observability.domain.entities import Trace, TraceEvent
from modules.observability.infra.database.mappers import (
    trace_entity_to_model,
    trace_event_entity_to_model,
    trace_event_model_to_entity,
    trace_model_to_entity,
)
from modules.observability.infra.database.models import (
    InboxEventModel,
    OutboxEventModel,
    TraceEventModel,
    TraceModel,
)
from modules.observability.infra.database.unit_of_work import ObservabilityUnitOfWork
from shared.contracts.pagination import CursorPage
from shared.infra.repositories.base_repository import BaseSQLAlchemyRepository

OBSERVABILITY_DEFAULT_BATCH_SIZE: int = 50
OBSERVABILITY_INBOX_LOCK_TIMEOUT_SECONDS: int = 60


class SQLAlchemyTraceRepository(
    BaseSQLAlchemyRepository[TraceModel],
    TraceRepository,
):
    def __init__(self, uow: ObservabilityUnitOfWork) -> None:
        super().__init__(uow, TraceModel)

    async def save(self, trace: Trace) -> Trace:
        model = trace_entity_to_model(trace)
        existing = await self._get_model_by_id(trace.id)
        if existing is not None:
            mapper = inspect(existing)
            for key in mapper.mapper.columns.keys():
                if key in ("id", "created_at", "updated_at"):
                    continue
                setattr(existing, key, getattr(model, key))
            await self._flush()
            await self._refresh_model(existing)
            return trace_model_to_entity(existing)
        await self._add_model(model)
        await self._flush()
        await self._refresh_model(model)
        return trace_model_to_entity(model)

    async def get_by_id(self, trace_id: UUID) -> Trace | None:
        model = await self._get_model_by_id(trace_id)
        if model is None:
            return None
        return trace_model_to_entity(model)

    async def list_by_project(
        self, project_id: UUID, limit: int = 100, offset: int = 0
    ) -> list[Trace]:
        statement = (
            select(TraceModel)
            .where(TraceModel.project_id == project_id)
            .order_by(TraceModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(statement)
        return [trace_model_to_entity(model) for model in result.scalars().all()]

    async def list_by_project_and_network(
        self,
        project_id: UUID,
        network_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Trace]:
        statement = (
            select(TraceModel)
            .where(
                TraceModel.project_id == project_id,
                TraceModel.network_id == network_id,
            )
            .order_by(TraceModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(statement)
        return [trace_model_to_entity(model) for model in result.scalars().all()]

    async def list_by_session(
        self, session_id: UUID, limit: int = 100, offset: int = 0
    ) -> list[Trace]:
        statement = (
            select(TraceModel)
            .where(TraceModel.session_id == session_id)
            .order_by(TraceModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(statement)
        return [trace_model_to_entity(model) for model in result.scalars().all()]

    async def list_by_project_and_agent(
        self, project_id: UUID, agent_id: UUID, limit: int = 100, offset: int = 0
    ) -> list[Trace]:
        statement = (
            select(TraceModel)
            .where(TraceModel.project_id == project_id, TraceModel.agent_id == agent_id)
            .order_by(TraceModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(statement)
        return [trace_model_to_entity(model) for model in result.scalars().all()]

    async def paginate_by_project(
        self, project_id: UUID, *, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[Trace]:
        statement = (
            select(TraceModel)
            .where(TraceModel.project_id == project_id)
            .order_by(TraceModel.id.desc())
        )
        page = await self._paginate_models(statement, limit=limit, cursor=cursor)
        return CursorPage(
            items=[trace_model_to_entity(model) for model in page.items],
            cursor=page.cursor,
            next_cursor=page.next_cursor,
            has_next=page.has_next,
            total=page.total,
        )

    async def paginate_by_session(
        self, session_id: UUID, *, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[Trace]:
        statement = (
            select(TraceModel)
            .where(TraceModel.session_id == session_id)
            .order_by(TraceModel.id.desc())
        )
        page = await self._paginate_models(statement, limit=limit, cursor=cursor)
        return CursorPage(
            items=[trace_model_to_entity(model) for model in page.items],
            cursor=page.cursor,
            next_cursor=page.next_cursor,
            has_next=page.has_next,
            total=page.total,
        )

    async def delete(self, trace_id: UUID) -> None:
        model = await self._get_model_by_id(trace_id)
        if model:
            await self._delete_model(model)


class SQLAlchemyTraceEventRepository(
    BaseSQLAlchemyRepository[TraceEventModel],
    TraceEventRepository,
):
    def __init__(self, uow: ObservabilityUnitOfWork) -> None:
        super().__init__(uow, TraceEventModel)

    async def save(self, event: TraceEvent) -> TraceEvent:
        model = trace_event_entity_to_model(event)
        existing = await self._get_model_by_id(event.id)
        if existing is not None:
            mapper = inspect(existing)
            for key in mapper.mapper.columns.keys():
                if key in ("id", "created_at", "updated_at"):
                    continue
                setattr(existing, key, getattr(model, key))
            await self._flush()
            await self._refresh_model(existing)
            return trace_event_model_to_entity(existing)
        await self._add_model(model)
        await self._flush()
        await self._refresh_model(model)
        return trace_event_model_to_entity(model)

    async def get_by_id(self, event_id: UUID) -> TraceEvent | None:
        model = await self._get_model_by_id(event_id)
        if model is None:
            return None
        return trace_event_model_to_entity(model)

    async def list_by_trace(
        self, trace_id: UUID, limit: int = 100, offset: int = 0
    ) -> list[TraceEvent]:
        statement = (
            select(TraceEventModel)
            .where(TraceEventModel.trace_id == trace_id)
            .order_by(TraceEventModel.created_at.asc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(statement)
        return [
            trace_event_model_to_entity(model) for model in result.scalars().all()
        ]

    async def paginate_by_trace(
        self, trace_id: UUID, *, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[TraceEvent]:
        statement = (
            select(TraceEventModel)
            .where(TraceEventModel.trace_id == trace_id)
            .order_by(TraceEventModel.id.desc())
        )
        page = await self._paginate_models(statement, limit=limit, cursor=cursor)
        return CursorPage(
            items=[trace_event_model_to_entity(model) for model in page.items],
            cursor=page.cursor,
            next_cursor=page.next_cursor,
            has_next=page.has_next,
            total=page.total,
        )

    async def delete(self, event_id: UUID) -> None:
        model = await self._get_model_by_id(event_id)
        if model:
            await self._delete_model(model)


class SQLAlchemyOutboxEventWriter(OutboxEventWriter):
    def __init__(self, uow: ObservabilityUnitOfWork) -> None:
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
        self._uow.session.add(
            OutboxEventModel(
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
        )


class ObservabilityInboxStore:
    def __init__(self, uow: ObservabilityUnitOfWork) -> None:
        self._uow = uow

    async def save_received(self, event: InboxEventModel) -> InboxEventModel:
        self._uow.session.add(event)
        await self._uow.session.flush()
        return event

    async def claim_batch(
        self,
        batch_size: int = OBSERVABILITY_DEFAULT_BATCH_SIZE,
        locked_by: str = "",
        lock_timeout_seconds: int = OBSERVABILITY_INBOX_LOCK_TIMEOUT_SECONDS,
    ) -> list[InboxEventModel]:
        now = datetime.now(timezone.utc)
        statement = (
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
        result = await self._uow.session.execute(statement)
        events = list(result.scalars().all())
        for event in events:
            event.locked_at = now
            event.locked_by = locked_by
        return events

    async def mark_processed(self, event_id: UUID) -> None:
        event = await self._event(event_id)
        if event:
            event.status = "processed"
            event.processed_at = datetime.now(timezone.utc)
            event.locked_at = None
            event.locked_by = None

    async def mark_failed(self, event_id: UUID, error: str) -> None:
        event = await self._event(event_id)
        if event:
            event.status = "failed"
            event.error = error
            event.locked_at = None
            event.locked_by = None

    async def mark_dead(self, event_id: UUID, error: str) -> None:
        event = await self._event(event_id)
        if event:
            event.status = "dead"
            event.error = error
            event.locked_at = None
            event.locked_by = None

    async def mark_retryable(
        self, event_id: UUID, error: str, available_at: datetime
    ) -> None:
        event = await self._event(event_id)
        if event:
            event.status = "retryable"
            event.error = error
            event.available_at = available_at
            event.attempts = (event.attempts or 0) + 1
            event.locked_at = None
            event.locked_by = None

    async def _event(self, event_id: UUID) -> InboxEventModel | None:
        result = await self._uow.session.execute(
            select(InboxEventModel).where(InboxEventModel.id == event_id)
        )
        return result.scalar_one_or_none()
