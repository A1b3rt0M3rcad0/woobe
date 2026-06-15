from __future__ import annotations

from modules.agent.application.handlers.session_resolver import SessionResolver
from modules.agent.domain.entities import AskJob, Message, Session
from modules.agent.domain.repositories import AskJobRepository, MessageRepository, SessionRepository
from modules.agent.application.dtos.runtime_dtos import (
    CreateAskJobInput,
    CreateAskJobOutput,
    CreateSessionInput,
    CreateSessionOutput,
    GetAskJobOutput,
    ListAgentSessionsInput,
    ListAgentSessionsOutput,
    ListMessagesInput,
    ListMessagesOutput,
    MessageResponse,
    SendMessageInput,
    SendMessageOutput,
)
from shared.messaging.outbox_writer import OutboxEventWriter
from shared.infra.time import utc_now


class CreateSessionUseCase:

    def __init__(
        self,
        repo: SessionRepository,
        outbox: OutboxEventWriter,
    ) -> None:
        self.repo = repo
        self._outbox = outbox

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

        await self._outbox.write(
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
        session_repo: SessionRepository,
        message_repo: MessageRepository,
        outbox: OutboxEventWriter,
    ) -> None:
        self.session_repo = session_repo
        self.message_repo = message_repo
        self._outbox = outbox

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

        sess.last_message_at = utc_now()
        await self.session_repo.update(sess)

        await self._outbox.write(
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


class ListMessagesUseCase:

    def __init__(self, repo: MessageRepository) -> None:
        self._repo = repo

    async def execute(self, input_dto: ListMessagesInput) -> list[ListMessagesOutput]:
        messages = await self._repo.list_by_session(input_dto.session_id, input_dto.offset, input_dto.limit)
        return [ListMessagesOutput(
            id=m.id,
            session_id=m.session_id,
            role=m.role.value if hasattr(m.role, "value") else m.role,
            content=m.content,
            input_tokens=m.input_tokens,
            output_tokens=m.output_tokens,
            cost_usd=m.cost_usd,
            data=m.data,
            created_at=m.created_at,
            updated_at=m.updated_at,
        ) for m in messages]


class ListAgentSessionsUseCase:

    def __init__(
        self,
        session_repo: SessionRepository,
        message_repo: MessageRepository,
    ) -> None:
        self._session_repo = session_repo
        self._message_repo = message_repo

    async def execute(self, input_dto: ListAgentSessionsInput) -> list[ListAgentSessionsOutput]:
        sessions = await self._session_repo.list_by_agent(
            input_dto.project_id, input_dto.agent_id
        )
        result = []
        for s in sessions:
            try:
                count = await self._message_repo.count_by_session(s.id)
            except Exception:
                count = 0
            result.append(ListAgentSessionsOutput(
                id=s.id,
                project_id=s.project_id,
                agent_id=s.agent_id,
                status=s.status.value if hasattr(s.status, "value") else s.status,
                mode=s.mode.value if hasattr(s.mode, "value") else s.mode,
                last_message_at=s.last_message_at,
                created_at=s.created_at,
                message_count=count,
            ))
        return result


class CreateAskJobUseCase:

    def __init__(self, repo: AskJobRepository, session_repo: SessionRepository) -> None:
        self._repo = repo
        self._session_resolver = SessionResolver(session_repo)

    async def execute(self, input_dto: CreateAskJobInput) -> CreateAskJobOutput:
        if input_dto.session_id is not None:
            await self._session_resolver.validate_existing(
                session_id=input_dto.session_id,
                project_id=input_dto.project_id,
                agent_id=input_dto.agent_id,
                tenant_id=input_dto.tenant_id,
                user_id=input_dto.user_id,
            )

        job = AskJob(
            project_id=input_dto.project_id,
            agent_id=input_dto.agent_id,
            session_id=input_dto.session_id,
            status="pending",
            params=input_dto.model_dump(exclude={"tenant_id", "user_id", "metadata"}),
        )
        created = await self._repo.create(job)
        return CreateAskJobOutput(job_id=created.id, status="pending")


class GetAskJobUseCase:

    def __init__(self, repo: AskJobRepository) -> None:
        self._repo = repo

    async def execute(self, job_id: UUID) -> GetAskJobOutput:
        job = await self._repo.get_by_id(job_id)
        return GetAskJobOutput(
            job_id=job.id,
            status=job.status,
            result=job.result,
            error=job.error,
            trace_id=job.trace_id,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
        )

