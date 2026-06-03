from __future__ import annotations

from datetime import datetime, timezone

from modules.runtime.domain.entities import Message, Session
from modules.runtime.domain.repositories import MessageRepository, SessionRepository
from modules.runtime.infra.models import OutboxEventModel
from modules.runtime.service.dtos import (
    CreateSessionInput,
    CreateSessionOutput,
    MessageResponse,
    SendMessageInput,
    SendMessageOutput,
)
from sqlalchemy.ext.asyncio import AsyncSession


class CreateSessionUseCase:

    def __init__(
        self,
        session: AsyncSession,
        repo: SessionRepository,
    ) -> None:
        self.session = session
        self.repo = repo

    async def execute(self, input_dto: CreateSessionInput) -> CreateSessionOutput:
        session = Session(
            project_id=input_dto.project_id,
            agent_id=input_dto.agent_id,
            external_session_id=input_dto.external_session_id,
            tenant_id=input_dto.tenant_id,
            user_id=input_dto.user_id,
            mode=input_dto.mode,
            data=input_dto.data,
        )
        created = await self.repo.create(session)

        event = OutboxEventModel(
            aggregate_type="session",
            aggregate_id=created.id,
            event_type="runtime.session.created",
            payload={
                "session_id": str(created.id),
                "project_id": str(created.project_id),
                "agent_id": str(created.agent_id),
                "mode": created.mode,
            },
        )
        self.session.add(event)

        return CreateSessionOutput(
            id=created.id,
            project_id=created.project_id,
            agent_id=created.agent_id,
            external_session_id=created.external_session_id,
            tenant_id=created.tenant_id,
            user_id=created.user_id,
            status=created.status,
            mode=created.mode,
            data=created.data,
            last_message_at=created.last_message_at,
            created_at=created.created_at,
            updated_at=created.updated_at,
        )


class SendMessageUseCase:

    def __init__(
        self,
        session: AsyncSession,
        session_repo: SessionRepository,
        message_repo: MessageRepository,
    ) -> None:
        self.session = session
        self.session_repo = session_repo
        self.message_repo = message_repo

    async def execute(self, input_dto: SendMessageInput) -> SendMessageOutput:
        sess = await self.session_repo.get_by_id(input_dto.session_id)

        message = Message(
            project_id=sess.project_id,
            agent_id=sess.agent_id,
            session_id=input_dto.session_id,
            role=input_dto.role,
            content=input_dto.content,
            data=input_dto.data,
        )
        created = await self.message_repo.create(message)

        now = datetime.now(timezone.utc)
        sess.last_message_at = now
        await self.session_repo.update(sess)

        event = OutboxEventModel(
            aggregate_type="message",
            aggregate_id=created.id,
            event_type="runtime.ask.completed",
            payload={
                "message_id": str(created.id),
                "session_id": str(input_dto.session_id),
                "project_id": str(sess.project_id),
                "agent_id": str(sess.agent_id),
                "role": created.role,
            },
        )
        self.session.add(event)

        return SendMessageOutput(
            message=MessageResponse(
                id=created.id,
                session_id=created.session_id,
                role=created.role,
                content=created.content,
                input_tokens=created.input_tokens,
                output_tokens=created.output_tokens,
                cost_usd=created.cost_usd,
                data=created.data,
                created_at=created.created_at,
                updated_at=created.updated_at,
            ),
            session_id=created.session_id,
        )

