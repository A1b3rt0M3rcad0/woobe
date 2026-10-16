from uuid import UUID

from modules.agent.application.dtos.ai_dtos import CreateProviderCredentialInput, CreateProviderCredentialOutput, ListProviderCredentialsInput, ListProviderCredentialsOutput, UpdateProviderCredentialInput, UpdateProviderCredentialOutput
from modules.agent.domain.entities import ProviderCredential
from modules.agent.domain.events import AgentProviderCredentialCreatedV1, AgentProviderCredentialUpdatedV1
from modules.agent.application.interfaces.repositories import ProviderCredentialRepository
from shared.security.crypto import encrypt_secret
from modules.agent.application.interfaces.outbox import OutboxEventWriter


class CreateProviderCredentialUseCase:
    def __init__(self, credential_repo: ProviderCredentialRepository, outbox: OutboxEventWriter, encryption_key: str) -> None:
        self._credential_repo = credential_repo
        self._outbox = outbox
        self._encryption_key = encryption_key

    async def execute(self, input_dto: CreateProviderCredentialInput) -> CreateProviderCredentialOutput:
        saved = await self._credential_repo.save(ProviderCredential(project_id=input_dto.project_id, provider=input_dto.provider, name=input_dto.name, encrypted_secret=encrypt_secret(input_dto.secret, self._encryption_key) if input_dto.secret is not None else "", authentication=input_dto.authentication, metadata=input_dto.metadata))
        await self._outbox.write(AgentProviderCredentialCreatedV1.create(credential_id=saved.id, project_id=saved.project_id, provider=saved.provider.value if hasattr(saved.provider, "value") else saved.provider, name=saved.name))
        return CreateProviderCredentialOutput(id=saved.id, project_id=saved.project_id, provider=saved.provider, name=saved.name, status=saved.status, created_at=saved.created_at, metadata=saved.metadata, authentication=saved.authentication, binding_revision=saved.binding_revision)


class UpdateProviderCredentialUseCase:
    def __init__(self, credential_repo: ProviderCredentialRepository, outbox: OutboxEventWriter, encryption_key: str) -> None:
        self._credential_repo = credential_repo
        self._outbox = outbox
        self._encryption_key = encryption_key

    async def execute(self, credential_id: UUID, input_dto: UpdateProviderCredentialInput) -> UpdateProviderCredentialOutput:
        item = await self._credential_repo.get_by_id(credential_id)
        if item is None:
            from modules.agent.domain.errors import CredentialNotFoundError
            raise CredentialNotFoundError(credential_id)
        data = input_dto.model_dump(exclude_unset=True)
        if "secret" in data:
            data["encrypted_secret"] = encrypt_secret(input_dto.secret, self._encryption_key)
            del data["secret"]
        if "authentication" in data:
            if item.authentication is None and item.encrypted_secret:
                from shared.contracts.project_configuration import ConfigurationError
                raise ConfigurationError("LEGACY_ENVIRONMENT_REQUIRED")
            item.encrypted_secret = ""
        for field, value in data.items():
            setattr(item, field, value)
        saved = await self._credential_repo.update(item)
        await self._outbox.write(AgentProviderCredentialUpdatedV1.create(credential_id=saved.id, project_id=saved.project_id, provider=saved.provider.value if hasattr(saved.provider, "value") else saved.provider, name=saved.name))
        return UpdateProviderCredentialOutput(id=saved.id, project_id=saved.project_id, provider=saved.provider, name=saved.name, status=saved.status, created_at=saved.created_at, updated_at=saved.updated_at, metadata=saved.metadata, authentication=saved.authentication, binding_revision=saved.binding_revision)


class ListProviderCredentialsUseCase:
    def __init__(self, credential_repo: ProviderCredentialRepository, provider_registry=None) -> None:
        self._credential_repo = credential_repo
        self._provider_registry = provider_registry

    def _supports_embedding(self, provider):
        if self._provider_registry is None:
            return None
        from modules.agent.domain.model_spec import ModelOperations
        from modules.agent.domain.provider_identity import canonical_provider_key
        provider = canonical_provider_key(provider)
        return self._provider_registry.contains(provider) and ModelOperations.EMBEDDING_CREATE in self._provider_registry.resolve(provider).manifest.supported_operations

    async def execute(self, input_dto: ListProviderCredentialsInput) -> list[ListProviderCredentialsOutput]:
        if not input_dto.project_id:
            return []
        return [ListProviderCredentialsOutput(id=item.id, project_id=item.project_id, provider=item.provider, name=item.name, status=item.status, created_at=item.created_at, metadata=item.metadata, authentication=item.authentication, binding_revision=item.binding_revision, supports_embedding=self._supports_embedding(item.provider)) for item in await self._credential_repo.list_by_project(input_dto.project_id)]
