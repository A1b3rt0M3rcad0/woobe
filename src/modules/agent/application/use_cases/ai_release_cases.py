from modules.agent.application.use_cases.release_lifecycle_use_cases import AutoCreateReleaseUseCase as CreateReleaseUseCase
from modules.agent.application.use_cases.release_lifecycle_use_cases import ReleaseLifecycleUseCase as PromoteReleaseUseCase
from modules.agent.application.use_cases.release_lifecycle_use_cases import _release_to_output
from modules.agent.application.dtos.ai_dtos import ListReleasesOutput
from modules.agent.domain.enums import ReleaseStatus


class RollbackReleaseUseCase(PromoteReleaseUseCase):
    pass


class ListReleasesUseCase:
    def __init__(self, release_repo):
        self._release_repo = release_repo

    async def execute(self, agent_id):
        return [ListReleasesOutput(**_release_to_output(item).model_dump()) for item in await self._release_repo.list_by_agent(agent_id)]


class GetReleaseUseCase:
    def __init__(self, release_repo):
        self._release_repo = release_repo

    async def execute(self, release_id):
        item = await self._release_repo.get_by_id(release_id)
        if item is None:
            from modules.agent.domain.errors import ReleaseNotFoundError
            raise ReleaseNotFoundError
        return item


class DeleteReleaseUseCase:
    def __init__(self, release_repo):
        self._release_repo = release_repo

    async def execute(self, release_id):
        item = await self._release_repo.get_by_id(release_id)
        if item is None:
            from modules.agent.domain.errors import ReleaseNotFoundError
            raise ReleaseNotFoundError
        if item.status == ReleaseStatus.production:
            from shared.infra.errors import ValidationError
            raise ValidationError("Cannot delete a production release. Rollback first.")
        await self._release_repo.delete(release_id)
