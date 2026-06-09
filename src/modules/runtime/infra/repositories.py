from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.infra.config.interface.unit_of_work import UnitOfWork

from modules.runtime.domain.entities import AskJob, Message, Session
from modules.runtime.domain.errors import AskJobNotFoundError, MessageNotFoundError, SessionNotFoundError
from modules.runtime.domain.repositories import AskJobRepository, MessageRepository, SessionRepository
from modules.runtime.infra.mappers import (
    ask_job_to_model,
    message_to_model,
    model_to_ask_job,
    model_to_message,
    model_to_session,
    session_to_model,
)
from modules.runtime.infra.models import AskJobModel, MessageModel, OutboxEventModel, SessionModel
from shared.domain.events import OutboxEventWriter
from shared.domain.objects import CursorPage
from shared.infra.repositories.base_repository import BaseSQLAlchemyRepository


class SQLAlchemySessionRepository(SessionRepository):

    def __init__(self, session: AsyncSession | UnitOfWork) -> None:
        self._base = BaseSQLAlchemyRepository(session, SessionModel)
        self._session_or_uow: AsyncSession | UnitOfWork = session

    @property
    def _session(self) -> AsyncSession:
        if isinstance(self._session_or_uow, UnitOfWork):
            return self._session_or_uow.session
        return self._session_or_uow

    async def create(self, session: Session) -> Session:
        model = session_to_model(session)
        await self._base._add_model(model)
        await self._base._flush()
        await self._base._refresh_model(model)
        return model_to_session(model)

    async def get_by_id(self, session_id: UUID) -> Session:
        model = await self._base._get_model_by_id(session_id)
        if model is None:
            raise SessionNotFoundError(session_id)
        return model_to_session(model)

    async def get_by_external_id(
        self, project_id: UUID, agent_id: UUID, external_session_id: str
    ) -> Session:
        stmt = select(SessionModel).where(
            SessionModel.project_id == project_id,
            SessionModel.agent_id == agent_id,
            SessionModel.external_session_id == external_session_id,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            raise SessionNotFoundError(session_id=external_session_id)
        return model_to_session(model)

    async def list_by_agent(
        self, project_id: UUID, agent_id: UUID, status: str | None = None
    ) -> list[Session]:
        stmt = select(SessionModel).where(
            SessionModel.project_id == project_id,
            SessionModel.agent_id == agent_id,
        )
        if status:
            stmt = stmt.where(SessionModel.status == status)
        stmt = stmt.order_by(SessionModel.last_message_at.desc().nullslast())
        result = await self._session.execute(stmt)
        return [model_to_session(m) for m in result.scalars().all()]

    async def list_by_project(
        self, project_id: UUID, status: str | None = None
    ) -> list[Session]:
        # TODO: Remove after pagination migration
        stmt = select(SessionModel).where(
            SessionModel.project_id == project_id
        )
        if status:
            stmt = stmt.where(SessionModel.status == status)
        stmt = stmt.order_by(SessionModel.created_at.desc())
        result = await self._session.execute(stmt)
        return [model_to_session(m) for m in result.scalars().all()]

    async def paginate_by_project(
        self, project_id: UUID, *, status: str | None = None, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[Session]:
        stmt = select(SessionModel).where(
            SessionModel.project_id == project_id
        )
        if status:
            stmt = stmt.where(SessionModel.status == status)
        stmt = stmt.order_by(SessionModel.id.desc())
        page = await self._base._paginate_models(stmt, limit=limit, cursor=cursor)
        return CursorPage(
            items=[model_to_session(m) for m in page.items],
            cursor=page.cursor,
            next_cursor=page.next_cursor,
            has_next=page.has_next,
            total=page.total,
        )

    async def update(self, session: Session) -> Session:
        model = await self._base._get_model_by_id(session.id)
        if model is None:
            raise SessionNotFoundError(session.id)
        model.external_session_id = session.external_session_id
        model.tenant_id = session.tenant_id
        model.user_id = session.user_id
        model.status = session.status
        model.data = session.data
        model.last_message_at = session.last_message_at
        return model_to_session(model)

    async def delete(self, session_id: UUID) -> None:
        model = await self._base._get_model_by_id(session_id)
        if model is None:
            raise SessionNotFoundError(session_id)
        await self._base._delete_model(model)


class SQLAlchemyMessageRepository(MessageRepository):

    def __init__(self, session: AsyncSession | UnitOfWork) -> None:
        self._base = BaseSQLAlchemyRepository(session, MessageModel)
        self._session_or_uow: AsyncSession | UnitOfWork = session

    @property
    def _session(self) -> AsyncSession:
        if isinstance(self._session_or_uow, UnitOfWork):
            return self._session_or_uow.session
        return self._session_or_uow

    async def create(self, message: Message) -> Message:
        model = message_to_model(message)
        await self._base._add_model(model)
        await self._base._flush()
        await self._base._refresh_model(model)
        return model_to_message(model)

    async def get_by_id(self, message_id: UUID) -> Message:
        model = await self._base._get_model_by_id(message_id)
        if model is None:
            raise MessageNotFoundError(message_id)
        return model_to_message(model)

    async def list_by_session(
        self, session_id: UUID, offset: int = 0, limit: int = 100
    ) -> list[Message]:
        # TODO: Remove after pagination migration
        stmt = (
            select(MessageModel)
            .where(MessageModel.session_id == session_id)
            .order_by(MessageModel.created_at)
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [model_to_message(m) for m in result.scalars().all()]

    async def paginate_by_session(
        self, session_id: UUID, *, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[Message]:
        stmt = (
            select(MessageModel)
            .where(MessageModel.session_id == session_id)
            .order_by(MessageModel.id.desc())
        )
        page = await self._base._paginate_models(stmt, limit=limit, cursor=cursor)
        return CursorPage(
            items=[model_to_message(m) for m in page.items],
            cursor=page.cursor,
            next_cursor=page.next_cursor,
            has_next=page.has_next,
            total=page.total,
        )

    async def count_by_session(self, session_id: UUID) -> int:
        stmt = select(func.count()).select_from(MessageModel).where(
            MessageModel.session_id == session_id
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def delete_by_session(self, session_id: UUID) -> None:
        stmt = select(MessageModel).where(
            MessageModel.session_id == session_id
        )
        result = await self._session.execute(stmt)
        for model in result.scalars().all():
            await self._base._delete_model(model)


class SQLAlchemyOutboxEventWriter(OutboxEventWriter):

    def __init__(self, session: AsyncSession | UnitOfWork) -> None:
        self._session_or_uow: AsyncSession | UnitOfWork = session

    @property
    def _session(self) -> AsyncSession:
        if isinstance(self._session_or_uow, UnitOfWork):
            return self._session_or_uow.session
        return self._session_or_uow

    async def write(
        self,
        aggregate_type: str,
        aggregate_id: UUID,
        event_type: str,
        payload: dict[str, Any],
        event_version: int = 1,
        correlation_id: UUID | None = None,
        causation_id: UUID | None = None,
    ) -> None:
        event = OutboxEventModel(
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            event_type=event_type,
            payload=payload,
            correlation_id=correlation_id,
            causation_id=causation_id,
        )
        self._session.add(event)


class SQLAlchemyAskJobRepository(AskJobRepository):

    def __init__(self, session: AsyncSession | UnitOfWork) -> None:
        self._base = BaseSQLAlchemyRepository(session, AskJobModel)
        self._session_or_uow: AsyncSession | UnitOfWork = session

    @property
    def _session(self) -> AsyncSession:
        if isinstance(self._session_or_uow, UnitOfWork):
            return self._session_or_uow.session
        return self._session_or_uow

    async def create(self, job: AskJob) -> AskJob:
        model = ask_job_to_model(job)
        await self._base._add_model(model)
        await self._base._flush()
        await self._base._refresh_model(model)
        return model_to_ask_job(model)

    async def get_by_id(self, job_id: UUID) -> AskJob:
        model = await self._base._get_model_by_id(job_id)
        if model is None:
            raise AskJobNotFoundError(job_id)
        return model_to_ask_job(model)

    async def list_pending(self, limit: int = 5) -> list[AskJob]:
        stmt = (
            select(AskJobModel)
            .where(AskJobModel.status == "pending")
            .order_by(AskJobModel.created_at)
            .limit(limit)
        )
        result = await self._session.execute(stmt)
        return [model_to_ask_job(m) for m in result.scalars().all()]

    async def mark_started(self, job_id: UUID) -> None:
        model = await self._base._get_model_by_id(job_id)
        if model:
            model.status = "running"
            model.started_at = datetime.now(timezone.utc)

    async def mark_completed(
        self, job_id: UUID, result: dict, trace_id: UUID
    ) -> None:
        model = await self._base._get_model_by_id(job_id)
        if model:
            model.status = "completed"
            model.result = result
            model.trace_id = trace_id
            model.completed_at = datetime.now(timezone.utc)

    async def mark_failed(self, job_id: UUID, error: str) -> None:
        model = await self._base._get_model_by_id(job_id)
        if model:
            model.status = "failed"
            model.error = error
            model.completed_at = datetime.now(timezone.utc)

