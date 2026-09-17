from __future__ import annotations

from typing import Any, Callable, Coroutine

from modules.agent.application.interfaces.context_assembler import ContextAssembler
from modules.agent.application.interfaces.execution import InstrumentedExecution
from modules.agent.infra.execution.capabilities.bundle import ExecutionCapabilities
from modules.agent.infra.execution.capabilities.model_invocation import ModelInvocationCapability
from modules.agent.infra.execution.capabilities.recovery import StrategyRecoveryCapability
from modules.agent.infra.execution.capabilities.tool_execution import ToolExecutionCapability
from modules.agent.infra.execution.durable_execution_instrumentation import (
    execute_tool_call,
    invoke_llm,
)
from modules.agent.infra.execution.strategies.standard import (
    MAX_CONSECUTIVE_SEMANTIC_FAILURE_ROUNDS,
    MAX_TOOL_ROUNDS,
    StandardExecutionStrategy,
)
from modules.agent.infra.execution.strategy_runtime.runner import (
    execute_strategy_with_capabilities,
)


async def run_tool_loop(
    *,
    model: Any,
    execute_single_tool: Callable[[dict, str], Coroutine[Any, Any, dict]],
    messages: list,
    tool_name_to_id: dict[str, str],
    provider: str,
    model_name: str,
    initial_phase: str,
    final_json_instruction: str | None,
    initial_tool_call: dict[str, Any] | None = None,
    final_model: Any | None = None,
    final_model_factory: Callable[[], Any] | None = None,
    pricing_snapshot: dict[str, Any] | None = None,
    context_assembler: ContextAssembler | None = None,
) -> tuple[InstrumentedExecution, int]:
    """Compatibility facade for callers of the pre-Strategy Standard loop API."""

    capabilities = ExecutionCapabilities(
        model=ModelInvocationCapability(
            model=model,
            provider=provider,
            model_name=model_name,
            pricing_snapshot=pricing_snapshot,
            context_assembler=context_assembler,
            invoke_fn=invoke_llm,
        ),
        tools=ToolExecutionCapability(
            execute_single_tool=execute_single_tool,
            tool_name_to_id=tool_name_to_id,
            execute_fn=execute_tool_call,
        ),
        recovery=StrategyRecoveryCapability(strategy_name="standard"),
    )
    return await execute_strategy_with_capabilities(
        strategy=StandardExecutionStrategy(),
        capabilities=capabilities,
        messages=messages,
        final_model=final_model,
        final_model_factory=final_model_factory,
        initial_phase=initial_phase,
        final_json_instruction=final_json_instruction,
        bootstrap={"initial_tool_call": initial_tool_call},
    )


__all__ = [
    "MAX_CONSECUTIVE_SEMANTIC_FAILURE_ROUNDS",
    "MAX_TOOL_ROUNDS",
    "run_tool_loop",
]
