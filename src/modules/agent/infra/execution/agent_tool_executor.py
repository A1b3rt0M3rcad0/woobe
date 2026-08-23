from uuid import UUID

from modules.agent.application.interfaces.ports import (
    ToolExecutionPort,
    ToolSecretResolverPort,
)
from modules.agent.application.interfaces.repositories import ToolRepository
from modules.agent.application.interfaces.tool_executor import ToolExecutor
from modules.agent.application.tool_converter import agent_tool_to_openai_definition
from modules.agent.infra.adapters.tool_executor import HttpToolExecutor
from modules.agent.infra.adapters.tool_runtime import build_default_tool_runtime_registry


class AgentToolExecutor(ToolExecutor):
    def __init__(
        self,
        tool_repo: ToolRepository,
        tool_executor: ToolExecutionPort | None = None,
        secret_resolver: ToolSecretResolverPort | None = None,
    ) -> None:
        self._tool_repo = tool_repo
        self._tool_executor = tool_executor or HttpToolExecutor()
        self._secret_resolver = secret_resolver

    async def execute_tool(self, tool_id: UUID, input_data: dict) -> dict:
        from modules.agent.application.dtos.tools_dtos import ExecuteToolInput
        from modules.agent.application.runtime_tool_use_cases import RuntimeExecuteToolUseCase

        registry = build_default_tool_runtime_registry(
            self._tool_executor,
            self._secret_resolver,
        )
        use_case = RuntimeExecuteToolUseCase(
            tool_repo=self._tool_repo,
            runtime_registry=registry,
        )
        result = await use_case.execute(
            ExecuteToolInput(tool_id=tool_id, input_data=input_data)
        )
        return result.model_dump()

    async def tool_to_openai_definition(
        self,
        tool_id: UUID,
    ) -> dict | None:
        tool = await self._tool_repo.get_by_id(tool_id)
        if tool:
            return agent_tool_to_openai_definition(tool)
        return None
