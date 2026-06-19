from datetime import UTC, datetime

from modules.core.application.dtos.api_key_lifecycle_dtos import (
    RevokeApiKeyInput,
    RevokeApiKeyOutput,
    RotateApiKeyInput,
    RotateApiKeyOutput,
)
from modules.core.domain.entities import ApiKey
from modules.core.domain.enums import ApiKeyStatus
from modules.core.domain.errors import ApiKeyNotActiveError, ApiKeyNotFoundError
from modules.core.domain.repositories import ApiKeyRepository
from shared.infra.errors import ValidationError
from shared.messaging.outbox_writer import OutboxEventWriter
from shared.security.api_keys import (
    API_KEY_VERSION,
    issue_project_api_key,
    normalize_project_api_key_scopes,
)


class RevokeApiKeyUseCase:
    def __init__(
        self,
        api_key_repo: ApiKeyRepository,
        outbox: OutboxEventWriter,
    ) -> None:
        self._api_key_repo = api_key_repo
        self._outbox = outbox

    async def execute(self, input_dto: RevokeApiKeyInput) -> RevokeApiKeyOutput:
        api_key = await self._api_key_repo.get_by_id(input_dto.api_key_id)
        if api_key is None or api_key.project_id != input_dto.project_id:
            raise ApiKeyNotFoundError("API key not found")

        now = datetime.now(UTC)
        if api_key.revoked_at is None:
            api_key.status = ApiKeyStatus.revoked
            api_key.revoked_at = now
            api_key.updated_at = now
            api_key = await self._api_key_repo.update(api_key)
            await self._outbox.write(
                aggregate_type="api_key",
                aggregate_id=api_key.id,
                event_type="api_key.revoked.v1",
                payload={
                    "project_id": str(api_key.project_id),
                    "revoked_by_user_id": str(input_dto.revoked_by_user_id),
                    "revoked_at": now.isoformat(),
                },
                routing_key="api_key.revoked.v1",
                idempotency_key=f"core:api_key.revoked.v1:{api_key.id}",
            )

        return RevokeApiKeyOutput(
            id=api_key.id,
            project_id=api_key.project_id,
            status=ApiKeyStatus.revoked,
            revoked_at=api_key.revoked_at or now,
        )


class RotateApiKeyUseCase:
    def __init__(
        self,
        api_key_repo: ApiKeyRepository,
        outbox: OutboxEventWriter,
    ) -> None:
        self._api_key_repo = api_key_repo
        self._outbox = outbox

    async def execute(self, input_dto: RotateApiKeyInput) -> RotateApiKeyOutput:
        current = await self._api_key_repo.get_by_id(input_dto.api_key_id)
        if current is None or current.project_id != input_dto.project_id:
            raise ApiKeyNotFoundError("API key not found")
        if current.status != ApiKeyStatus.active or current.revoked_at is not None:
            raise ApiKeyNotActiveError("Only active API keys can be rotated")

        requested_scopes = (
            input_dto.scopes if input_dto.scopes is not None else current.scopes
        )
        try:
            scopes = normalize_project_api_key_scopes(requested_scopes)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        now = datetime.now(UTC)
        current.status = ApiKeyStatus.revoked
        current.revoked_at = now
        current.updated_at = now
        await self._api_key_repo.update(current)

        issued = issue_project_api_key()
        replacement = ApiKey(
            project_id=current.project_id,
            name=input_dto.name or current.name,
            key_prefix=issued.public_prefix,
            key_hash=issued.digest,
            key_version=API_KEY_VERSION,
            scopes=scopes,
            expires_at=(
                input_dto.expires_at
                if input_dto.expires_at is not None
                else current.expires_at
            ),
            created_by_user_id=input_dto.rotated_by_user_id,
            rotated_from_id=current.id,
        )
        saved = await self._api_key_repo.save(replacement)

        await self._outbox.write(
            aggregate_type="api_key",
            aggregate_id=saved.id,
            event_type="api_key.rotated.v1",
            payload={
                "project_id": str(saved.project_id),
                "rotated_from_id": str(current.id),
                "rotated_by_user_id": str(input_dto.rotated_by_user_id),
                "key_prefix": issued.display_prefix,
                "scopes": list(saved.scopes),
            },
            routing_key="api_key.rotated.v1",
            idempotency_key=f"core:api_key.rotated.v1:{saved.id}",
        )

        return RotateApiKeyOutput(
            id=saved.id,
            project_id=saved.project_id,
            name=saved.name,
            key=issued.value,
            key_prefix=issued.display_prefix,
            scopes=list(saved.scopes),
            status=saved.status,
            expires_at=saved.expires_at,
            created_at=saved.created_at,
            rotated_from_id=current.id,
        )
