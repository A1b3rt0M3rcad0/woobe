from __future__ import annotations

from modules.agent.application.use_cases.auto_compatible_release_lifecycle import AutoCompatibleReleaseLifecycleUseCase
from modules.agent.application.use_cases.release_lifecycle_use_cases import AutoCreateReleaseUseCase
from modules.agent.domain.entities import AgentRelease
from modules.agent.domain.errors import ReleaseNotFoundError


class KnowledgeSafeCreateReleaseUseCase(AutoCreateReleaseUseCase):
    def __init__(self, release_repo, knowledge_validator) -> None:
        super().__init__(release_repo)
        self._knowledge_validator = knowledge_validator

    async def execute(self, input_dto, change_kind: str = "change"):
        candidate = AgentRelease(
            project_id=input_dto.project_id,
            agent_id=input_dto.agent_id,
            knowledge_version_id=input_dto.knowledge_version_id,
        )
        await self._knowledge_validator.validate(candidate)
        return await super().execute(input_dto, change_kind=change_kind)


class KnowledgeSafeReleaseLifecycleUseCase(AutoCompatibleReleaseLifecycleUseCase):
    def __init__(self, release_repo, knowledge_validator) -> None:
        super().__init__(release_repo)
        self._knowledge_validator = knowledge_validator

    async def execute(self, agent_id, release_id, input_dto=None, **kwargs):
        release = await self._release_repo.get_by_id(release_id)
        if release is None or release.agent_id != agent_id:
            raise ReleaseNotFoundError
        await self._knowledge_validator.validate(release)
        return await super().execute(agent_id, release_id, input_dto, **kwargs)


class KnowledgeSafeRollbackReleaseUseCase(KnowledgeSafeReleaseLifecycleUseCase):
    pass
