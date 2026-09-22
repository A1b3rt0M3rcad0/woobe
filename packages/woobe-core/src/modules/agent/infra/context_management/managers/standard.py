from __future__ import annotations

from modules.agent.application.context_manager_sdk import (
    ContextManagerContext,
    ContextManagerOutcome,
    ContextManagerState,
)
from modules.agent.domain.context import ContextSourceType


class StandardContextManager:
    """General-purpose deterministic context algorithm expressed through SDK primitives."""

    name = "standard"
    state_type = ContextManagerState

    async def assemble(
        self,
        ctx: ContextManagerContext[ContextManagerState],
    ) -> ContextManagerOutcome:
        policy = ctx.policy

        ctx.candidates.allow(policy.allowed_sources)
        ctx.priorities.configure(policy.source_priorities)

        ctx.candidates.recent_session(
            max_messages=policy.session.max_messages,
            max_units=policy.session.max_units,
        )

        ctx.candidates.cap(ContextSourceType.CHECKPOINT, policy.checkpoints.max_units)
        ctx.candidates.cap(ContextSourceType.MEMORY, policy.memory.max_units)
        ctx.candidates.cap(ContextSourceType.KNOWLEDGE, policy.knowledge.max_units)
        ctx.candidates.cap(ContextSourceType.TOOL, policy.tools.max_result_units)
        ctx.candidates.cap(ContextSourceType.ARTIFACT, policy.artifacts.max_units)
        ctx.candidates.cap(ContextSourceType.DELEGATION, policy.delegation.max_units)

        ctx.candidates.deduplicate(
            strategy=policy.deduplication.strategy,
            sources=policy.deduplication.sources,
        )
        ctx.candidates.order(strategy=policy.ordering.strategy)

        ctx.budget.configure(
            max_input_units=policy.budget.max_input_units,
            runtime_reserve_units=policy.budget.runtime_reserve_units,
        )
        ctx.pressure.thresholds(
            moderate_at=policy.pressure.moderate_at,
            high_at=policy.pressure.high_at,
            critical_at=policy.pressure.critical_at,
        )

        if ctx.has_active_skills:
            ctx.sources.skills()

        return ctx.complete()


__all__ = ["StandardContextManager"]
