from __future__ import annotations

from typing import Any, cast
from uuid import UUID

from modules.agent.application.dtos.runtime_dtos import (
    CreateSessionInput,
    CreateSessionOutput,
    ListAgentSessionsInput,
    ListAgentSessionsOutput,
    ListAgentSessionsPageOutput,
)
from modules.agent.application.interfaces.outbox import OutboxEventWriter
from modules.agent.application.interfaces.repositories import (
    AgentReleaseRepository,
    AgentRepository,
)
from modules.agent.application.interfaces.runtime_session_repository import (
    RuntimeSessionRepository,
)
from modules.agent.domain.entities import Session
from modules.agent.domain.enums import ReleaseStatus, RuntimeSessionMode, SessionStatus
from modules.agent.domain.errors import (
    AgentNotFoundError,
    RuntimeEnvironmentNotReadyError,
)
from modules.agent.domain.events import AgentSessionCreatedV1
from shared.contracts.errors import ValidationError

_LEGACY_RUNTIME_KEYS = {"runtime_environment", "loaded_release_id", "release_version"}
_VALID_ENVIRONMENTS = {"draft", "staging", "production"}


def _release_sort_key(release: Any) -> float:
    value = getattr(release, "updated_at", None) or getattr(
        release, "created_at", None
    )
    return value.timestamp() if value is not None else 0.0


def _session_data(data: dict | None) -> dict | None:
    if not isinstance(data, dict):
        return None
    sanitized = {
        key: value for key, value in data.items() if key not in _LEGACY_RUNTIME_KEYS
    }
    return sanitized or None


class EnvironmentAwareCreateSessionUseCase:
    def __init__(
        self,
        session_repo: RuntimeSessionRepository,
        agent_repo: AgentRepository,
        release_repo: AgentReleaseRepository,
        outbox: OutboxEventWriter,
    ) -> None:
        self._session_repo = session_repo
        self._agent_repo = agent_repo
        self._release_repo = release_repo
        self._outbox = outbox

    async def _opening_release_id(
        self,
        agent_id: UUID,
        environment: str,
    ) -> UUID | None:
        if environment == "draft":
            return None
        if environment == "production":
            release = await self._release_repo.get_active_production(agent_id)
            if release is None:
                raise RuntimeEnvironmentNotReadyError("production", agent_id)
            return release.id

        get_active_staging = getattr(
            self._release_repo, "get_active_staging", None
        )
        if callable(get_active_staging):
            release = await get_active_staging(agent_id)
        else:
            releases = await self._release_repo.list_by_status(
                agent_id, ReleaseStatus.staging
            )
            release = max(releases, key=_release_sort_key) if releases else None
        if release is None:
            raise RuntimeEnvironmentNotReadyError("staging", agent_id)
        return release.id

    async def execute(
        self, input_dto: CreateSessionInput
    ) -> CreateSessionOutput:
        environment = input_dto.runtime_environment
        if environment not in _VALID_ENVIRONMENTS:
            raise ValidationError(
                "runtime_environment must be draft, staging or production"
            )

        agent = await self._agent_repo.get_by_id(input_dto.agent_id)
        if agent is None or agent.project_id != input_dto.project_id:
            raise AgentNotFoundError(input_dto.agent_id)

        opened_release_id = await self._opening_release_id(
            input_dto.agent_id, environment
        )
        session = Session(
            project_id=input_dto.project_id,
            agent_id=input_dto.agent_id,
            runtime_environment=environment,
            opened_release_id=opened_release_id,
            external_session_id=input_dto.external_session_id,
            tenant_id=input_dto.tenant_id,
            user_id=input_dto.user_id,
            mode=input_dto.mode,
            data=_session_data(input_dto.data),
        )
        created = await self._session_repo.create(session)
        project_id = cast(UUID, created.project_id)
        agent_id = cast(UUID, created.agent_id)

        await self._outbox.write(
            AgentSessionCreatedV1.create(
                session_id=created.id,
                project_id=project_id,
                agent_id=agent_id,
                payload={
                    "mode": created.mode,
                    "runtime_environment": created.runtime_environment,
                    "opened_release_id": str(created.opened_release_id)
                    if created.opened_release_id
                    else None,
                },
            )
        )

        return CreateSessionOutput(
            id=created.id,
            project_id=project_id,
            agent_id=agent_id,
            runtime_environment=created.runtime_environment,
            opened_release_id=created.opened_release_id,
            external_session_id=created.external_session_id,
            tenant_id=created.tenant_id,
            user_id=created.user_id,
            status=created.status,
            mode=created.mode,
            data=_session_data(created.data),
            external_context_snapshot=created.external_context_snapshot,
            last_message_at=created.last_message_at,
            created_at=created.created_at,
            updated_at=created.updated_at,
        )


class EnvironmentAwareListAgentSessionsUseCase:
    def __init__(self, session_repo: RuntimeSessionRepository) -> None:
        self._session_repo = session_repo

    async def execute(
        self, input_dto: ListAgentSessionsInput
    ) -> ListAgentSessionsPageOutput:
        environment = input_dto.environment or "draft"
        if environment not in _VALID_ENVIRONMENTS:
            raise ValidationError(
                "environment must be draft, staging or production"
            )

        page = await self._session_repo.paginate_by_agent_environment(
            input_dto.project_id,
            input_dto.agent_id,
            environment,
            limit=input_dto.limit,
            cursor=input_dto.cursor,
        )
        items = [
            ListAgentSessionsOutput(
                id=session.id,
                project_id=cast(UUID, session.project_id),
                agent_id=cast(UUID, session.agent_id),
                runtime_environment=session.runtime_environment,
                opened_release_id=session.opened_release_id,
                status=SessionStatus(session.status),
                mode=RuntimeSessionMode(session.mode),
                data=_session_data(session.data),
                external_context_snapshot=session.external_context_snapshot,
                last_message_at=session.last_message_at,
                created_at=session.created_at,
                message_count=message_count,
            )
            for session, message_count in page.items
        ]
        return ListAgentSessionsPageOutput(
            items=items,
            next_cursor=page.next_cursor,
            has_next=page.has_next,
        )
