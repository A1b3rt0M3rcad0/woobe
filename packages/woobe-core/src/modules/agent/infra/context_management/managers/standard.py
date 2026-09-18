from __future__ import annotations

from modules.agent.application.context_manager_sdk import (
    ContextManagerContext,
    ContextManagerOutcome,
)
from modules.agent.domain.context import ContextSourceType


class StandardContextManager:
    """General-purpose deterministic context algorithm expressed through SDK primitives."""

    name = "standard"

    def assemble(
        self,
        ctx: ContextManagerContext,
    ) -> ContextManagerOutcome:
        policy = ctx.policy

        ctx.candidates.allow(policy.allowed_sources)
        ctx.candidates.recent_session(
            max_messages=policy.session.max_messages,
            max_units=policy.session.max_units,
        )

        ctx.candidates.cap(
            ContextSourceType.CHECKPOINT,
            policy.checkpoints.max_units,
        )
        ctx.candidates.cap(
            ContextSourceType.MEMORY,
            policy.memory.max_units,
        )
        ctx.candidates.cap(
            ContextSourceType.KNOWLEDGE,
            policy.knowledge.max_units,
        )
        ctx.candidates.cap(
            ContextSourceType.TOOL,
            policy.tools.max_result_units,
        )
        ctx.candidates.cap(
            ContextSourceType.ARTIFACT,
            policy.artifacts.max_units,
        )
        ctx.candidates.cap(
            ContextSourceType.DELEGATION,
            policy.delegation.max_units,
        )

        ctx.candidates.deduplicate(
            strategy=policy.deduplication.strategy,
            sources=policy.deduplication.sources,
        )
        ctx.candidates.order(
            strategy=policy.ordering.strategy,
        )

        if ctx.has_active_skills:
            ctx.sources.skills()

        return ctx.complete()


__all__ = ["StandardContextManager"]
