from uuid import UUID

from modules.agent.application.dtos.public_runtime_dtos import PublicRunRequest
from modules.agent.domain.entities import AgentRelease
from modules.agent.domain.enums import ReleaseStatus
from modules.agent.domain.errors import (
    AgentNotFoundError,
    RuntimeEnvironmentNotReadyError,
    SessionNotFoundError,
)
from modules.agent.application.interfaces.repositories import (
    AgentReleaseRepository,
    AgentRepository,
    SessionRepository,
)
from shared.contracts.errors import ConflictError


def _session_environment(session) -> str:
    explicit = getattr(session, "runtime_environment", None)
    if explicit in {"draft", "staging", "production"}:
        return explicit
    data = getattr(session, "data", None)
    legacy = data.get("runtime_environment") if isinstance(data, dict) else None
    if legacy in {"draft", "staging", "production"}:
        return legacy
    return "draft"


class PublicRuntimeRequestPreparer:
    def __init__(
        self,
        release_repo: AgentReleaseRepository,
        session_repo: SessionRepository,
        agent_repo: AgentRepository,
    ) -> None:
        self._release_repo = release_repo
        self._session_repo = session_repo
        self._agent_repo = agent_repo

    async def prepare(
        self,
        payload: PublicRunRequest,
        project_id: UUID,
        agent_id: UUID,
        environment: str,
    ) -> PublicRunRequest:
        await self._resolve_release(agent_id, environment)

        agent = await self._agent_repo.get_by_id(agent_id)
        if agent is None or agent.project_id != project_id:
            raise AgentNotFoundError(agent_id)

        if payload.session_id is not None:
            session = await self._session_repo.get_by_id(payload.session_id)
            if session.project_id != project_id or session.agent_id != agent_id:
                raise SessionNotFoundError(payload.session_id)

            session_environment = _session_environment(session)
            if session_environment != environment:
                raise ConflictError(
                    f"Agent Session belongs to {session_environment}, not {environment}"
                )

        return payload

    async def _resolve_release(
        self,
        agent_id: UUID,
        environment: str,
    ) -> AgentRelease:
        if environment == ReleaseStatus.production.value:
            release = await self._release_repo.get_active_production(agent_id)
            if release is None:
                raise RuntimeEnvironmentNotReadyError(environment, agent_id)
            return release

        if environment == ReleaseStatus.staging.value:
            selected = getattr(self._release_repo, "get_active_staging", None)
            if callable(selected):
                release = await selected(agent_id)
            else:
                releases = await self._release_repo.list_by_status(agent_id, ReleaseStatus.staging)
                release = releases[0] if releases else None
            if release is None:
                raise RuntimeEnvironmentNotReadyError(environment, agent_id)
            return release

        raise ValueError("Unsupported runtime environment")
