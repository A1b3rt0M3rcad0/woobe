from __future__ import annotations

from modules.agent.application.interfaces.execution import InstrumentedExecution
from modules.agent.application.interfaces.execution_strategy import ExecutionStrategyRequest
from modules.agent.infra.execution.capabilities.preparation import prepare_execution
from modules.agent.infra.execution.capabilities.result_finalization import (
    finalize_execution_result,
)
from modules.agent.infra.execution.tool_execution_loop import run_tool_loop


class StandardExecutionStrategy:
    """Current Woobe Agent algorithm composed from reusable execution capabilities."""

    async def execute(self, request: ExecutionStrategyRequest) -> InstrumentedExecution:
        prepared = prepare_execution(request)
        execution, call_index = await run_tool_loop(
            model=prepared.model,
            final_model=prepared.final_model,
            final_model_factory=prepared.final_model_factory,
            execute_single_tool=prepared.execute_single_tool,
            messages=prepared.messages,
            tool_name_to_id=prepared.tool_name_to_id,
            provider=prepared.provider,
            model_name=prepared.model_name,
            initial_phase=prepared.initial_phase,
            final_json_instruction=prepared.final_json_instruction,
            pricing_snapshot=prepared.pricing_snapshot,
            context_assembler=request.context_assembler,
        )
        return await finalize_execution_result(
            request=request,
            prepared=prepared,
            execution=execution,
            call_index=call_index,
        )
