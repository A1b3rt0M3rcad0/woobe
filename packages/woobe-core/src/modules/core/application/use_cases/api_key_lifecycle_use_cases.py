from shared.security.delegation import ApiKeyDelegationPolicy
from shared.security.control_plane import require_expiration_ceiling
from shared.contracts.errors import AuthorizationError
from datetime import UTC, datetime

from modules.core.application.dtos.api_key_lifecycle_dtos import (
    RevokeApiKeyInput,
    RevokeApiKeyOutput,
    RotateApiKeyInput,
    RotateApiKeyOutput,
    UpdateApiKeyCredentialInput,
    UpdateApiKeyCredentialOutput,
)
from modules.core.domain.entities import ApiKey
from modules.core.domain.enums import ApiKeyKind, ApiKeyStatus
from modules.core.domain.errors import ApiKeyNotActiveError, ApiKeyNotFoundError
from modules.core.domain.repositories import ApiKeyRepository
from shared.contracts.errors import ValidationError
from shared.messaging.outbox_writer import OutboxEventWriter
from shared.security.api_keys import (
    issue_project_api_key,
    issue_runtime_api_key,
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
                    "credential_id": str(api_key.credential_id or api_key.id),
                    "revoked_by_user_id": (
                        str(input_dto.revoked_by_user_id)
                        if input_dto.revoked_by_user_id
                        else None
                    ),
                    "revoked_by_control_key_id": (
                        str(input_dto.revoked_by_control_key_id)
                        if input_dto.revoked_by_control_key_id
                        else None
                    ),
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
        delegation_policy: ApiKeyDelegationPolicy | None = None,
    ) -> None:
        self._api_key_repo = api_key_repo
        self._outbox = outbox
        self._delegation_policy = delegation_policy

    async def execute(self, input_dto: RotateApiKeyInput) -> RotateApiKeyOutput:
        current = await self._api_key_repo.get_by_id(input_dto.api_key_id)
        if current is None or current.project_id != input_dto.project_id:
            raise ApiKeyNotFoundError("API key not found")
        if current.status != ApiKeyStatus.active or current.revoked_at is not None:
            raise ApiKeyNotActiveError("Only active API keys can be rotated")
        if current.kind == ApiKeyKind.chat_surface:
            raise ValidationError(
                "Rotate ChatSurface Access Keys through the ChatSurface endpoint"
            )

        requested_scopes = (
            current.scopes
            if current.kind == ApiKeyKind.runtime
            else input_dto.scopes
            if input_dto.scopes is not None
            else current.scopes
        )
        try:
            scopes = normalize_project_api_key_scopes(requested_scopes)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        expires_at = input_dto.expires_at or current.expires_at
        delegation_expires_at = current.delegation_expires_at
        try:
            require_expiration_ceiling(expires_at, delegation_expires_at)
        except ValueError as exc:
            raise AuthorizationError(str(exc)) from exc

        if input_dto.rotated_by_control_key_id is not None:
            if self._delegation_policy is None:
                raise AuthorizationError("Control key delegation policy is required")
            conditions = (
                {
                    "environments": [current.environment.value],
                    "target_types": [current.target_type.value],
                    "target_ids": [str(current.target_id)],
                    "interfaces": list(current.interfaces),
                }
                if current.kind == ApiKeyKind.runtime
                else {}
            )
            actor_ceiling = await self._delegation_policy.validate(
                actor_key_id=input_dto.rotated_by_control_key_id,
                project_id=current.project_id,
                scopes=scopes,
                conditions=conditions,
                expires_at=expires_at,
            )

            ceilings = [
                value
                for value in (delegation_expires_at, actor_ceiling)
                if value is not None
            ]
            delegation_expires_at = min(ceilings) if ceilings else None

        if current.kind == ApiKeyKind.runtime:
            if current.environment is None:
                raise ValidationError("Runtime API key environment is missing")
            issued = issue_runtime_api_key(current.environment.value)
        else:
            issued = issue_project_api_key()

        now = datetime.now(UTC)
        current.status = ApiKeyStatus.revoked
        current.revoked_at = now
        current.updated_at = now
        await self._api_key_repo.update(current)

        replacement = ApiKey(
            project_id=current.project_id,
            credential_id=current.credential_id or current.id,
            name=input_dto.name or current.name,
            description=current.description,
            key_prefix=issued.public_prefix,
            key_hash=issued.digest,
            key_version=issued.key_version,
            scopes=scopes,
            kind=current.kind,
            agent_id=current.agent_id,
            target_type=current.target_type,
            target_id=current.target_id,
            environment=current.environment,
            interfaces=list(current.interfaces),
            expires_at=(
                input_dto.expires_at
                if input_dto.expires_at is not None
                else current.expires_at
            ),
            delegation_expires_at=delegation_expires_at,
            created_by_user_id=input_dto.rotated_by_user_id,
            created_by_control_key_id=input_dto.rotated_by_control_key_id,
            rotated_from_id=current.id,
        )
        saved = await self._api_key_repo.save(replacement)

        await self._outbox.write(
            aggregate_type="api_key",
            aggregate_id=saved.id,
            event_type="api_key.rotated.v1",
            payload={
                "project_id": str(saved.project_id),
                "credential_id": str(saved.credential_id or saved.id),
                "rotated_from_id": str(current.id),
                "rotated_by_user_id": (
                    str(input_dto.rotated_by_user_id)
                    if input_dto.rotated_by_user_id
                    else None
                ),
                "rotated_by_control_key_id": (
                    str(input_dto.rotated_by_control_key_id)
                    if input_dto.rotated_by_control_key_id
                    else None
                ),
                "key_prefix": issued.display_prefix,
                "scopes": list(saved.scopes),
                "kind": saved.kind.value,
                "target_type": saved.target_type.value if saved.target_type else None,
                "target_id": str(saved.target_id) if saved.target_id else None,
                "agent_id": str(saved.agent_id) if saved.agent_id else None,
                "environment": saved.environment.value if saved.environment else None,
                "interfaces": list(saved.interfaces),
            },
            routing_key="api_key.rotated.v1",
            idempotency_key=f"core:api_key.rotated.v1:{saved.id}",
        )

        return RotateApiKeyOutput(
            id=saved.id,
            credential_id=saved.credential_id or saved.id,
            project_id=saved.project_id,
            name=saved.name,
            description=saved.description,
            key=issued.value,
            key_prefix=issued.display_prefix,
            scopes=list(saved.scopes),
            kind=saved.kind,
            agent_id=saved.agent_id,
            target_type=saved.target_type,
            target_id=saved.target_id,
            environment=saved.environment,
            interfaces=list(saved.interfaces),
            status=saved.status,
            expires_at=saved.expires_at,
            created_at=saved.created_at,
            rotated_from_id=current.id,
        )


class UpdateApiKeyCredentialUseCase:
    def __init__(
        self,
        api_key_repo: ApiKeyRepository,
        outbox: OutboxEventWriter,
    ) -> None:
        self._api_key_repo = api_key_repo
        self._outbox = outbox

    async def execute(
        self,
        input_dto: UpdateApiKeyCredentialInput,
    ) -> UpdateApiKeyCredentialOutput:
        current = await self._api_key_repo.get_by_id(input_dto.api_key_id)
        if current is None or current.project_id != input_dto.project_id:
            raise ApiKeyNotFoundError("API key credential not found")

        credential_id = current.credential_id or current.id
        now = datetime.now(UTC)
        saved = await self._api_key_repo.update_credential_metadata(
            credential_id,
            name=input_dto.name,
            description=input_dto.description,
        )

        await self._outbox.write(
            aggregate_type="api_key_credential",
            aggregate_id=credential_id,
            event_type="api_key_credential.updated.v1",
            payload={
                "project_id": str(saved.project_id),
                "name": saved.name,
                "description": saved.description,
                "updated_by_user_id": (
                    str(input_dto.updated_by_user_id)
                    if input_dto.updated_by_user_id
                    else None
                ),
                "updated_by_control_key_id": (
                    str(input_dto.updated_by_control_key_id)
                    if input_dto.updated_by_control_key_id
                    else None
                ),
                "updated_at": now.isoformat(),
            },
            routing_key="api_key_credential.updated.v1",
            idempotency_key=(
                f"core:api_key_credential.updated.v1:{credential_id}:{now.isoformat()}"
            ),
        )

        return UpdateApiKeyCredentialOutput(
            id=saved.id,
            credential_id=saved.credential_id or saved.id,
            project_id=saved.project_id,
            name=saved.name,
            description=saved.description,
            kind=saved.kind,
            agent_id=saved.agent_id,
            target_type=saved.target_type,
            target_id=saved.target_id,
            environment=saved.environment,
            updated_at=now,
        )
