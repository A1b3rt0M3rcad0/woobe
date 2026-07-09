from modules.core.application.dtos.list_api_keys_dtos import (
    ListApiKeysInput,
    ListApiKeysOutput,
)
from modules.core.domain.repositories import ApiKeyRepository
from shared.security.api_keys import format_api_key_prefix


class ListApiKeysByProjectUseCase:
    def __init__(self, api_key_repo: ApiKeyRepository) -> None:
        self._api_key_repo = api_key_repo

    async def execute(self, input_dto: ListApiKeysInput) -> list[ListApiKeysOutput]:
        keys = await self._api_key_repo.list_by_project(input_dto.project_id)
        return [
            ListApiKeysOutput(
                id=key.id,
                project_id=key.project_id,
                name=key.name,
                key_prefix=format_api_key_prefix(key.key_prefix),
                scopes=list(key.scopes),
                kind=key.kind,
                agent_id=key.agent_id,
                environment=key.environment,
                interfaces=list(key.interfaces),
                status=key.status,
                last_used_at=key.last_used_at,
                expires_at=key.expires_at,
                revoked_at=key.revoked_at,
                created_at=key.created_at,
            )
            for key in keys
        ]
