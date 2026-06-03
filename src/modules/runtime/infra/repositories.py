from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.runtime.domain.entities import Message, Session
from modules.runtime.domain.errors import MessageNotFoundError, SessionNotFoundError
from modules.runtime.domain.repositories import MessageRepository, SessionRepository
from modules.runtime.infra.mappers import (
    message_to_model,
    model_to_message,
    model_to_session,
    session_to_model,
)
from modules.runtime.infra.models import MessageModel, SessionModel
from shared.infra.repositories.base_repository import BaseRepository


class SQLAlchemySessionRepository(SessionRepository):

    def __init__(self, session: AsyncSession) -> None:
        self._base = BaseRepository(session, SessionModel)
        self.session = session

    async def create(self, session: Session) -> Session:
        model = session_to_model(session)
        await self._base.add(model)
        return model_to_session(model)

    async def get_by_id(self, session_id: UUID) -> Session:
        model = await self._base.get_by_id(session_id)
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
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            raise SessionNotFoundError(session_id=external_session_id)
        return model_to_session(model)

    async def list_by_project(
        self, project_id: UUID, status: str | None = None
    ) -> list[Session]:
        stmt = select(SessionModel).where(
            SessionModel.project_id == project_id
        )
        if status:
            stmt = stmt.where(SessionModel.status == status)
        stmt = stmt.order_by(SessionModel.created_at.desc())
        result = await self.session.execute(stmt)
        return [model_to_session(m) for m in result.scalars().all()]

    async def update(self, session: Session) -> Session:
        model = await self._base.get_by_id(session.id)
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
        model = await self._base.get_by_id(session_id)
        if model is None:
            raise SessionNotFoundError(session_id)
        await self._base.delete(model)


class SQLAlchemyMessageRepository(MessageRepository):

    def __init__(self, session: AsyncSession) -> None:
        self._base = BaseRepository(session, MessageModel)
        self.session = session

    async def create(self, message: Message) -> Message:
        model = message_to_model(message)
        await self._base.add(model)
        return model_to_message(model)

    async def get_by_id(self, message_id: UUID) -> Message:
        model = await self._base.get_by_id(message_id)
        if model is None:
            raise MessageNotFoundError(message_id)
        return model_to_message(model)

    async def list_by_session(
        self, session_id: UUID, offset: int = 0, limit: int = 100
    ) -> list[Message]:
        stmt = (
            select(MessageModel)
            .where(MessageModel.session_id == session_id)
            .order_by(MessageModel.created_at)
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return [model_to_message(m) for m in result.scalars().all()]

    async def count_by_session(self, session_id: UUID) -> int:
        stmt = select(func.count()).select_from(MessageModel).where(
            MessageModel.session_id == session_id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def delete_by_session(self, session_id: UUID) -> None:
        stmt = select(MessageModel).where(
            MessageModel.session_id == session_id
        )
        result = await self.session.execute(stmt)
        for model in result.scalars().all():
            await self._base.delete(model)

