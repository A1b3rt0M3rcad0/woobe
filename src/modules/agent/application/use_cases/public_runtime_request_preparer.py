from uuid import UUID

from modules.agent.application.dtos.public_runtime_dtos import PublicRunRequest
from modules.agent.domain.entities import AgentRelease
from modules.agent.domain.enums import ReleaseStatus
from modules.agent.domain.errors import (
    RuntimeEnvironmentNotReadyError,
    SessionNotFoundError,
)
from modules.agent.domain.repositories import (
    AgentReleaseRepository,
    SessionRepository,
)


class PublicRuntimeRequestPreparer:
    def __init__(
        self,
        release_repo: AgentReleaseRepository,
        session_repo: SessionRepository,
    ) -> None:
        self._release_repo = release_repo
        self._session_repo = session_repo

    async def prepare(
        self,
        payload: PublicRunRequest,
        *,
        project_id: UUID,
        agent_id: UUID,
        environment: str,
    ) -> PublicRunRequest:
        release = await self._resolve_release(agent_id, environment)
        session_mode = getattr(release.session_mode, "value", release.session_mode)

        if session_mode == "stateless":
            return payload.model_copy(update={"session_id": None})

        if payload.session_id is not None:
            session = await self._session_repo.get_by_id(payload.session_id)
            if session.project_id != project_id or session.agent_id != agent_id:
                raise SessionNotFoundError(payload.session_id)

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
            releases = await self._release_repo.list_by_status(
                agent_id,
                ReleaseStatus.staging,
            )
            if not releases:
                raise RuntimeEnvironmentNotReadyError(environment, agent_id)
            return releases[0]

        raise ValueError("Unsupported runtime environment")
