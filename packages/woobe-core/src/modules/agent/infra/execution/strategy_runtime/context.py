from __future__ import annotations

from typing import Generic, TypeVar

from modules.agent.application.strategy_sdk import (
    ExecutionCheckpointBoundary,
    ExecutionState,
    StrategyBootstrap,
)
from modules.agent.infra.execution.strategy_runtime.checkpoint import RuntimeStrategyCheckpoint
from modules.agent.infra.execution.strategy_runtime.context_manager import (
    RuntimeStrategyContextManager,
)
from modules.agent.infra.execution.strategy_runtime.knowledge import RuntimeStrategyKnowledge
from modules.agent.infra.execution.strategy_runtime.model import RuntimeStrategyModel
from modules.agent.infra.execution.strategy_runtime.output import RuntimeStrategyOutput
from modules.agent.infra.execution.strategy_runtime.tools import RuntimeStrategyTools


StateT = TypeVar("StateT", bound=ExecutionState)


class RuntimeStrategyContext(Generic[StateT]):
    """Concrete implementation of the stable StrategyContext API."""

    __slots__ = (
        "state",
        "bootstrap",
        "model",
        "tools",
        "knowledge",
        "context",
        "output",
        "_checkpoint",
    )

    def __init__(
        self,
        *,
        state: StateT,
        bootstrap: StrategyBootstrap,
        model: RuntimeStrategyModel,
        tools: RuntimeStrategyTools,
        knowledge: RuntimeStrategyKnowledge,
        context: RuntimeStrategyContextManager,
        output: RuntimeStrategyOutput,
        checkpoint: RuntimeStrategyCheckpoint,
    ) -> None:
        self.state = state
        self.bootstrap = bootstrap
        self.model = model
        self.tools = tools
        self.knowledge = knowledge
        self.context = context
        self.output = output
        self._checkpoint = checkpoint

    async def checkpoint(
        self,
        boundary: ExecutionCheckpointBoundary = ExecutionCheckpointBoundary.TOOL,
    ) -> None:
        await self._checkpoint.save(self.state, boundary)
