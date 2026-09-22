from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from modules.agent.application.interfaces.context_policy import ContextPolicyV1
from modules.agent.domain.context import ContextSnapshot


DEFAULT_CONTEXT_MANAGER = "standard"

_LEGACY_CONTEXT_MANAGER_ALIASES = {
    "default": DEFAULT_CONTEXT_MANAGER,
    "stdcm": DEFAULT_CONTEXT_MANAGER,
}


def normalize_context_manager_name(value: str) -> str:
    normalized = value.strip().lower()
    if not normalized:
        raise ValueError("Context Manager name must not be empty")
    if normalized in {"stdcm:v1", "stdcm:v2", "default:v1"}:
        return DEFAULT_CONTEXT_MANAGER
    return _LEGACY_CONTEXT_MANAGER_ALIASES.get(normalized, normalized)


@dataclass(frozen=True, slots=True)
class ContextAssemblerSelection:
    """Stable unversioned Context Manager identity selected by an Agent snapshot."""

    name: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", normalize_context_manager_name(self.name))

    def as_dict(self) -> dict[str, str]:
        return {"name": self.name}


def context_assembler_selection_from_runtime_config(
    value: object,
) -> ContextAssemblerSelection:
    """Read the Context Manager selected by an Agent snapshot.

    New snapshots persist only the manager name. Historical default/stdcm
    versioned shapes remain readable and collapse to standard. Historical
    strategy_name is honored when present.
    """

    if value is None:
        return ContextAssemblerSelection(DEFAULT_CONTEXT_MANAGER)
    if not isinstance(value, dict):
        raise ValueError("Agent runtime_config must be an object")

    raw = value.get("context_assembler")
    if raw is None:
        return ContextAssemblerSelection(DEFAULT_CONTEXT_MANAGER)
    if isinstance(raw, str):
        return ContextAssemblerSelection(raw)
    if not isinstance(raw, dict):
        raise ValueError("context_assembler must be an object")

    strategy_name = raw.get("strategy_name")
    name = (
        strategy_name
        if isinstance(strategy_name, str) and strategy_name.strip()
        else raw.get("name")
    )
    if not isinstance(name, str) or not name.strip():
        raise ValueError("context_assembler requires a non-empty string name")
    return ContextAssemblerSelection(name)


def context_assembler_key_from_runtime_config(value: object) -> str:
    """Compatibility helper returning the canonical Context Manager name."""

    return context_assembler_selection_from_runtime_config(value).name


def context_assembler_strategy_key_from_runtime_config(value: object) -> str:
    """Compatibility alias for callers that previously consumed strategy keys."""

    return context_assembler_selection_from_runtime_config(value).name


class ContextAssemblyRuntimeContext(Protocol):
    """Read-only attribute surface consumed by Context Assembly."""

    @property
    def skill_context(self) -> list[dict[str, Any]] | None: ...

    @property
    def external_context_contract(self) -> dict[str, Any] | None: ...

    @property
    def model_external_context(self) -> dict[str, Any] | None: ...

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
    """Assemble the context for exactly one Model Invocation."""

    def assemble(self, request: ContextAssemblyRequest) -> ContextAssemblyOutput: ...
