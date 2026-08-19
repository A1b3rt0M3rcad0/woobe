from uuid import UUID

from modules.agent.application.dtos.ai_dtos import CreateModelConfigInput, CreateModelConfigOutput, ListModelConfigsOutput
from modules.agent.domain.entities import AgentModelConfig
from modules.agent.domain.enums import ModelConfigStatus
from modules.agent.application.interfaces.repositories import AgentModelConfigRepository


def _to_output(saved: AgentModelConfig):
    return CreateModelConfigOutput(
        id=saved.id,
        project_id=saved.project_id,
        agent_id=saved.agent_id,
        version=saved.version,
        provider=saved.provider,
        provider_credential_id=saved.provider_credential_id,
        model=saved.model,
        base_url=saved.base_url,
        temperature=saved.temperature,
        max_output_tokens=saved.max_output_tokens,
        session_mode=saved.session_mode,
        settings=saved.settings,
        status=saved.status,
        created_at=saved.created_at,
        updated_at=saved.updated_at,
    )


class CreateModelConfigUseCase:
    def __init__(self, config_repo: AgentModelConfigRepository) -> None:
        self._config_repo = config_repo

    async def execute(self, input_dto: CreateModelConfigInput) -> CreateModelConfigOutput:
        saved = await self._config_repo.save(AgentModelConfig(
            project_id=input_dto.project_id,
            agent_id=input_dto.agent_id,
            version=input_dto.version,
            provider=input_dto.provider,
            provider_credential_id=input_dto.provider_credential_id,
            model=input_dto.model,
            base_url=input_dto.base_url,
            temperature=input_dto.temperature,
            max_output_tokens=input_dto.max_output_tokens,
            session_mode=input_dto.session_mode,
            settings=input_dto.settings,
            status=ModelConfigStatus.draft,
        ))
        return _to_output(saved)


class ListModelConfigsUseCase:
    def __init__(self, config_repo: AgentModelConfigRepository) -> None:
        self._config_repo = config_repo

    async def execute(self, agent_id: UUID) -> list[ListModelConfigsOutput]:
        return [ListModelConfigsOutput(id=item.id, version=item.version, provider=item.provider, model=item.model, status=item.status, created_at=item.created_at) for item in await self._config_repo.list_by_agent(agent_id)]


class GetModelConfigUseCase:
    def __init__(self, config_repo: AgentModelConfigRepository) -> None:
        self._config_repo = config_repo

    async def execute(self, config_id: UUID) -> AgentModelConfig:
        item = await self._config_repo.get_by_id(config_id)
        if item is None:
            from modules.agent.domain.errors import ModelConfigNotFoundError
            raise ModelConfigNotFoundError
        return item
