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
class ContextManagerKey:
    """Stable Context Manager identity.

    Context Managers are identified only by name. Behavioral alternatives use
    different names instead of version suffixes.
    """

    name: str

    def __post_init__(self) -> None:
        name = self.name.strip()
        if not name:
            raise ValueError("Context Manager name must not be empty")
        if ":" in name:
            raise ValueError("Context Manager name must not contain ':'")
        object.__setattr__(self, "name", name)

    @classmethod
    def parse(cls, value: str) -> ContextManagerKey:
        normalized = value.strip()
        if not normalized or ":" in normalized:
            raise ValueError("Context Manager key must be a plain name")
        return cls(name=normalized)

    def __str__(self) -> str:
        return self.name

    def as_dict(self) -> dict[str, str]:
        return {"name": self.name}


STANDARD_CONTEXT_MANAGER_KEY = ContextManagerKey(name="stdcm")
DEFAULT_CONTEXT_MANAGER_KEY = STANDARD_CONTEXT_MANAGER_KEY


def context_manager_key_from_runtime_config(value: object) -> ContextManagerKey:
    """Read the Context Manager name frozen in an Agent runtime snapshot."""

    if value is None:
        return STANDARD_CONTEXT_MANAGER_KEY
    if not isinstance(value, dict):
        raise ValueError("Agent runtime_config must be an object")

    canonical = value.get("context_manager")
    legacy = value.get("context_assembler")
    if canonical is not None and legacy is not None and canonical != legacy:
        raise ValueError(
            "runtime_config cannot define conflicting context_manager and context_assembler"
        )
    raw = canonical if canonical is not None else legacy
    if raw is None:
        return STANDARD_CONTEXT_MANAGER_KEY
    if not isinstance(raw, dict):
        raise ValueError("Context Manager selection must be an object")

    name = raw.get("name")
    if not isinstance(name, str):
        raise ValueError("Context Manager selection requires string name")

    unexpected = sorted(set(raw).difference({"name"}))
    if unexpected:
        raise ValueError(
            "Context Manager selection supports only the 'name' field; unsupported fields: "
            + ", ".join(unexpected)
        )
    return ContextManagerKey(name=name)


@dataclass(frozen=True, slots=True)
class ContextInvocationEnvironment:
    """Immutable per-invocation inputs consumed by Context Manager algorithms."""

    run_id: UUID | None = None
    input_message_id: UUID | None = None
    model_capacity_units: int | None = None
    reserved_output_units: int | None = None
    active_tool_definitions: tuple[Mapping[str, Any], ...] = ()
    skill_context: tuple[Mapping[str, Any], ...] = ()
    external_context_contract: Mapping[str, Any] | None = None
    model_external_context: Mapping[str, Any] | None = None
    context_selection_metadata: Mapping[str, Any] | None = None
    rag_metadata: Mapping[str, Any] | None = None
    context_rag_sources: tuple[Mapping[str, Any], ...] = ()
    context_manager_name: str | None = None
    parent_invocation_id: UUID | None = None
    network_execution_id: UUID | None = None
    network_invocation_id: UUID | None = None
    network_node_id: UUID | None = None


@dataclass(frozen=True, slots=True)
class ContextAssemblyRequest:
    messages: list[Any]
    model_invocation_id: UUID
    agent_run_id: UUID
    project_id: UUID
    provider: str
    model: str
    environment: ContextInvocationEnvironment
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
    replaces_message_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ContextInspectionRequest:
    """Read-only state supplied to one Context Manager inspection."""

    messages: tuple[Any, ...]
    contributions: tuple[ContextManagedContribution, ...]
    environment: ContextInvocationEnvironment
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
    environment: ContextInvocationEnvironment
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
class ContextManager(Protocol):
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
