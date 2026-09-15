from __future__ import annotations

from typing import Any, Callable, Coroutine

from modules.agent.application.interfaces.context_assembler import ContextAssembler
from modules.agent.application.interfaces.execution import InstrumentedExecution
from modules.agent.application.interfaces.execution_strategy import ExecutionStrategyRequest
from modules.agent.domain.entities import Agent
from modules.agent.infra.execution.capabilities.preparation import (
    _messages_with_bound_capability_authority,
    configure_skill_runtime,
)
from modules.agent.infra.execution.strategies.standard import StandardExecutionStrategy


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

    New runtime code resolves Strategies through `ExecutionStrategyResolver`. This function
    remains only for focused legacy callers/tests and delegates to the same Standard Strategy
    used by production instead of maintaining a second execution algorithm.
    """
    return await StandardExecutionStrategy().execute(
        ExecutionStrategyRequest(
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
    )


__all__ = [
    "_messages_with_bound_capability_authority",
    "configure_skill_runtime",
    "run_instrumented_execution",
]
