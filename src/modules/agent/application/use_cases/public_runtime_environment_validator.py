from uuid import UUID

from modules.agent.domain.enums import ReleaseStatus
from modules.agent.domain.errors import RuntimeEnvironmentNotReadyError
from modules.agent.domain.repositories import AgentReleaseRepository


class PublicRuntimeEnvironmentValidator:
    def __init__(self, release_repo: AgentReleaseRepository) -> None:
        self._release_repo = release_repo

    async def validate(self, agent_id: UUID, environment: str) -> None:
        if environment == ReleaseStatus.production.value:
            release = await self._release_repo.get_active_production(agent_id)
            if release is None:
                raise RuntimeEnvironmentNotReadyError(environment, agent_id)
            return

        if environment == ReleaseStatus.staging.value:
            releases = await self._release_repo.list_by_status(
                agent_id, ReleaseStatus.staging
            )
            if not releases:
                raise RuntimeEnvironmentNotReadyError(environment, agent_id)
            return

        raise ValueError("Unsupported runtime environment")
