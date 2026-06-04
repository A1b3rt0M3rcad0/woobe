from uuid import UUID

from cryptography.fernet import Fernet

from modules.ai.domain.entities import Agent, ProviderCredential
from modules.ai.domain.repositories import (
    AgentRepository,
    ProviderCredentialRepository,
)
from modules.ai.service.dtos import (
    CreateAgentInput,
    CreateProviderCredentialInput,
    CreateProviderCredentialOutput,
    GetAgentInput,
    ListAgentsInput,
    ListAgentsOutput,
    ListProviderCredentialsInput,
    ListProviderCredentialsOutput,
    UpdateAgentInput,
    UpdateAgentOutput,
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
            metadata=input_dto.metadata,
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
            metadata=saved.metadata,
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

    async def execute(self, input_dto: CreateAgentInput) -> Agent:
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

        return saved


class UpdateAgentUseCase:

    def __init__(
        self,
        agent_repo: AgentRepository,
        credential_repo: ProviderCredentialRepository,
        outbox: OutboxEventWriter,
    ) -> None:
        self._agent_repo = agent_repo
        self._credential_repo = credential_repo
        self._outbox = outbox

    async def execute(self, agent_id: UUID, input_dto: UpdateAgentInput) -> UpdateAgentOutput:
        existing = await self._agent_repo.get_by_id(agent_id)
        if not existing:
            from modules.ai.domain.errors import AgentNotFoundError
            raise AgentNotFoundError(agent_id)

        if input_dto.provider_credential_id is not None:
            cred = await self._credential_repo.get_by_id(input_dto.provider_credential_id)
            if not cred:
                from modules.ai.domain.errors import CredentialNotFoundError
                raise CredentialNotFoundError(input_dto.provider_credential_id)

        update_data = input_dto.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(existing, field, value)

        saved = await self._agent_repo.update(existing)

        await self._outbox.write(
            aggregate_type="agent",
            aggregate_id=saved.id,
            event_type="agent.updated",
            payload={
                "project_id": str(saved.project_id),
                "name": saved.name,
                "provider": saved.provider.value if hasattr(saved.provider, 'value') else saved.provider,
                "model": saved.model,
            },
        )

        return UpdateAgentOutput(
            id=saved.id,
            project_id=saved.project_id,
            name=saved.name,
            type=saved.type,
            provider=saved.provider,
            model=saved.model,
            provider_credential_id=saved.provider_credential_id,
            fallback_credential_id=saved.fallback_credential_id,
            fallback_provider=saved.fallback_provider,
            fallback_model=saved.fallback_model,
            temperature=saved.temperature,
            max_output_tokens=saved.max_output_tokens,
            session_mode=saved.session_mode,
            system_prompt=saved.system_prompt,
            description=saved.description,
            status=saved.status,
            settings=saved.settings,
            created_at=saved.created_at,
            updated_at=saved.updated_at,
        )


class ListProviderCredentialsUseCase:

    def __init__(self, credential_repo: ProviderCredentialRepository) -> None:
        self._credential_repo = credential_repo

    async def execute(self, input_dto: ListProviderCredentialsInput) -> list[ListProviderCredentialsOutput]:
        if not input_dto.project_id:
            return []
        credentials = await self._credential_repo.list_by_project(input_dto.project_id)
        return [ListProviderCredentialsOutput(
            id=c.id,
            project_id=c.project_id,
            provider=c.provider,
            name=c.name,
            status=c.status,
            created_at=c.created_at,
            metadata=c.metadata,
        ) for c in credentials]


class ListAgentsUseCase:

    def __init__(self, agent_repo: AgentRepository) -> None:
        self._agent_repo = agent_repo

    async def execute(self, input_dto: ListAgentsInput) -> list[ListAgentsOutput]:
        if not input_dto.project_id:
            return []
        agents = await self._agent_repo.list_by_project(input_dto.project_id)
        return [ListAgentsOutput(
            id=a.id,
            project_id=a.project_id,
            name=a.name,
            provider=a.provider,
            model=a.model,
            status=a.status,
            created_at=a.created_at,
        ) for a in agents]


class GetAgentByIdUseCase:

    def __init__(self, agent_repo: AgentRepository) -> None:
        self._agent_repo = agent_repo

    async def execute(self, input_dto: GetAgentInput) -> Agent:
        from modules.ai.domain.errors import AgentNotFoundError
        agent = await self._agent_repo.get_by_id(input_dto.agent_id)
        if not agent:
            raise AgentNotFoundError(input_dto.agent_id)
        return agent

