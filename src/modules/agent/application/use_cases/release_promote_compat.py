from __future__ import annotations

from uuid import UUID

from modules.agent.application.use_cases.release_lifecycle_use_cases import ReleaseLifecycleUseCase
from modules.agent.application.interfaces.repositories import AgentReleaseRepository


class PromoteReleaseUseCase(ReleaseLifecycleUseCase):
    def __init__(self, release_repo: AgentReleaseRepository) -> None:
        super().__init__(release_repo)

    async def execute(self, agent_id: UUID, release_id: UUID, input_dto=None):
        return await super().execute(
            agent_id,
            release_id,
            target_status="production",
            user_id=getattr(input_dto, "user_id", None),
        )
