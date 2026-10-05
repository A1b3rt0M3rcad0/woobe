from shared.security.delegation import ApiKeyDelegationPolicy
from shared.contracts.errors import AuthorizationError
from modules.core.application.dtos.create_api_key_dtos import (
    CreateApiKeyInput,
    CreateApiKeyOutput,
)
from modules.core.domain.entities import ApiKey
from modules.core.domain.errors import ProjectNotFoundError
from modules.core.domain.repositories import ApiKeyRepository, ProjectRepository
from shared.contracts.errors import ValidationError
from shared.messaging.outbox_writer import OutboxEventWriter
from shared.security.api_keys import (
    issue_project_api_key,
    normalize_project_api_key_scopes,
)


class CreateApiKeyUseCase:
    def __init__(
        self,
        project_repo: ProjectRepository,
        api_key_repo: ApiKeyRepository,
        outbox: OutboxEventWriter,
        delegation_policy: ApiKeyDelegationPolicy | None = None,
    ) -> None:
        self._project_repo = project_repo
        self._api_key_repo = api_key_repo
        self._outbox = outbox
        self._delegation_policy = delegation_policy

    async def execute(self, input_dto: CreateApiKeyInput) -> CreateApiKeyOutput:
        project = await self._project_repo.get_by_id(input_dto.project_id)
        if not project:
            raise ProjectNotFoundError(input_dto.project_id)

        try:
            scopes = normalize_project_api_key_scopes(input_dto.scopes)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc

        if input_dto.created_by_control_key_id is not None:
            if self._delegation_policy is None:
                raise AuthorizationError("Control key delegation policy is required")
            await self._delegation_policy.validate(actor_key_id=input_dto.created_by_control_key_id, project_id=input_dto.project_id, scopes=scopes, conditions={}, expires_at=input_dto.expires_at)

        issued = issue_project_api_key()
        api_key = ApiKey(
            project_id=input_dto.project_id,
            name=input_dto.name,
            description=input_dto.description,
            key_prefix=issued.public_prefix,
            key_hash=issued.digest,
            key_version=issued.key_version,
            scopes=scopes,
            expires_at=input_dto.expires_at,
            created_by_user_id=input_dto.created_by_user_id,
            created_by_control_key_id=input_dto.created_by_control_key_id,
        )
        api_key.credential_id = api_key.id
        saved = await self._api_key_repo.save(api_key)

        await self._outbox.write(
            aggregate_type="api_key",
            aggregate_id=saved.id,
            event_type="api_key.created.v1",
            payload={
                "project_id": str(saved.project_id),
                "credential_id": str(saved.credential_id or saved.id),
                "name": saved.name,
                "description": saved.description,
                "key_prefix": issued.display_prefix,
                "scopes": list(saved.scopes),
                "created_by_user_id": (
                    str(input_dto.created_by_user_id)
                    if input_dto.created_by_user_id
                    else None
                ),
                "created_by_control_key_id": (
                    str(input_dto.created_by_control_key_id)
                    if input_dto.created_by_control_key_id
                    else None
                ),
                "expires_at": saved.expires_at.isoformat()
                if saved.expires_at
                else None,
            },
            routing_key="api_key.created.v1",
            idempotency_key=f"core:api_key.created.v1:{saved.id}",
        )

        return CreateApiKeyOutput(
            id=saved.id,
            credential_id=saved.credential_id or saved.id,
            project_id=saved.project_id,
            name=saved.name,
            description=saved.description,
            key=issued.value,
            key_prefix=issued.display_prefix,
            scopes=list(saved.scopes or scopes),
            status=saved.status,
            expires_at=saved.expires_at,
            created_at=saved.created_at,
        )

