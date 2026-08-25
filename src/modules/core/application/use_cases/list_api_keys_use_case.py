from datetime import UTC, datetime

from modules.core.application.dtos.list_api_keys_dtos import (
    ListApiKeysInput,
    ListApiKeysOutput,
)
from modules.core.domain.enums import ApiKeyStatus
from modules.core.domain.repositories import ApiKeyRepository
from shared.security.api_keys import format_api_key_prefix


def _effective_status(key, now: datetime) -> ApiKeyStatus:
    if key.status != ApiKeyStatus.active or key.expires_at is None:
        return key.status

    expires_at = key.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    else:
        expires_at = expires_at.astimezone(UTC)

    return ApiKeyStatus.expired if expires_at <= now else key.status


class ListApiKeysByProjectUseCase:
    def __init__(self, api_key_repo: ApiKeyRepository) -> None:
        self._api_key_repo = api_key_repo

    async def execute(self, input_dto: ListApiKeysInput) -> list[ListApiKeysOutput]:
        keys = await self._api_key_repo.list_by_project(input_dto.project_id)
        now = datetime.now(UTC)
        return [
            ListApiKeysOutput(
                id=key.id,
                credential_id=key.credential_id or key.id,
                project_id=key.project_id,
                name=key.name,
                description=key.description,
                key_prefix=format_api_key_prefix(
                    key.key_prefix,
                    key_version=key.key_version,
                    kind=key.kind.value,
                    environment=key.environment.value if key.environment else None,
                ),
                scopes=list(key.scopes),
                kind=key.kind,
                agent_id=key.agent_id,
                target_type=key.target_type,
                target_id=key.target_id,
                environment=key.environment,
                interfaces=list(key.interfaces),
                status=_effective_status(key, now),
                last_used_at=key.last_used_at,
                expires_at=key.expires_at,
                revoked_at=key.revoked_at,
                rotated_from_id=key.rotated_from_id,
                created_at=key.created_at,
            )
            for key in keys
        ]
