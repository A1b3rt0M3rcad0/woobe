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
    """Behavioral boundary for assembling one Model Invocation context."""

    @abstractmethod
    def assemble(self, request: ContextAssemblyRequest) -> ContextAssemblyOutput:
        ...
