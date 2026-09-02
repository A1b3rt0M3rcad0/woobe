from uuid import UUID

from modules.core.application.dtos.runtime_api_key_dtos import (
    CreateRuntimeApiKeyInput,
    CreateRuntimeApiKeyOutput,
)
from modules.core.domain.entities import ApiKey
from modules.core.domain.enums import ApiKeyKind, RuntimeTargetType
from modules.core.domain.errors import ProjectNotFoundError
from modules.core.application.interfaces.api_key_issuer import ApiKeyIssuer
from modules.core.application.interfaces.outbox import OutboxEventWriter
from modules.core.application.interfaces.repositories import ApiKeyRepository, ProjectRepository
from modules.core.application.interfaces.runtime_key_target_reader import RuntimeKeyTargetReader
from shared.contracts.errors import NotFoundError
from modules.core.domain.api_keys import API_KEY_SCOPE_RUNTIME_EXECUTE


class CreateRuntimeApiKeyUseCase:
    def __init__(
        self,
        project_repo: ProjectRepository,
        target_reader: RuntimeKeyTargetReader,
        api_key_repo: ApiKeyRepository,
        outbox: OutboxEventWriter,
        api_key_issuer: ApiKeyIssuer,
    ) -> None:
        self._project_repo = project_repo
        self._target_reader = target_reader
        self._api_key_repo = api_key_repo
        self._outbox = outbox
        self._api_key_issuer = api_key_issuer

    async def execute(
        self, input_dto: CreateRuntimeApiKeyInput
    ) -> CreateRuntimeApiKeyOutput:
        project = await self._project_repo.get_by_id(input_dto.project_id)
        if project is None:
            raise ProjectNotFoundError(input_dto.project_id)

        target_id = input_dto.target_id
        if target_id is None:
            raise NotFoundError("Runtime key target is missing")
        target_project_id = await self._target_reader.get_target_project_id(
            input_dto.target_type,
            target_id,
        )
        if target_project_id != input_dto.project_id:
            raise NotFoundError(
                f"{input_dto.target_type.value.title()} not found: {target_id}"
            )

        issued = self._api_key_issuer.issue_runtime(input_dto.environment.value)
        interfaces = [interface.value for interface in input_dto.interfaces]
        api_key = ApiKey(
            project_id=input_dto.project_id,
            name=input_dto.name,
            description=input_dto.description,
            key_prefix=issued.public_prefix,
            key_hash=issued.digest,
            key_version=issued.key_version,
            scopes=[API_KEY_SCOPE_RUNTIME_EXECUTE],
            kind=ApiKeyKind.runtime,
            agent_id=(
                target_id if input_dto.target_type == RuntimeTargetType.agent else None
            ),
            target_type=input_dto.target_type,
            target_id=target_id,
            environment=input_dto.environment,
            interfaces=interfaces,
            expires_at=input_dto.expires_at,
            created_by_user_id=input_dto.created_by_user_id,
        )
        api_key.credential_id = api_key.id
        saved = await self._api_key_repo.save(api_key)

        await self._outbox.write(
            aggregate_type="api_key",
            aggregate_id=saved.id,
            event_type="runtime_api_key.created.v1",
            payload={
                "project_id": str(saved.project_id),
                "credential_id": str(saved.credential_id or saved.id),
                "name": saved.name,
                "description": saved.description,
                "target_type": saved.target_type.value if saved.target_type else None,
                "target_id": str(saved.target_id) if saved.target_id else None,
                "agent_id": str(saved.agent_id) if saved.agent_id else None,
                "environment": saved.environment.value if saved.environment else None,
                "interfaces": list(saved.interfaces),
                "key_prefix": issued.display_prefix,
                "expires_at": saved.expires_at.isoformat()
                if saved.expires_at
                else None,
            },
            routing_key="runtime_api_key.created.v1",
            idempotency_key=f"core:runtime_api_key.created.v1:{saved.id}",
        )

        return CreateRuntimeApiKeyOutput(
            id=saved.id,
            credential_id=saved.credential_id or saved.id,
            project_id=saved.project_id,
            name=saved.name,
            description=saved.description,
            key=issued.value,
            key_prefix=issued.display_prefix,
            scopes=list(saved.scopes),
            kind=saved.kind.value,
            target_type=input_dto.target_type,
            target_id=target_id,
            agent_id=(
                target_id if input_dto.target_type == RuntimeTargetType.agent else None
            ),
            environment=input_dto.environment,
            interfaces=list(saved.interfaces),
            status=saved.status,
            expires_at=saved.expires_at,
            created_at=saved.created_at,
        )
