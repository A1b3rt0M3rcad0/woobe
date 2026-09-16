from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Coroutine, Generic, Protocol, TypeVar, runtime_checkable

from modules.agent.application.interfaces.context_assembler import ContextAssembler
from modules.agent.application.interfaces.execution import InstrumentedExecution
from modules.agent.application.strategy_sdk import (
    StrategyContext,
    StrategyOutcome,
    StrategyStateCodec,
    StrategyStateFactory,
)
from modules.agent.domain.entities import Agent


StateT = TypeVar("StateT")


@dataclass(frozen=True, slots=True)
class ExecutionStrategyRequest:
    """Outer runtime input used to prepare one Agent execution.

    Concrete Strategies must not consume this request directly. The Strategy Runtime
    resolves it into the stable ``StrategyContext`` API so algorithms do not depend on
    provider factories, runtime callbacks, persistence or transport plumbing.
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
    context_assembler: ContextAssembler | None = None


@runtime_checkable
class ExecutionStrategy(Protocol, Generic[StateT]):
    """Algorithm used by an Agent to conduct one execution."""

    async def execute(
        self,
        ctx: StrategyContext[StateT],
    ) -> StrategyOutcome: ...


@dataclass(frozen=True, slots=True)
class ExecutionStrategyDefinition(Generic[StateT]):
    """Composition metadata required to instantiate one concrete Strategy safely."""

    name: str
    strategy_factory: Callable[[], ExecutionStrategy[StateT]]
    state_factory: StrategyStateFactory[StateT]
    state_codec: StrategyStateCodec[StateT]


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
