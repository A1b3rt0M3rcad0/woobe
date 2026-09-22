from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from modules.agent.application.context_assembly import (
    analyze_context_candidates,
    estimate_input_units,
)
from modules.agent.application.context_manager_sdk import (
    ContextCheckpointBoundary,
    ContextManagerOutcome,
    ContextManagerState,
)
from modules.agent.application.interfaces.context_assembler import ContextAssemblyRequest
from modules.agent.application.skill_runtime import skill_contribution_content
from modules.agent.application.interfaces.context_policy import (
    ArtifactContextPolicy,
    CheckpointContextPolicy,
    ContextBudgetPolicy,
    ContextDeduplicationPolicy,
    ContextOrderingPolicy,
    ContextPolicyV1,
    ContextPressurePolicy,
    DelegationContextPolicy,
    KnowledgeContextPolicy,
    MemoryContextPolicy,
    SessionContextPolicy,
    ToolContextPolicy,
)
from modules.agent.domain.context import ContextPriority, ContextSourceType
from modules.agent.infra.context_management.manager_runtime.checkpoint import (
    RuntimeContextCheckpoint,
)
from modules.agent.infra.context_management.manager_runtime.summary import RuntimeContextSummary


_MANDATORY_SOURCE_PRIORITIES = {
    ContextSourceType.SYSTEM,
    ContextSourceType.USER_INPUT,
}


def _set_priority(
    policy: ContextPolicyV1,
    source: ContextSourceType,
    priority: ContextPriority,
) -> None:
    if source in _MANDATORY_SOURCE_PRIORITIES and priority != ContextPriority.MANDATORY:
        raise ValueError(f"{source.value} context priority must remain MANDATORY")
    policy.source_priorities[source] = priority


class RuntimeContextCandidates:
    """Concrete candidate controls backed by a per-invocation effective policy."""

    __slots__ = ("_policy",)

    def __init__(self, policy: ContextPolicyV1) -> None:
        self._policy = policy

    def allow(self, sources: list[ContextSourceType]) -> None:
        self._policy.allowed_sources = list(dict.fromkeys(sources))

    def recent_session(
        self,
        *,
        max_messages: int,
        max_units: int | None,
    ) -> None:
        self._policy.session = SessionContextPolicy(
            strategy="recent",
            max_messages=max_messages,
            max_units=max_units,
        )

    def cap(
        self,
        source: ContextSourceType,
        max_units: int | None,
    ) -> None:
        if source == ContextSourceType.CHECKPOINT:
            self._policy.checkpoints = CheckpointContextPolicy(max_units=max_units)
        elif source == ContextSourceType.MEMORY:
            self._policy.memory = MemoryContextPolicy(max_units=max_units)
        elif source == ContextSourceType.KNOWLEDGE:
            self._policy.knowledge = KnowledgeContextPolicy(max_units=max_units)
        elif source == ContextSourceType.TOOL:
            self._policy.tools = ToolContextPolicy(max_result_units=max_units)
        elif source == ContextSourceType.ARTIFACT:
            self._policy.artifacts = ArtifactContextPolicy(
                strategy=self._policy.artifacts.strategy,
                max_units=max_units,
            )
        elif source == ContextSourceType.DELEGATION:
            self._policy.delegation = DelegationContextPolicy(max_units=max_units)
        else:
            raise ValueError(
                f"Context source {source.value} does not expose an independent source cap"
            )

    def require(
        self,
        source: ContextSourceType,
        *,
        priority: ContextPriority = ContextPriority.MANDATORY,
    ) -> None:
        if source not in self._policy.allowed_sources:
            self._policy.allowed_sources.append(source)
        _set_priority(self._policy, source, priority)

    def deduplicate(
        self,
        *,
        strategy: Literal["none", "content_hash"],
        sources: list[ContextSourceType],
    ) -> None:
        self._policy.deduplication = ContextDeduplicationPolicy(
            strategy=strategy,
            sources=list(dict.fromkeys(sources)),
        )

    def order(
        self,
        *,
        strategy: Literal["preserve_input", "source_priority"],
    ) -> None:
        self._policy.ordering = ContextOrderingPolicy(strategy=strategy)


class RuntimeContextPriorities:
    """Priority decisions consumed by ordering and global overflow reduction."""

    __slots__ = ("_policy",)

    def __init__(self, policy: ContextPolicyV1) -> None:
        self._policy = policy

    def set(
        self,
        source: ContextSourceType,
        priority: ContextPriority,
    ) -> None:
        _set_priority(self._policy, source, priority)

    def configure(
        self,
        priorities: Mapping[ContextSourceType, ContextPriority],
    ) -> None:
        for source, priority in priorities.items():
            _set_priority(self._policy, source, priority)


class RuntimeContextInvocation:
    """Read-only invocation facts exposed without leaking the outer request."""

    __slots__ = ("_request", "_delegated")

    def __init__(self, request: ContextAssemblyRequest, *, delegated: bool) -> None:
        self._request = request
        self._delegated = delegated

    @property
    def phase(self) -> str | None:
        return self._request.phase

    @property
    def provider(self) -> str:
        return self._request.provider

    @property
    def model(self) -> str:
        return self._request.model

    @property
    def delegated(self) -> bool:
        return self._delegated

    @property
    def has_active_tools(self) -> bool:
        definitions = getattr(
            self._request.runtime_context,
            "active_tool_definitions",
            None,
        )
        return bool(definitions)


class RuntimeContextInventory:
    """Aggregate candidate facts without exposing raw provider messages."""

    __slots__ = ("_summary",)

    def __init__(self, request: ContextAssemblyRequest) -> None:
        analysis = analyze_context_candidates(
            request.messages,
            request.runtime_context,
        )
        self._summary = {
            source: dict(values)
            for source, values in analysis.source_summary.items()
        }

        tool_definitions = getattr(
            request.runtime_context,
            "active_tool_definitions",
            None,
        )
        if isinstance(tool_definitions, list) and tool_definitions:
            units = estimate_input_units(tool_definitions)
            item = self._summary.setdefault(
                ContextSourceType.SYSTEM.value,
                {"count": 0, "units": 0},
            )
            item["count"] += 1
            item["units"] += units

        skill_candidates = getattr(
            request.runtime_context,
            "skill_context",
            None,
        )
        if isinstance(skill_candidates, list) and skill_candidates:
            item = self._summary.setdefault(
                ContextSourceType.SKILL.value,
                {"count": 0, "units": 0},
            )
            seen: set[tuple[object, object]] = set()
            for candidate in skill_candidates:
                if not isinstance(candidate, dict):
                    continue
                identity = (
                    candidate.get("source_ref"),
                    candidate.get("resource_hash"),
                )
                if identity in seen:
                    continue
                seen.add(identity)
                try:
                    content = skill_contribution_content(candidate)
                except (KeyError, TypeError):
                    continue
                item["count"] += 1
                item["units"] += estimate_input_units(content)

    @property
    def total_count(self) -> int:
        return sum(item["count"] for item in self._summary.values())

    @property
    def total_units(self) -> int:
        return sum(item["units"] for item in self._summary.values())

    @property
    def sources(self) -> tuple[ContextSourceType, ...]:
        return tuple(
            source
            for source in ContextSourceType
            if self.contains(source)
        )

    def count(self, source: ContextSourceType) -> int:
        item = self._summary.get(source.value)
        return int(item["count"]) if item is not None else 0

    def units(self, source: ContextSourceType) -> int:
        item = self._summary.get(source.value)
        return int(item["units"]) if item is not None else 0

    def contains(self, source: ContextSourceType) -> bool:
        return self.count(source) > 0


class RuntimeContextCapacity:
    """Read-only capacity facts derived from invocation runtime state and effective policy."""

    __slots__ = ("_policy", "_runtime_context")

    def __init__(self, policy: ContextPolicyV1, runtime_context) -> None:
        self._policy = policy
        self._runtime_context = runtime_context

    @property
    def model_capacity_units(self) -> int | None:
        value = getattr(self._runtime_context, "model_capacity_units", None)
        return value if isinstance(value, int) and value > 0 else None

    @property
    def reserved_output_units(self) -> int | None:
        value = getattr(self._runtime_context, "reserved_output_units", None)
        return value if isinstance(value, int) and value >= 0 else None

    @property
    def runtime_reserve_units(self) -> int:
        return self._policy.budget.runtime_reserve_units

    @property
    def configured_input_budget_units(self) -> int | None:
        return self._policy.budget.max_input_units

    @property
    def model_usable_input_units(self) -> int | None:
        capacity = self.model_capacity_units
        if capacity is None:
            return None
        return max(
            0,
            capacity
            - (self.reserved_output_units or 0)
            - self.runtime_reserve_units,
        )

    @property
    def usable_input_budget_units(self) -> int | None:
        model_usable = self.model_usable_input_units
        configured = self.configured_input_budget_units
        if model_usable is not None and configured is not None:
            return min(model_usable, configured)
        return model_usable if model_usable is not None else configured

    @property
    def budget_clamped(self) -> bool:
        model_usable = self.model_usable_input_units
        configured = self.configured_input_budget_units
        return (
            model_usable is not None
            and configured is not None
            and configured > model_usable
        )


class RuntimeContextBudget:
    __slots__ = ("_policy",)

    def __init__(self, policy: ContextPolicyV1) -> None:
        self._policy = policy

    def configure(
        self,
        *,
        max_input_units: int | None,
        runtime_reserve_units: int,
    ) -> None:
        self._policy.budget = ContextBudgetPolicy(
            max_input_units=max_input_units,
            runtime_reserve_units=runtime_reserve_units,
        )


class RuntimeContextPressure:
    """Configure pressure evidence thresholds without changing overflow mechanics."""

    __slots__ = ("_policy",)

    def __init__(self, policy: ContextPolicyV1) -> None:
        self._policy = policy

    def thresholds(
        self,
        *,
        moderate_at: float,
        high_at: float,
        critical_at: float,
    ) -> None:
        self._policy.pressure = ContextPressurePolicy(
            moderate_at=moderate_at,
            high_at=high_at,
            critical_at=critical_at,
        )


class RuntimeContextSources:
    __slots__ = ("materialize_skills",)

    def __init__(self) -> None:
        self.materialize_skills = False

    def skills(self) -> None:
        self.materialize_skills = True


class RuntimeContextManagerContext:
    """Concrete implementation of the stable ContextManagerContext API."""

    __slots__ = (
        "_configured_policy",
        "state",
        "candidates",
        "capacity",
        "inventory",
        "invocation",
        "priorities",
        "budget",
        "pressure",
        "sources",
        "summary",
        "_checkpoint",
        "_request",
        "_effective_policy",
    )

    def __init__(
        self,
        request: ContextAssemblyRequest,
        *,
        state: ContextManagerState,
        summary: RuntimeContextSummary,
        checkpoint: RuntimeContextCheckpoint,
    ) -> None:
        self._request = request
        self._configured_policy = request.policy.model_copy(deep=True)
        self._effective_policy = request.policy.model_copy(deep=True)
        self.state = state
        self.candidates = RuntimeContextCandidates(self._effective_policy)
        self.capacity = RuntimeContextCapacity(
            self._effective_policy,
            request.runtime_context,
        )
        self.inventory = RuntimeContextInventory(request)
        self.invocation = RuntimeContextInvocation(
            request,
            delegated=bool(
                getattr(request.runtime_context, "parent_invocation_id", None)
            ),
        )
        self.priorities = RuntimeContextPriorities(self._effective_policy)
        self.budget = RuntimeContextBudget(self._effective_policy)
        self.pressure = RuntimeContextPressure(self._effective_policy)
        self.sources = RuntimeContextSources()
        self.summary = summary
        self._checkpoint = checkpoint

    @property
    def policy(self) -> ContextPolicyV1:
        return self._configured_policy

    @property
    def has_active_skills(self) -> bool:
        return bool(getattr(self._request.runtime_context, "skill_context", None))

    async def checkpoint(
        self,
        boundary: ContextCheckpointBoundary = ContextCheckpointBoundary.MANUAL,
    ) -> None:
        await self._checkpoint.save(self.state, boundary)

    def materialize_messages(self, messages: list) -> list:
        return self.summary.materialize(messages)

    def complete(self) -> ContextManagerOutcome:
        validated = ContextPolicyV1.model_validate(
            self._effective_policy.model_dump(mode="json")
        )
        return ContextManagerOutcome(
            policy=validated,
            materialize_skills=self.sources.materialize_skills,
        )
