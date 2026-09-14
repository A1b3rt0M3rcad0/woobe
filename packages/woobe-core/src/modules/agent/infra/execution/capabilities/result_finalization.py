from __future__ import annotations

from modules.agent.application.interfaces.execution import InstrumentedExecution
from modules.agent.application.interfaces.execution_strategy import ExecutionStrategyRequest
from modules.agent.infra.execution.capabilities.preparation import PreparedExecution
from modules.agent.infra.execution.structured_json_repair import repair_json_if_needed


async def finalize_execution_result(
    *,
    request: ExecutionStrategyRequest,
    prepared: PreparedExecution,
    execution: InstrumentedExecution,
    call_index: int,
) -> InstrumentedExecution:
    """Finalize the strategy result without owning Agent Run lifecycle finalization."""
    if not request.json_enabled:
        return execution

    return await repair_json_if_needed(
        execution=execution,
        call_index=call_index,
        llm_factory=request.llm_factory,
        provider=prepared.provider,
        model_name=prepared.model_name,
        api_key=request.api_key,
        base_url=request.base_url,
        max_tokens=prepared.effective_output_tokens,
        schema=request.response_format.get("schema", {}),
        clean_json_answer=request.clean_json_answer,
        pricing_snapshot=prepared.pricing_snapshot,
        context_assembler=request.context_assembler,
    )
