from uuid import UUID

from modules.agent.application.dtos.ai_dtos import (
    CreatePromptInput,
    CreatePromptOutput,
    ListPromptsOutput,
)
from modules.agent.domain.entities import AgentPrompt
from modules.agent.domain.enums import PromptStatus
from modules.agent.application.interfaces.repositories import AgentPromptRepository


class CreatePromptUseCase:
    def __init__(self, prompt_repo: AgentPromptRepository) -> None:
        self._prompt_repo = prompt_repo

    async def execute(self, input_dto: CreatePromptInput) -> CreatePromptOutput:
        item = AgentPrompt(
            project_id=input_dto.project_id,
            agent_id=input_dto.agent_id,
            version=input_dto.version,
            name=input_dto.name,
            content=input_dto.content,
            content_hash=input_dto.content_hash,
            status=PromptStatus.draft,
            created_by=input_dto.created_by,
        )
        saved = await self._prompt_repo.save(item)
        return CreatePromptOutput(
            id=saved.id,
            project_id=saved.project_id,
            agent_id=saved.agent_id,
            version=saved.version,
            name=saved.name,
            content=saved.content,
            content_hash=saved.content_hash,
            status=saved.status,
            created_by=saved.created_by,
            created_at=saved.created_at,
            updated_at=saved.updated_at,
        )


class ListPromptsUseCase:
    def __init__(self, prompt_repo: AgentPromptRepository) -> None:
        self._prompt_repo = prompt_repo

    async def execute(self, agent_id: UUID) -> list[ListPromptsOutput]:
        items = await self._prompt_repo.list_by_agent(agent_id)
        return [
            ListPromptsOutput(
                id=item.id,
                version=item.version,
                name=item.name,
                content=item.content,
                status=item.status,
                content_hash=item.content_hash,
                created_by=item.created_by,
                created_at=item.created_at,
            )
            for item in items
        ]


class GetPromptUseCase:
    def __init__(self, prompt_repo: AgentPromptRepository) -> None:
        self._prompt_repo = prompt_repo

    async def execute(self, prompt_id: UUID) -> AgentPrompt:
        item = await self._prompt_repo.get_by_id(prompt_id)
        if item is None:
            from modules.agent.domain.errors import PromptNotFoundError

            raise PromptNotFoundError
        return item
