from __future__ import annotations

from dataclasses import dataclass

from modules.agent.infra.execution.capabilities.context_assembly import (
    ContextAssemblyCapability,
)
from modules.agent.infra.execution.capabilities.knowledge_retrieval import (
    KnowledgeRetrievalCapability,
)
from modules.agent.infra.execution.capabilities.model_invocation import (
    ModelInvocationCapability,
)
from modules.agent.infra.execution.capabilities.preparation import PreparedExecution
from modules.agent.infra.execution.capabilities.recovery import StrategyRecoveryCapability
from modules.agent.infra.execution.capabilities.tool_execution import ToolExecutionCapability


@dataclass(frozen=True, slots=True)
class ExecutionCapabilities:
    """Strategy-facing execution operations with runtime guarantees already attached."""

    model: ModelInvocationCapability
    tools: ToolExecutionCapability
    knowledge: KnowledgeRetrievalCapability
    context: ContextAssemblyCapability
    recovery: StrategyRecoveryCapability


def build_execution_capabilities(
    *,
    prepared: PreparedExecution,
    strategy_name: str,
) -> ExecutionCapabilities:
    return ExecutionCapabilities(
        model=ModelInvocationCapability(
            model=prepared.model,
            provider=prepared.provider,
            model_name=prepared.model_name,
            pricing_snapshot=prepared.pricing_snapshot,
        ),
        tools=ToolExecutionCapability(
            execute_single_tool=prepared.execute_single_tool,
            tool_name_to_id=prepared.tool_name_to_id,
        ),
        knowledge=KnowledgeRetrievalCapability(
            retrieve_fn=prepared.knowledge_retrieve,
        ),
        context=ContextAssemblyCapability(
            manager=prepared.context_manager,
            provider=prepared.provider,
            model_name=prepared.model_name,
            pricing_snapshot=prepared.pricing_snapshot,
            tool_definitions=tuple(prepared.tool_definitions),
        ),
        recovery=StrategyRecoveryCapability(strategy_name=strategy_name),
    )
