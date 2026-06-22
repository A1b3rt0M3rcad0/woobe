from uuid import UUID

from modules.agent.application.dtos.ai_dtos import (
    CreateAgentInput,
    GetAgentInput,
    ListAgentsInput,
    ListAgentsOutput,
    UpdateAgentInput,
    UpdateAgentOutput,
)
from modules.agent.domain.entities import Agent
from modules.agent.domain.events import AgentCreatedV1, AgentUpdatedV1
from modules.agent.domain.repositories import AgentRepository, ProviderCredentialRepository
from shared.messaging.outbox_writer import OutboxEventWriter


class CreateAgentUseCase:
    def __init__(self, agent_repo: AgentRepository, credential_repo: ProviderCredentialRepository, outbox: OutboxEventWriter) -> None:
        self._agent_repo = agent_repo
        self._credential_repo = credential_repo
        self._outbox = outbox

    async def execute(self, input_dto: CreateAgentInput) -> Agent:
        if input_dto.provider_credential_id and not await self._credential_repo.get_by_id(input_dto.provider_credential_id):
            from modules.agent.domain.errors import CredentialNotFoundError
            raise CredentialNotFoundError(input_dto.provider_credential_id)
        saved = await self._agent_repo.save(Agent(**input_dto.model_dump()))
        await self._outbox.write(AgentCreatedV1.create(
            agent_id=saved.id,
            project_id=saved.project_id,
            name=saved.name,
            provider=saved.provider.value if hasattr(saved.provider, "value") else str(saved.provider),
            model=saved.model,
        ))
        return saved


class UpdateAgentUseCase:
    def __init__(self, agent_repo: AgentRepository, credential_repo: ProviderCredentialRepository, outbox: OutboxEventWriter) -> None:
        self._agent_repo = agent_repo
        self._credential_repo = credential_repo
        self._outbox = outbox

    async def execute(self, agent_id: UUID, input_dto: UpdateAgentInput) -> UpdateAgentOutput:
        existing = await self._agent_repo.get_by_id(agent_id)
        if not existing:
            from modules.agent.domain.errors import AgentNotFoundError
            raise AgentNotFoundError(agent_id)
        for field, value in input_dto.model_dump(exclude_unset=True).items():
            setattr(existing, field, value)
        saved = await self._agent_repo.update(existing)
        await self._outbox.write(AgentUpdatedV1.create(
            agent_id=saved.id,
            project_id=saved.project_id,
            name=saved.name,
            provider=saved.provider.value if hasattr(saved.provider, "value") else str(saved.provider),
            model=saved.model,
        ))
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


class ListAgentsUseCase:
    def __init__(self, agent_repo: AgentRepository) -> None:
        self._agent_repo = agent_repo

    async def execute(self, input_dto: ListAgentsInput) -> list[ListAgentsOutput]:
        if not input_dto.project_id:
            return []
        return [
            ListAgentsOutput(id=item.id, project_id=item.project_id, name=item.name, provider=item.provider, model=item.model, status=item.status, created_at=item.created_at)
            for item in await self._agent_repo.list_by_project(input_dto.project_id)
        ]


class GetAgentByIdUseCase:
    def __init__(self, agent_repo: AgentRepository) -> None:
        self._agent_repo = agent_repo

    async def execute(self, input_dto: GetAgentInput) -> Agent:
        from modules.agent.domain.errors import AgentNotFoundError
        item = await self._agent_repo.get_by_id(input_dto.agent_id)
        if not item:
            raise AgentNotFoundError(input_dto.agent_id)
        return item
