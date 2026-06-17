import secrets
from hashlib import sha256

from modules.core.domain.entities import ApiKey
from modules.core.domain.errors import ProjectNotFoundError
from modules.core.domain.repositories import ApiKeyRepository, ProjectRepository
from modules.core.application.dtos.create_api_key_dtos import CreateApiKeyInput, CreateApiKeyOutput
from shared.messaging.outbox_writer import OutboxEventWriter


class CreateApiKeyUseCase:

    def __init__(
        self,
        project_repo: ProjectRepository,
        api_key_repo: ApiKeyRepository,
        outbox: OutboxEventWriter,
    ) -> None:
        self._project_repo = project_repo
        self._api_key_repo = api_key_repo
        self._outbox = outbox

    async def execute(self, input_dto: CreateApiKeyInput) -> CreateApiKeyOutput:
        project = await self._project_repo.get_by_id(input_dto.project_id)
        if not project:
            raise ProjectNotFoundError(input_dto.project_id)

        raw = "rai_" + secrets.token_hex(32)
        key_hash = sha256(raw.encode()).digest()
        key_prefix = raw[:10]

        api_key = ApiKey(
            project_id=input_dto.project_id,
            name=input_dto.name,
            key_prefix=key_prefix,
            key_hash=key_hash,
            scopes=input_dto.scopes,
            created_by_user_id=input_dto.created_by_user_id,
        )
        saved = await self._api_key_repo.save(api_key)

        await self._outbox.write(
            aggregate_type="api_key",
            aggregate_id=saved.id,
            event_type="api_key.created.v1",
            payload={
                "project_id": str(saved.project_id),
                "name": saved.name,
            },
        )

        return CreateApiKeyOutput(
            id=saved.id,
            project_id=saved.project_id,
            name=saved.name,
            key_prefix=saved.key_prefix,
            key_hash=saved.key_hash,
            status=saved.status,
            created_at=saved.created_at,
        )
