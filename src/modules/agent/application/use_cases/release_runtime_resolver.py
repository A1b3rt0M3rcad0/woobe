from __future__ import annotations

from modules.agent.application.dtos.runtime_dtos import AskInput
from modules.agent.application.use_cases.ask_use_case import AskAgentUseCase
from modules.agent.domain.entities import Agent
from modules.agent.domain.enums import ReleaseStatus
from modules.agent.infra.database.repositories import SQLAlchemyAgentReleaseRepository
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork


class ReleaseRuntimeResolver(AskAgentUseCase):
    async def _load_agent(self, uow: AgentUnitOfWork, input_dto: AskInput) -> Agent:
        agent = await self._load_base_agent(uow, input_dto)
        release_repo = SQLAlchemyAgentReleaseRepository(uow)
        context = (input_dto.execution_context or "playground").lower()

        if context == "production":
            release = await release_repo.get_active_production(agent.id)
            if release is None:
                raise ValueError("No production release deployed")
            return self._apply_release_to_agent(agent, release)

        if context == "staging":
            releases = await release_repo.list_by_status(agent.id, ReleaseStatus.staging)
            if not releases:
                raise ValueError("No staging release configured")
            return self._apply_release_to_agent(agent, releases[0])

        if context != "playground":
            raise ValueError("Unsupported execution context")

        if input_dto.snapshot_override:
            return self._apply_snapshot_override(agent, input_dto.snapshot_override)

        if input_dto.loaded_release_id:
            release = await release_repo.get_by_id(input_dto.loaded_release_id)
            if release is not None:
                return self._apply_release_to_agent(agent, release)

        drafts = await release_repo.list_by_status(agent.id, ReleaseStatus.draft)
        if drafts:
            return self._apply_release_to_agent(agent, drafts[0])

        return agent

    async def _load_base_agent(self, uow: AgentUnitOfWork, input_dto: AskInput) -> Agent:
        from modules.agent.domain.errors import AgentNotFoundError
        from shared.infra.errors import ValidationError

        agent = await uow.agents.get_by_id(input_dto.agent_id)
        if agent is None:
            raise AgentNotFoundError(input_dto.agent_id)
        if agent.project_id != input_dto.project_id:
            raise AgentNotFoundError(input_dto.agent_id)
        status = getattr(agent, "status", None)
        status_value = getattr(status, "value", status)
        if status_value not in (None, "active"):
            raise ValidationError("Agent is not active")
        return agent
