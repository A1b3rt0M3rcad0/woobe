import os

from cryptography.fernet import Fernet

from modules.ai.domain.entities import Agent, ProviderCredential
from modules.ai.domain.repositories import (
    AgentRepository,
    ProviderCredentialRepository,
)
from modules.ai.service.dtos import (
    CreateAgentInput,
    CreateAgentOutput,
    CreateProviderCredentialInput,
    CreateProviderCredentialOutput,
)
from shared.domain.events import OutboxEventWriter


def _generate_encryption_key() -> bytes:
    return Fernet.generate_key()


class CreateProviderCredentialUseCase:

    def __init__(
        self,
        credential_repo: ProviderCredentialRepository,
        outbox: OutboxEventWriter,
    ) -> None:
        self._credential_repo = credential_repo
        self._outbox = outbox

    async def execute(
        self, input_dto: CreateProviderCredentialInput
    ) -> CreateProviderCredentialOutput:
        encryption_key = _generate_encryption_key()
        fernet = Fernet(encryption_key)
        encrypted_secret = fernet.encrypt(input_dto.secret.encode()).decode()

        credential = ProviderCredential(
            project_id=input_dto.project_id,
            provider=input_dto.provider,
            name=input_dto.name,
            encrypted_secret=encrypted_secret,
        )
        saved = await self._credential_repo.save(credential)

        await self._outbox.write(
            aggregate_type="provider_credential",
            aggregate_id=saved.id,
            event_type="provider_credential.created",
            payload={
                "project_id": str(saved.project_id),
                "provider": saved.provider.value,
                "name": saved.name,
            },
        )

        return CreateProviderCredentialOutput(
            id=saved.id,
            project_id=saved.project_id,
            provider=saved.provider,
            name=saved.name,
            status=saved.status,
            created_at=saved.created_at,
        )


class CreateAgentUseCase:

    def __init__(
        self,
        agent_repo: AgentRepository,
        credential_repo: ProviderCredentialRepository,
        outbox: OutboxEventWriter,
    ) -> None:
        self._agent_repo = agent_repo
        self._credential_repo = credential_repo
        self._outbox = outbox

    async def execute(self, input_dto: CreateAgentInput) -> CreateAgentOutput:
        if input_dto.provider_credential_id:
            cred = await self._credential_repo.get_by_id(
                input_dto.provider_credential_id
            )
            if not cred:
                from modules.ai.domain.errors import CredentialNotFoundError
                raise CredentialNotFoundError(input_dto.provider_credential_id)

        agent = Agent(
            project_id=input_dto.project_id,
            provider_credential_id=input_dto.provider_credential_id,
            fallback_credential_id=input_dto.fallback_credential_id,
            name=input_dto.name,
            description=input_dto.description,
            type=input_dto.type,
            system_prompt=input_dto.system_prompt,
            provider=input_dto.provider,
            model=input_dto.model,
            fallback_provider=input_dto.fallback_provider,
            fallback_model=input_dto.fallback_model,
            temperature=input_dto.temperature,
            max_output_tokens=input_dto.max_output_tokens,
            session_mode=input_dto.session_mode,
            settings=input_dto.settings,
        )
        saved = await self._agent_repo.save(agent)

        await self._outbox.write(
            aggregate_type="agent",
            aggregate_id=saved.id,
            event_type="agent.created",
            payload={
                "project_id": str(saved.project_id),
                "name": saved.name,
                "provider": saved.provider.value,
                "model": saved.model,
            },
        )

        return CreateAgentOutput(
            id=saved.id,
            project_id=saved.project_id,
            name=saved.name,
            type=saved.type,
            provider=saved.provider,
            model=saved.model,
            status=saved.status,
            created_at=saved.created_at,
        )
