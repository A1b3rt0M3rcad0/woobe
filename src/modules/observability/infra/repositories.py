from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.observability.domain.entities import Trace, TraceEvent
from modules.observability.domain.repositories import TraceEventRepository, TraceRepository
from modules.observability.infra.mappers import (
    trace_entity_to_model,
    trace_event_entity_to_model,
    trace_event_model_to_entity,
    trace_model_to_entity,
)
from modules.observability.infra.models import (
    OutboxEventModel,
    TraceEventModel,
    TraceModel,
)
from shared.domain.events import OutboxEventWriter
from shared.infra.repositories.base_repository import BaseRepository


class SQLAlchemyTraceRepository(BaseRepository[TraceModel], TraceRepository):

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, TraceModel)

    async def save(self, trace: Trace) -> Trace:
        model = trace_entity_to_model(trace)
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        return trace_model_to_entity(model)

    async def get_by_id(self, trace_id: UUID) -> Trace | None:
        model = await self.session.get(TraceModel, trace_id)
        if model is None:
            return None
        return trace_model_to_entity(model)

    async def list_by_project(
        self, project_id: UUID, limit: int = 100, offset: int = 0
    ) -> list[Trace]:
        stmt = (
            select(TraceModel)
            .where(TraceModel.project_id == project_id)
            .order_by(TraceModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return [trace_model_to_entity(m) for m in result.scalars().all()]

    async def list_by_session(
        self, session_id: UUID, limit: int = 100, offset: int = 0
    ) -> list[Trace]:
        stmt = (
            select(TraceModel)
            .where(TraceModel.session_id == session_id)
            .order_by(TraceModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return [trace_model_to_entity(m) for m in result.scalars().all()]

    async def delete(self, trace_id: UUID) -> None:
        model = await self.session.get(TraceModel, trace_id)
        if model:
            await self.session.delete(model)


class SQLAlchemyTraceEventRepository(
    BaseRepository[TraceEventModel], TraceEventRepository
):

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, TraceEventModel)

    async def save(self, event: TraceEvent) -> TraceEvent:
        model = trace_event_entity_to_model(event)
        self.session.add(model)
        await self.session.flush()
        await self.session.refresh(model)
        return trace_event_model_to_entity(model)

    async def get_by_id(self, event_id: UUID) -> TraceEvent | None:
        model = await self.session.get(TraceEventModel, event_id)
        if model is None:
            return None
        return trace_event_model_to_entity(model)

    async def list_by_trace(
        self, trace_id: UUID, limit: int = 100, offset: int = 0
    ) -> list[TraceEvent]:
        stmt = (
            select(TraceEventModel)
            .where(TraceEventModel.trace_id == trace_id)
            .order_by(TraceEventModel.created_at.asc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return [trace_event_model_to_entity(m) for m in result.scalars().all()]

    async def delete(self, event_id: UUID) -> None:
        model = await self.session.get(TraceEventModel, event_id)
        if model:
            await self.session.delete(model)


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
