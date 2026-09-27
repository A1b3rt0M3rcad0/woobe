from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Coroutine, Generic, Protocol, TypeVar, runtime_checkable

from modules.agent.application.interfaces.context_manager import ContextManager
from modules.agent.application.interfaces.execution import InstrumentedExecution
from modules.agent.application.strategy_sdk import ExecutionState, StrategyContext, StrategyOutcome
from modules.agent.domain.entities import Agent


StateT = TypeVar("StateT", bound=ExecutionState)


@dataclass(frozen=True, slots=True)
class ExecutionStrategyRequest:
    """Outer runtime input used to prepare one Agent execution.

    Concrete Strategies never consume this request directly. The Strategy Runtime resolves
    it into ``StrategyContext`` so algorithms stay independent from provider factories,
    persistence, transport and lifecycle plumbing.
    """

    llm_factory: Any
    execute_single_tool: Callable[[dict, str], Coroutine[Any, Any, dict]]
    clean_json_answer: Callable[..., Any]
    agent: Agent
    api_key: str
    base_url: str | None
    response_format: dict
    json_enabled: bool
    has_tools: bool
    agent_tools: list[dict]
    tool_name_to_id: dict[str, str]
    messages: list
    context_assembler: ContextManager | None = None
    knowledge_retrieve: Callable[[str], Awaitable[Any]] | None = None
    knowledge_query: str | None = None

    @property
    def context_manager(self) -> ContextManager | None:
        """Canonical internal name for the legacy request field."""
        return self.context_assembler


@runtime_checkable
class ExecutionStrategy(Protocol, Generic[StateT]):
    """One concrete Agent execution algorithm."""

    name: str
    state_type: type[StateT]

    async def execute(
        self,
        ctx: StrategyContext[StateT],
    ) -> StrategyOutcome: ...


@runtime_checkable
class ExecutableExecutionStrategy(Protocol):
    """Outer-runtime adapter that executes a Strategy from a prepared request."""

    async def execute(
        self,
        request: ExecutionStrategyRequest,
    ) -> InstrumentedExecution: ...


@runtime_checkable
class ExecutionStrategyResolver(Protocol):
    """Resolve a runtime-ready Strategy adapter selected by an Agent snapshot."""

    def resolve(self, name: str) -> ExecutableExecutionStrategy: ...
