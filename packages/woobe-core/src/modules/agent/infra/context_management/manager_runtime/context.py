from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from modules.agent.application.context_manager_sdk import ContextManagerOutcome
from modules.agent.application.interfaces.context_assembler import ContextAssemblyRequest
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
        "policy",
        "candidates",
        "priorities",
        "budget",
        "pressure",
        "sources",
        "_request",
        "_effective_policy",
    )

    def __init__(self, request: ContextAssemblyRequest) -> None:
        self._request = request
        self.policy = request.policy.model_copy(deep=True)
        self._effective_policy = request.policy.model_copy(deep=True)
        self.candidates = RuntimeContextCandidates(self._effective_policy)
        self.priorities = RuntimeContextPriorities(self._effective_policy)
        self.budget = RuntimeContextBudget(self._effective_policy)
        self.pressure = RuntimeContextPressure(self._effective_policy)
        self.sources = RuntimeContextSources()

    @property
    def has_active_skills(self) -> bool:
        return bool(getattr(self._request.runtime_context, "skill_context", None))

    def complete(self) -> ContextManagerOutcome:
        validated = ContextPolicyV1.model_validate(
            self._effective_policy.model_dump(mode="json")
        )
        return ContextManagerOutcome(
            policy=validated,
            materialize_skills=self.sources.materialize_skills,
        )
