from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from modules.agent.application.interfaces.context_policy import ContextPolicyV1
from modules.agent.domain.context import ContextSnapshot


@dataclass(frozen=True, slots=True)
class ContextAssemblyRequest:
    messages: list[Any]
    model_invocation_id: UUID
    agent_run_id: UUID
    project_id: UUID
    provider: str
    model: str
    runtime_context: Any
    policy: ContextPolicyV1


class ContextAssemblyOutput(Protocol):
    messages: list[Any]
    snapshot: ContextSnapshot


class ContextAssembler(ABC):
    """Assemble the context for exactly one Model Invocation.

    Runtime hosts may share one assembler instance across concurrent Runs. Concrete
    implementations therefore must keep per-invocation mutable state in the request
    or local call scope instead of storing it on the assembler instance.
    """

    @abstractmethod
    def assemble(self, request: ContextAssemblyRequest) -> ContextAssemblyOutput:
        ...
