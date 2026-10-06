from modules.agent.application.dtos.ai_dtos import CreateReleaseInput, UpdateAgentInput
from modules.agent.application.execution_snapshot import build_agent_execution_snapshot
from modules.agent.application.interfaces.repositories import AgentRepository
from modules.agent.application.use_cases.ai_agent_cases import UpdateAgentUseCase
from modules.agent.application.use_cases.session_mode_compatible_release import (
    SessionModeCompatibleCreateReleaseUseCase,
)
from modules.agent.domain.enums import AgentStatus
from modules.agent.domain.errors import AgentNotFoundError
from shared.contracts.errors import ConflictError


class FinalizeImportedAgentUseCase:
    """Publish the complete Draft and make its preparatory Agent available atomically."""

    def __init__(
        self,
        draft: SessionModeCompatibleCreateReleaseUseCase,
        update: UpdateAgentUseCase,
        agents: AgentRepository,
    ):
        self._draft, self._update, self._agents = draft, update, agents

    async def execute(self, input_dto: CreateReleaseInput, change_kind="change"):
        agent = await self._agents.get_by_id(input_dto.agent_id)
        if agent is None or agent.project_id != input_dto.project_id:
            raise AgentNotFoundError(input_dto.agent_id)
        if agent.status != AgentStatus.inactive:
            raise ConflictError(
                "Import finalization requires its inactive preparatory Agent"
            )
        complete = input_dto.model_copy(update={"agent_status": "active"})
        draft = await self._draft.execute(complete, change_kind=change_kind)
        await self._update.execute(
            agent.id, UpdateAgentInput(status=AgentStatus.active)
        )
        # The native update path may canonicalize Models, Skills and Behavior.
        # Reject a disagreement within the owner transaction instead of exposing
        # an active Agent with a different executable definition from its Draft.
        projected = await self._agents.get_by_id(agent.id)
        if build_agent_execution_snapshot(projected) != build_agent_execution_snapshot(
            draft
        ):
            raise ConflictError(
                "Imported Agent projection differs from its saved Draft"
            )
        return draft
