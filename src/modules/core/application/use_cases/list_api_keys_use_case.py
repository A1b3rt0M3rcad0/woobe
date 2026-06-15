from modules.core.domain.repositories import ApiKeyRepository
from modules.core.application.dtos.list_api_keys_dtos import ListApiKeysInput, ListApiKeysOutput


class ListApiKeysByProjectUseCase:

    def __init__(self, api_key_repo: ApiKeyRepository) -> None:
        self._api_key_repo = api_key_repo

    async def execute(self, input_dto: ListApiKeysInput) -> list[ListApiKeysOutput]:
        keys = await self._api_key_repo.list_by_project(input_dto.project_id)
        return [ListApiKeysOutput(
            id=k.id,
            name=k.name,
            key_prefix=k.key_prefix,
            status=k.status,
        ) for k in keys]
