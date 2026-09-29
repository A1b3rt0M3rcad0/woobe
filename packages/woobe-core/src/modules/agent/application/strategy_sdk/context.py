from __future__ import annotations

from typing import Generic, Protocol, TypeVar

from modules.agent.application.strategy_sdk.bootstrap import StrategyBootstrap
from modules.agent.application.strategy_sdk.conversation import StrategyConversation
from modules.agent.application.strategy_sdk.context_manager import StrategyContextManager
from modules.agent.application.strategy_sdk.contracts import (
    ExecutionCheckpointBoundary,
    ExecutionState,
)
from modules.agent.application.strategy_sdk.knowledge import StrategyKnowledge
from modules.agent.application.strategy_sdk.model import StrategyModel
from modules.agent.application.strategy_sdk.output import StrategyOutput
from modules.agent.application.strategy_sdk.tools import StrategyTools


StateT = TypeVar("StateT", bound=ExecutionState)


class StrategyContext(Protocol, Generic[StateT]):
    """Stable internal API exposed to concrete Execution Strategies."""

    state: StateT
    bootstrap: StrategyBootstrap
    conversation: StrategyConversation
    model: StrategyModel
    tools: StrategyTools
    knowledge: StrategyKnowledge
    context: StrategyContextManager
    output: StrategyOutput

    async def checkpoint(
        self,
        boundary: ExecutionCheckpointBoundary = ExecutionCheckpointBoundary.TOOL,
    ) -> None: ...
