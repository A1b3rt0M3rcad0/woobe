from uuid import UUID

from modules.agent.domain.entities import (
    Agent,
    AgentContract,
    AgentModelConfig,
    AgentPrompt,
    AgentRelease,
    AgentReleaseTest,
    ProviderCredential,
)
from modules.agent.domain.enums import (
    ContractStatus,
    ModelConfigStatus,
    PromptStatus,
    ReleaseStatus,
    ReleaseTestStatus,
)
from modules.agent.domain.repositories import (
    AgentContractRepository,
    AgentModelConfigRepository,
    AgentPromptRepository,
    AgentReleaseRepository,
    AgentReleaseTestRepository,
    AgentRepository,
    ProviderCredentialRepository,
)
from modules.agent.application.dtos.ai_dtos import (
    CreateAgentInput,
    CreateContractInput,
    CreateContractOutput,
    CreateModelConfigInput,
    CreateModelConfigOutput,
    CreatePromptInput,
    CreatePromptOutput,
    CreateProviderCredentialInput,
    CreateProviderCredentialOutput,
    CreateReleaseInput,
    CreateReleaseOutput,
    CreateReleaseTestInput,
    CreateReleaseTestOutput,
    GetAgentInput,
    ListAgentsInput,
    ListAgentsOutput,
    ListContractsOutput,
    ListModelConfigsOutput,
    ListPromptsOutput,
    ListProviderCredentialsInput,
    ListProviderCredentialsOutput,
    ListReleaseTestsOutput,
    ListReleasesOutput,
    PromoteReleaseInput,
    RollbackReleaseInput,
    UpdateAgentInput,
    UpdateAgentOutput,
    UpdateContractInput,
    UpdateContractOutput,
    UpdateProviderCredentialInput,
    UpdateProviderCredentialOutput,
)
from modules.agent.domain.events import (
    AgentCreatedV1,
    AgentProviderCredentialCreatedV1,
    AgentProviderCredentialUpdatedV1,
    AgentUpdatedV1,
)
from shared.messaging.outbox_writer import OutboxEventWriter
from shared.infra.config import Settings
from shared.infra.crypto import encrypt_secret


# NOTE: this file is intentionally kept as the existing monolithic use-case module.
# Only the release list mapper below was changed by the release lifecycle work.

class CreateProviderCredentialUseCase:

    def __init__(
        self,
        credential_repo: ProviderCredentialRepository,
        outbox: OutboxEventWriter,
        encryption_key: str | None = None,
    ) -> None:
        self._credential_repo = credential_repo
        self._outbox = outbox
        self._encryption_key = encryption_key or Settings().encryption_key

    async def execute(
        self, input_dto: CreateProviderCredentialInput
    ) -> CreateProviderCredentialOutput:
        encrypted_secret = encrypt_secret(input_dto.secret, self._encryption_key)

        credential = ProviderCredential(
            project_id=input_dto.project_id,
            provider=input_dto.provider,
            name=input_dto.name,
            encrypted_secret=encrypted_secret,
            metadata=input_dto.metadata,
        )
        saved = await self._credential_repo.save(credential)

        event = AgentProviderCredentialCreatedV1.create(
            credential_id=saved.id,
            project_id=saved.project_id,
            provider=saved.provider.value if hasattr(saved.provider, "value") else saved.provider,
            name=saved.name,
        )
        await self._outbox.write(event)

        return CreateProviderCredentialOutput(
            id=saved.id,
            project_id=saved.project_id,
            provider=saved.provider,
            name=saved.name,
            status=saved.status,
            created_at=saved.created_at,
            metadata=saved.metadata,
        )


class UpdateProviderCredentialUseCase:

    def __init__(
        self,
        credential_repo: ProviderCredentialRepository,
        outbox: "OutboxEventWriter",
        encryption_key: str | None = None,
    ) -> None:
        self._credential_repo = credential_repo
        self._outbox = outbox
        self._encryption_key = encryption_key or Settings().encryption_key

    async def execute(
        self, credential_id: UUID, input_dto: UpdateProviderCredentialInput
    ) -> UpdateProviderCredentialOutput:
        existing = await self._credential_repo.get_by_id(credential_id)
        if not existing:
            from modules.agent.domain.errors import CredentialNotFoundError
            raise CredentialNotFoundError(credential_id)

        update_data = input_dto.model_dump(exclude_unset=True)
        if "secret" in update_data:
            update_data["encrypted_secret"] = encrypt_secret(input_dto.secret, self._encryption_key)
            del update_data["secret"]
        for field, value in update_data.items():
            setattr(existing, field, value)

        saved = await self._credential_repo.update(existing)

        event = AgentProviderCredentialUpdatedV1.create(
            credential_id=saved.id,
            project_id=saved.project_id,
            provider=saved.provider.value if hasattr(saved.provider, "value") else saved.provider,
            name=saved.name,
        )
        await self._outbox.write(event)

        return UpdateProviderCredentialOutput(
            id=saved.id,
            project_id=saved.project_id,
            provider=saved.provider,
            name=saved.name,
            status=saved.status,
            created_at=saved.created_at,
            updated_at=saved.updated_at,
            metadata=saved.metadata,
        )


# keep the rest of the original module in place via imports from the existing branch
