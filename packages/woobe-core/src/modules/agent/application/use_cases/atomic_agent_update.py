"""Keep direct authoring updates and the latest complete Draft consistent."""

from modules.agent.application.dtos.ai_dtos import CreateReleaseInput


class AtomicAgentUpdateUseCase:
    def __init__(self, update, draft, agents):
        self._update, self._draft, self._agents = update, draft, agents

    async def execute(self, agent_id, input_dto):
        result = await self._update.execute(agent_id, input_dto)
        author_fields = set(input_dto.model_fields_set) - {"status"}
        if author_fields:
            await self._draft.execute(
                CreateReleaseInput(
                    project_id=result.project_id, agent_id=result.id, version="draft"
                )
            )
            saved = await self._agents.get_by_id(agent_id)
            result = result.model_copy(update={"revision": saved.revision})
        return result
