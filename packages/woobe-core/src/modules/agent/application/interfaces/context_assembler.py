from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from modules.agent.application.interfaces.context_policy import ContextPolicyV1
from modules.agent.domain.context import ContextSnapshot


class ContextAssemblyRuntimeContext(Protocol):
    """Execution evidence/configuration consumed by Context Assembly.

    This is intentionally narrower than RequestExecutionContext so ContextAssembler
    implementations do not depend on the complete Agent runtime state container.
    """

    run_id: UUID | None
    input_message_id: UUID | None
    model_capacity_units: int | None
    reserved_output_units: int | None
    active_tool_definitions: list[dict[str, Any]] | None
    context_selection_metadata: dict[str, Any] | None
    rag_metadata: dict[str, Any] | None
    context_rag_sources: list[dict[str, Any]] | None
    parent_invocation_id: UUID | None
    network_execution_id: UUID | None
    network_invocation_id: UUID | None
    network_node_id: UUID | None


@dataclass(frozen=True, slots=True)
class ContextAssemblyRequest:
    messages: list[Any]
    model_invocation_id: UUID
    agent_run_id: UUID
    project_id: UUID
    provider: str
    model: str
    runtime_context: ContextAssemblyRuntimeContext
    policy: ContextPolicyV1


class ContextAssemblyOutput(Protocol):
    @property
    def messages(self) -> list[Any]: ...

    @property
    def snapshot(self) -> ContextSnapshot: ...


class ContextAssembler(ABC):
    """Assemble the context for exactly one Model Invocation.

    Runtime hosts may share one assembler instance across concurrent Runs. Concrete
    implementations therefore must keep per-invocation mutable state in the request
    or local call scope instead of storing it on the assembler instance.
    """

    @abstractmethod
    def assemble(self, request: ContextAssemblyRequest) -> ContextAssemblyOutput:
        ...
