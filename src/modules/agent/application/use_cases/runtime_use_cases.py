from __future__ import annotations

from typing import cast
from uuid import UUID

from modules.agent.domain.entities import AskJob, Message, Session
from modules.agent.domain.errors import AskJobNotFoundError
from modules.agent.domain.events import (
    AgentExecutionRequestedV1,
    AgentMessageCreatedV1,
    AgentSessionCreatedV1,
)
from modules.agent.application.interfaces.outbox import OutboxEventWriter
from modules.agent.application.interfaces.repositories import AskJobRepository, MessageRepository, SessionRepository
from modules.agent.application.dtos.runtime_dtos import (
    CreateAskJobInput,
    CreateAskJobOutput,
    CreateSessionInput,
    CreateSessionOutput,
    GetAskJobOutput,
    ListAgentSessionsInput,
    ListAgentSessionsOutput,
    ListAgentSessionsPageOutput,
    ListMessagesInput,
    ListMessagesOutput,
    MessageResponse,
    SendMessageInput,
    SendMessageOutput,
)
from modules.agent.domain.enums import RuntimeSessionMode, SessionStatus
from shared.contracts.time import utc_now


class CreateSessionUseCase:

    def __init__(
        self,
        repo: SessionRepository,
        outbox: "OutboxEventWriter",
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
        project_id = cast(UUID, created.project_id)
        agent_id = cast(UUID, created.agent_id)

        event = AgentSessionCreatedV1.create(
            session_id=created.id,
            project_id=project_id,
            agent_id=agent_id,
            payload={"mode": created.mode},
        )
        await self._outbox.write(event)

        return CreateSessionOutput(
            id=created.id,
            project_id=project_id,
            agent_id=agent_id,
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
        project_id = cast(UUID, sess.project_id)
        agent_id = cast(UUID, sess.agent_id)

        message = Message(
            project_id=project_id,
            agent_id=agent_id,
            session_id=input_dto.session_id,
            role=input_dto.role,
            content=input_dto.content,
            data=input_dto.data,
        )
        created = await self.message_repo.create(message)
        session_id = cast(UUID, created.session_id)

        sess.last_message_at = utc_now()
        await self.session_repo.update(sess)

        event = AgentMessageCreatedV1.create(
            message_id=created.id,
            session_id=sess.id,
            project_id=project_id,
            agent_id=agent_id,
            role=created.role,
        )
        await self._outbox.write(event)

        return SendMessageOutput(
            message=MessageResponse(
                id=created.id,
                session_id=session_id,
                role=created.role,
                content=created.content,
                input_tokens=created.input_tokens,
                output_tokens=created.output_tokens,
                cost_usd=created.cost_usd,
                data=created.data,
                created_at=created.created_at,
                updated_at=created.updated_at,
            ),
            session_id=session_id,
        )


class ListMessagesUseCase:

    def __init__(self, repo: MessageRepository) -> None:
        self._repo = repo

    async def execute(self, input_dto: ListMessagesInput) -> list[ListMessagesOutput]:
        messages = await self._repo.list_by_session(input_dto.session_id, input_dto.offset, input_dto.limit)
        return [ListMessagesOutput(
            id=m.id,
            session_id=cast(UUID, m.session_id),
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

    async def execute(self, input_dto: ListAgentSessionsInput) -> ListAgentSessionsPageOutput:
        sessions = await self._session_repo.list_by_agent(
            input_dto.project_id, input_dto.agent_id
        )
        sessions = sorted(
            sessions,
            key=lambda session: (session.last_message_at or session.created_at).timestamp()
            if session.last_message_at or session.created_at
            else 0.0,
            reverse=True,
        )

        start_index = 0
        if input_dto.cursor:
            for index, session in enumerate(sessions):
                if str(session.id) == input_dto.cursor:
                    start_index = index + 1
                    break

        page_sessions = sessions[start_index:start_index + input_dto.limit + 1]
        has_next = len(page_sessions) > input_dto.limit
        visible_sessions = page_sessions[:input_dto.limit]

        result: list[ListAgentSessionsOutput] = []
        for s in visible_sessions:
            try:
                count = await self._message_repo.count_by_session(s.id)
            except Exception:
                count = 0
            result.append(ListAgentSessionsOutput(
                id=s.id,
                project_id=cast(UUID, s.project_id),
                agent_id=cast(UUID, s.agent_id),
                status=SessionStatus(s.status),
                mode=RuntimeSessionMode(s.mode),
                data=s.data,
                last_message_at=s.last_message_at,
                created_at=s.created_at,
                message_count=count,
            ))

        return ListAgentSessionsPageOutput(
            items=result,
            next_cursor=str(result[-1].id) if has_next and result else None,
            has_next=has_next,
        )


class CreateAskJobUseCase:

    def __init__(self, repo: AskJobRepository, outbox: OutboxEventWriter | None = None) -> None:
        self._repo = repo
        self._outbox = outbox

    async def execute(self, input_dto: CreateAskJobInput) -> CreateAskJobOutput:
        job = AskJob(
            project_id=input_dto.project_id,
            agent_id=input_dto.agent_id,
            session_id=input_dto.session_id,
            status="pending",
            params=input_dto.model_dump(mode="json"),
        )
        created = await self._repo.create(job)

        if self._outbox:
            event = AgentExecutionRequestedV1.create(
                agent_id=input_dto.agent_id,
                session_id=input_dto.session_id or created.id,
                payload={
                    "job_id": str(created.id),
                    "project_id": str(input_dto.project_id),
                    "agent_id": str(input_dto.agent_id),
                    "session_id": str(input_dto.session_id) if input_dto.session_id else None,
                },
            )
            await self._outbox.write(event)

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


class GetPublicAskJobUseCase:
    def __init__(self, repo: AskJobRepository) -> None:
        self._repo = repo

    async def execute(
        self,
        job_id: UUID,
        *,
        project_id: UUID,
        agent_id: UUID,
        environment: str,
    ) -> GetAskJobOutput:
        job = await self._repo.get_by_id(job_id)
        job_environment = (job.params or {}).get("execution_context")
        if (
            job.project_id != project_id
            or job.agent_id != agent_id
            or job_environment != environment
        ):
            raise AskJobNotFoundError(job_id)

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
