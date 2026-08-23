from __future__ import annotations

from modules.agent.application.dtos.runtime_dtos import AskInput, AskOutput
from modules.agent.application.interfaces.agent_execution import AgentExecutionPort


class ExecuteAgentUseCase:
    """Application use case that owns the Agent execution boundary.

    Concrete LLM, Tool, persistence and streaming implementations stay outside
    the Application layer and are injected through ``AgentExecutionPort``.
    """

    def __init__(self, execution: AgentExecutionPort) -> None:
        self._execution = execution

    async def execute(self, input_dto: AskInput) -> AskOutput:
        return await self._execution.execute(input_dto)
