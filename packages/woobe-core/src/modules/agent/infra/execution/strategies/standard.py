from __future__ import annotations

from modules.agent.application.interfaces.execution import InstrumentedExecution
from modules.agent.application.interfaces.execution_strategy import ExecutionStrategyRequest
from modules.agent.infra.execution.instrumented_execution_runner import (
    run_instrumented_execution,
)


class StandardExecutionStrategy:
    """Current Woobe Agent execution behavior behind the strategy boundary."""

    async def execute(self, request: ExecutionStrategyRequest) -> InstrumentedExecution:
        return await run_instrumented_execution(
            llm_factory=request.llm_factory,
            execute_single_tool=request.execute_single_tool,
            clean_json_answer=request.clean_json_answer,
            agent=request.agent,
            api_key=request.api_key,
            base_url=request.base_url,
            response_format=request.response_format,
            json_enabled=request.json_enabled,
            has_tools=request.has_tools,
            agent_tools=request.agent_tools,
            tool_name_to_id=request.tool_name_to_id,
            messages=request.messages,
            context_assembler=request.context_assembler,
        )
