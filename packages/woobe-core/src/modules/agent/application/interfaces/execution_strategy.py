from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Coroutine, Protocol, runtime_checkable

from modules.agent.application.interfaces.context_assembler import ContextAssembler
from modules.agent.application.interfaces.execution import InstrumentedExecution
from modules.agent.domain.entities import Agent


@dataclass(frozen=True, slots=True)
class ExecutionStrategyRequest:
    """Complete input required to execute one Agent algorithm.

    The Agent Runtime owns lifecycle, persistence, recovery, observability and policy
    guarantees. A strategy receives only the dependencies and resolved inputs needed
    to decide how model invocations and capability loops are conducted.
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
class ExecutionStrategy(Protocol):
    """Algorithm used by an Agent to conduct one execution."""

    async def execute(self, request: ExecutionStrategyRequest) -> InstrumentedExecution: ...


@runtime_checkable
class ExecutionStrategyResolver(Protocol):
    """Resolve the concrete algorithm selected by an Agent runtime snapshot."""

    def resolve(self, name: str) -> ExecutionStrategy: ...
