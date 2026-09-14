from __future__ import annotations

from typing import Any, Callable, Coroutine

from modules.agent.application.interfaces.context_assembler import ContextAssembler
from modules.agent.application.interfaces.execution import InstrumentedExecution
from modules.agent.application.interfaces.execution_strategy import ExecutionStrategyRequest
from modules.agent.domain.entities import Agent
from modules.agent.infra.execution.capabilities.preparation import (
    configure_skill_runtime,
    prepare_execution,
)
from modules.agent.infra.execution.capabilities.result_finalization import (
    finalize_execution_result,
)
from modules.agent.infra.execution.tool_execution_loop import run_tool_loop


async def run_instrumented_execution(
    *,
    llm_factory: Any,
    execute_single_tool: Callable[[dict, str], Coroutine[Any, Any, dict]],
    clean_json_answer,
    agent: Agent,
    api_key: str,
    base_url: str | None,
    response_format: dict,
    json_enabled: bool,
    has_tools: bool,
    agent_tools: list[dict],
    tool_name_to_id: dict[str, str],
    messages: list,
    context_assembler: ContextAssembler | None = None,
) -> InstrumentedExecution:
    """Compatibility entrypoint for the pre-Strategy execution API.

    New execution strategies should compose the reusable execution capabilities directly
    instead of depending on this runner as their algorithm boundary.
    """
    request = ExecutionStrategyRequest(
        llm_factory=llm_factory,
        execute_single_tool=execute_single_tool,
        clean_json_answer=clean_json_answer,
        agent=agent,
        api_key=api_key,
        base_url=base_url,
        response_format=response_format,
        json_enabled=json_enabled,
        has_tools=has_tools,
        agent_tools=agent_tools,
        tool_name_to_id=tool_name_to_id,
        messages=messages,
        context_assembler=context_assembler,
    )
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


__all__ = ["configure_skill_runtime", "run_instrumented_execution"]
