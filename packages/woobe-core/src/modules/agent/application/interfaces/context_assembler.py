from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from modules.agent.application.interfaces.context_policy import ContextPolicyV1
from modules.agent.domain.context import ContextSnapshot


@dataclass(frozen=True, slots=True)
class ContextAssemblerKey:
    """Stable, serializable identity for a ContextAssembler implementation."""

    name: str
    version: str

    def __post_init__(self) -> None:
        name = self.name.strip()
        version = self.version.strip()
        if not name:
            raise ValueError("Context assembler name must not be empty")
        if not version:
            raise ValueError("Context assembler version must not be empty")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "version", version)

    def __str__(self) -> str:
        return f"{self.name}:{self.version}"

    def as_dict(self) -> dict[str, str]:
        return {"name": self.name, "version": self.version}


DEFAULT_CONTEXT_ASSEMBLER_KEY = ContextAssemblerKey(name="default", version="v1")


def context_assembler_key_from_runtime_config(value: object) -> ContextAssemblerKey:
    """Read the immutable assembler selection from an Agent runtime snapshot.

    Snapshots created before assembler selection existed resolve to default:v1 so
    historical releases keep the original Woobe context behavior.
    """

    if value is None:
        return DEFAULT_CONTEXT_ASSEMBLER_KEY
    if not isinstance(value, dict):
        raise ValueError("Agent runtime_config must be an object")

    raw = value.get("context_assembler")
    if raw is None:
        return DEFAULT_CONTEXT_ASSEMBLER_KEY
    if not isinstance(raw, dict):
        raise ValueError("context_assembler must be an object")

    name = raw.get("name")
    version = raw.get("version")
    if not isinstance(name, str) or not isinstance(version, str):
        raise ValueError("context_assembler requires string name and version")
    return ContextAssemblerKey(name=name, version=version)


class ContextAssemblyRuntimeContext(Protocol):
    """Read-only attribute surface consumed by Context Assembly.

    This is intentionally narrower than RequestExecutionContext so ContextAssembler
    implementations do not depend on the complete Agent runtime state container.
    Container values exposed through this view are input data and must be treated as
    immutable by assembler implementations.
    """

    @property
    def run_id(self) -> UUID | None: ...

    @property
    def input_message_id(self) -> UUID | None: ...

    @property
    def model_capacity_units(self) -> int | None: ...

    @property
    def reserved_output_units(self) -> int | None: ...

    @property
    def active_tool_definitions(self) -> list[dict[str, Any]] | None: ...

    @property
    def context_selection_metadata(self) -> dict[str, Any] | None: ...

    @property
    def rag_metadata(self) -> dict[str, Any] | None: ...

    @property
    def context_rag_sources(self) -> list[dict[str, Any]] | None: ...

    @property
    def context_assembler_name(self) -> str | None: ...

    @property
    def context_assembler_version(self) -> str | None: ...

    @property
    def parent_invocation_id(self) -> UUID | None: ...

    @property
    def network_execution_id(self) -> UUID | None: ...

    @property
    def network_invocation_id(self) -> UUID | None: ...

    @property
    def network_node_id(self) -> UUID | None: ...


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


@runtime_checkable
class ContextAssembler(Protocol):
    """Assemble the context for exactly one Model Invocation.

    Runtime hosts may share one assembler instance across concurrent Runs. Concrete
    implementations therefore must keep per-invocation mutable state in the request
    or local call scope instead of storing it on the assembler instance. Request
    values are inputs; implementations should return assembled output rather than
    mutate runtime-owned state in place.
    """

    def assemble(self, request: ContextAssemblyRequest) -> ContextAssemblyOutput: ...
