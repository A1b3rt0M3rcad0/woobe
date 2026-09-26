from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, runtime_checkable
from uuid import UUID

from modules.agent.application.interfaces.context_policy import ContextPolicyV1
from modules.agent.domain.context import ContextSnapshot

class ContextBudgetExceeded(RuntimeError):
    """Context assembly could not fit mandatory input within the invocation budget."""

    def __init__(
        self,
        message: str,
        *,
        configured_budget_units: int | None = None,
        effective_budget_units: int | None = None,
        mandatory_units: int | None = None,
        model_capacity_units: int | None = None,
        reserved_output_units: int | None = None,
        runtime_reserve_units: int = 0,
    ) -> None:
        super().__init__(message)
        self.configured_budget_units = configured_budget_units
        self.effective_budget_units = effective_budget_units
        self.mandatory_units = mandatory_units
        self.model_capacity_units = model_capacity_units
        self.reserved_output_units = reserved_output_units
        self.runtime_reserve_units = runtime_reserve_units

    def failure_context(self) -> dict[str, Any]:
        return {
            "code": "CONTEXT_BUDGET_EXCEEDED",
            "context_fit_status": "UNFIT",
            "configured_budget_units": self.configured_budget_units,
            "effective_budget_units": self.effective_budget_units,
            "mandatory_units": self.mandatory_units,
            "model_capacity_units": self.model_capacity_units,
            "reserved_output_units": self.reserved_output_units,
            "runtime_reserve_units": self.runtime_reserve_units,
            "provider_called": False,
        }



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


@dataclass(frozen=True, slots=True)
class ContextManagedContribution:
    """Mutation produced by a Context Manager and persisted by the Runtime."""

    key: str
    source_type: str
    content: Any
    metadata: Mapping[str, Any] = field(default_factory=dict)
    replaces_message_indexes: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class ContextInspectionRequest:
    """Read-only state supplied to one Context Manager inspection."""

    messages: tuple[Any, ...]
    contributions: tuple[ContextManagedContribution, ...]
    runtime_context: ContextAssemblyRuntimeContext
    policy: ContextPolicyV1


@dataclass(frozen=True, slots=True)
class ContextInspectionOutput:
    message_count: int
    contribution_count: int
    estimated_input_units: int
    usable_input_units: int | None
    utilization: float | None
    pressure: str


@dataclass(frozen=True, slots=True)
class ContextSummaryRequest:
    """Model-assisted summarization requested by a Context Manager implementation."""

    instruction: str
    input_text: str
    target_units: int
    phase: str


@dataclass(frozen=True, slots=True)
class ContextSummaryOutput:
    content: str
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ContextCompactionRequest:
    """Input available when a Context Manager decides how to compact Context."""

    messages: tuple[Any, ...]
    contributions: tuple[ContextManagedContribution, ...]
    phase: str
    runtime_context: ContextAssemblyRuntimeContext
    policy: ContextPolicyV1


@dataclass(frozen=True, slots=True)
class ContextCompactionOutput:
    changed: bool
    upserts: tuple[ContextManagedContribution, ...] = ()
    remove_keys: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)


class ContextManagerCapabilities(Protocol):
    """Mechanisms available to Context Manager algorithms."""

    async def summarize(
        self,
        request: ContextSummaryRequest,
    ) -> ContextSummaryOutput: ...


@runtime_checkable
class ContextAssembler(Protocol):
    """Assemble the context for exactly one Model Invocation.

    Runtime hosts may share one assembler instance across concurrent Runs. Concrete
    implementations therefore must keep per-invocation mutable state in the request
    or local call scope instead of storing it on the assembler instance. Request
    values are inputs; implementations should return assembled output rather than
    mutate runtime-owned state in place.
    """

    def inspect(
        self,
        request: ContextInspectionRequest,
    ) -> ContextInspectionOutput: ...

    async def compact(
        self,
        request: ContextCompactionRequest,
        capabilities: ContextManagerCapabilities,
    ) -> ContextCompactionOutput: ...

    def assemble(self, request: ContextAssemblyRequest) -> ContextAssemblyOutput: ...
