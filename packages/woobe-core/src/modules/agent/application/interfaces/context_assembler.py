from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable
from uuid import UUID

from modules.agent.application.interfaces.context_policy import ContextPolicyV1
from modules.agent.domain.context import ContextSnapshot


@dataclass(frozen=True, slots=True)
class ContextAssemblerKey:
    """Stable, serializable identity for a ContextAssembler selection or strategy."""

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

    @classmethod
    def parse(cls, value: str) -> ContextAssemblerKey:
        normalized = value.strip()
        name, separator, version = normalized.partition(":")
        if not separator or not name.strip() or not version.strip() or ":" in version:
            raise ValueError("Context assembler key must use '<name>:<version>'")
        return cls(name=name, version=version)

    def __str__(self) -> str:
        return f"{self.name}:{self.version}"

    def as_dict(self) -> dict[str, str]:
        return {"name": self.name, "version": self.version}


# Historical snapshots created before strategy identity was frozen resolve to the
# original Woobe behavior. Keep this mapping stable for replay/rollback.
LEGACY_DEFAULT_CONTEXT_ASSEMBLER_KEY = ContextAssemblerKey(name="default", version="v1")
STANDARD_CONTEXT_ASSEMBLER_KEY = ContextAssemblerKey(name="stdcm", version="v1")

# Compatibility alias for call sites/tests that still refer to the historical key.
DEFAULT_CONTEXT_ASSEMBLER_KEY = LEGACY_DEFAULT_CONTEXT_ASSEMBLER_KEY


@dataclass(frozen=True, slots=True)
class ContextAssemblerSelection:
    """Snapshot-safe selection identity plus the concrete strategy it resolves to."""

    selection_key: ContextAssemblerKey
    strategy_key: ContextAssemblerKey

    def as_dict(self) -> dict[str, str]:
        return {
            "name": self.selection_key.name,
            "version": self.selection_key.version,
            "strategy_name": self.strategy_key.name,
            "strategy_version": self.strategy_key.version,
        }


def context_assembler_selection_from_runtime_config(
    value: object,
) -> ContextAssemblerSelection:
    """Read a frozen Context Manager selection from an Agent runtime snapshot.

    New snapshots persist both the selection identity (for example ``default:v1``)
    and the resolved strategy identity (for example ``stdcm:v1``). This lets the
    system default change later without changing the behavior of existing Agents or
    immutable Releases.

    Historical snapshots created before strategy identity was persisted continue to
    resolve ``default:v1`` to the original Standard Context Manager behavior.
    """

    if value is None:
        return ContextAssemblerSelection(
            selection_key=LEGACY_DEFAULT_CONTEXT_ASSEMBLER_KEY,
            strategy_key=STANDARD_CONTEXT_ASSEMBLER_KEY,
        )
    if not isinstance(value, dict):
        raise ValueError("Agent runtime_config must be an object")

    raw = value.get("context_assembler")
    if raw is None:
        return ContextAssemblerSelection(
            selection_key=LEGACY_DEFAULT_CONTEXT_ASSEMBLER_KEY,
            strategy_key=STANDARD_CONTEXT_ASSEMBLER_KEY,
        )
    if not isinstance(raw, dict):
        raise ValueError("context_assembler must be an object")

    name = raw.get("name")
    version = raw.get("version")
    if not isinstance(name, str) or not isinstance(version, str):
        raise ValueError("context_assembler requires string name and version")
    selection_key = ContextAssemblerKey(name=name, version=version)

    strategy_name = raw.get("strategy_name")
    strategy_version = raw.get("strategy_version")
    if strategy_name is None and strategy_version is None:
        strategy_key = (
            STANDARD_CONTEXT_ASSEMBLER_KEY
            if selection_key == LEGACY_DEFAULT_CONTEXT_ASSEMBLER_KEY
            else selection_key
        )
    elif isinstance(strategy_name, str) and isinstance(strategy_version, str):
        strategy_key = ContextAssemblerKey(
            name=strategy_name,
            version=strategy_version,
        )
    else:
        raise ValueError(
            "context_assembler strategy_name and strategy_version must be provided together"
        )

    if selection_key.name != "default" and strategy_key != selection_key:
        raise ValueError(
            "Explicit Context Manager selections must match their strategy identity"
        )

    return ContextAssemblerSelection(
        selection_key=selection_key,
        strategy_key=strategy_key,
    )


def context_assembler_key_from_runtime_config(value: object) -> ContextAssemblerKey:
    """Compatibility helper returning the user-visible selection identity."""

    return context_assembler_selection_from_runtime_config(value).selection_key


def context_assembler_strategy_key_from_runtime_config(value: object) -> ContextAssemblerKey:
    """Return the concrete strategy identity frozen in the Agent snapshot."""

    return context_assembler_selection_from_runtime_config(value).strategy_key


class ContextAssemblyRuntimeContext(Protocol):
    """Read-only attribute surface consumed by Context Assembly.

    This is intentionally narrower than RequestExecutionContext so ContextAssembler
    implementations do not depend on the complete Agent runtime state container.
    Container values exposed through this view are input data and must be treated as
    immutable by assembler implementations.
    """

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
    def context_assembler_version(self) -> str | None: ...

    @property
    def context_assembler_strategy_name(self) -> str | None: ...

    @property
    def context_assembler_strategy_version(self) -> str | None: ...

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
