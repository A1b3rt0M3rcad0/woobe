from __future__ import annotations

from typing import Any

from modules.agent.application.interfaces.execution import InstrumentedExecution
from modules.agent.application.strategy_sdk import Completed, Suspended
from modules.agent.infra.execution.capabilities.bundle import ExecutionCapabilities
from modules.agent.infra.execution.strategies.standard.definition import (
    build_standard_strategy_definition,
)
from modules.agent.infra.execution.strategy_runtime.builder import (
    build_strategy_context_from_capabilities,
)


async def run_standard_strategy_loop(
    *,
    capabilities: ExecutionCapabilities,
    messages: list,
    initial_phase: str,
    final_json_instruction: str | None,
    final_model: Any | None = None,
    final_model_factory: Any | None = None,
    initial_tool_call: dict[str, Any] | None = None,
) -> tuple[InstrumentedExecution, int]:
    """Compatibility facade delegating to the same Standard Strategy implementation."""

    definition = build_standard_strategy_definition()
    built = build_strategy_context_from_capabilities(
        definition=definition,
        capabilities=capabilities,
        messages=messages,
        initial_phase=initial_phase,
        final_model=final_model,
        final_model_factory=final_model_factory,
        final_json_instruction=final_json_instruction,
        bootstrap={"initial_tool_call": initial_tool_call},
    )
    outcome = await definition.strategy_factory().execute(built.context)
    if isinstance(outcome, Suspended):
        raise RuntimeError("Legacy Standard loop does not support suspended outcomes")
    if not isinstance(outcome, Completed):
        raise RuntimeError("Standard Strategy returned an unsupported outcome")
    return outcome.execution, built.runtime_state.call_index
