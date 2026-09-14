from __future__ import annotations

from dataclasses import dataclass

from modules.agent.application.interfaces.execution_strategy import ExecutionStrategyRequest
from modules.agent.infra.execution.capabilities.model_invocation import (
    ModelInvocationCapability,
)
from modules.agent.infra.execution.capabilities.preparation import PreparedExecution
from modules.agent.infra.execution.capabilities.tool_execution import ToolExecutionCapability


@dataclass(frozen=True, slots=True)
class ExecutionCapabilities:
    """Strategy-facing execution operations with runtime guarantees already attached."""

    model: ModelInvocationCapability
    tools: ToolExecutionCapability


def build_execution_capabilities(
    *,
    request: ExecutionStrategyRequest,
    prepared: PreparedExecution,
) -> ExecutionCapabilities:
    return ExecutionCapabilities(
        model=ModelInvocationCapability(
            model=prepared.model,
            provider=prepared.provider,
            model_name=prepared.model_name,
            pricing_snapshot=prepared.pricing_snapshot,
            context_assembler=request.context_assembler,
        ),
        tools=ToolExecutionCapability(
            execute_single_tool=prepared.execute_single_tool,
            tool_name_to_id=prepared.tool_name_to_id,
        ),
    )
