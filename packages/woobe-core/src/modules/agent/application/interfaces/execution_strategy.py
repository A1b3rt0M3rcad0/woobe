from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Coroutine, Protocol, runtime_checkable

from modules.agent.application.interfaces.context_assembler import ContextAssembler
from modules.agent.application.interfaces.execution import InstrumentedExecution
from modules.agent.domain.entities import Agent


@dataclass(frozen=True, slots=True)
class ExecutionStrategyRequest:
    """Runtime-to-Strategy input for one Agent execution.

    This is the outer boundary supplied by the Agent Runtime. Concrete Strategies should
    resolve it through the shared execution preparation/capability layer rather than
    reaching into Runtime lifecycle services directly. The Runtime keeps ownership of
    persistence, Agent Run lifecycle, release/recovery wiring, policy, streaming transport
    and terminal observability guarantees.
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
