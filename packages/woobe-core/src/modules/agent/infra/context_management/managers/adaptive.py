from __future__ import annotations

from pydantic import Field

from modules.agent.application.context_manager_sdk import (
    ContextCheckpointBoundary,
    ContextManagerContext,
    ContextManagerOutcome,
    ContextManagerState,
    ContextSummaryResult,
)
from modules.agent.domain.context import ContextSourceType


class AdaptiveContextState(ContextManagerState):
    summaries: dict[str, ContextSummaryResult] = Field(default_factory=dict)
    summary_generation: int = 0


def _bounded_cap(
    configured: int | None,
    *,
    usable: int | None,
    ratio: float,
    minimum: int,
) -> int | None:
    if usable is None:
        return configured
    adaptive = max(minimum, int(usable * ratio))
    return min(configured, adaptive) if configured is not None else adaptive


class AdaptiveContextManager:
    """Capacity-aware context algorithm with reusable semantic summaries."""

    name = "adaptive"
    state_type = AdaptiveContextState

    async def assemble(
        self,
        ctx: ContextManagerContext[AdaptiveContextState],
    ) -> ContextManagerOutcome:
        policy = ctx.policy
        usable = ctx.capacity.usable_input_budget_units

        ctx.candidates.allow(policy.allowed_sources)
        ctx.priorities.configure(policy.source_priorities)

        session_limit = _bounded_cap(
            policy.session.max_units,
            usable=usable,
            ratio=0.55,
            minimum=128,
        )
        ctx.candidates.recent_session(
            max_messages=policy.session.max_messages,
            max_units=session_limit,
        )

        ctx.candidates.cap(
            ContextSourceType.CHECKPOINT,
            _bounded_cap(
                policy.checkpoints.max_units,
                usable=usable,
                ratio=0.20,
                minimum=128,
            ),
        )
        ctx.candidates.cap(
            ContextSourceType.MEMORY,
            _bounded_cap(
                policy.memory.max_units,
                usable=usable,
                ratio=0.20,
                minimum=128,
            ),
        )
        ctx.candidates.cap(
            ContextSourceType.KNOWLEDGE,
            _bounded_cap(
                policy.knowledge.max_units,
                usable=usable,
                ratio=0.35,
                minimum=128,
            ),
        )
        ctx.candidates.cap(
            ContextSourceType.TOOL,
            _bounded_cap(
                policy.tools.max_result_units,
                usable=usable,
                ratio=0.20,
                minimum=64,
            ),
        )
        ctx.candidates.cap(
            ContextSourceType.ARTIFACT,
            _bounded_cap(
                policy.artifacts.max_units,
                usable=usable,
                ratio=0.25,
                minimum=64,
            ),
        )
        ctx.candidates.cap(
            ContextSourceType.DELEGATION,
            _bounded_cap(
                policy.delegation.max_units,
                usable=usable,
                ratio=0.35,
                minimum=64,
            ),
        )

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

        await self._manage_summaries(ctx)

        if ctx.has_active_skills:
            skill_units = ctx.inventory.units(ContextSourceType.SKILL)
            if usable is None or skill_units <= max(256, int(usable * 0.25)):
                ctx.sources.skills()

        return ctx.complete()

    async def _manage_summaries(
        self,
        ctx: ContextManagerContext[AdaptiveContextState],
    ) -> None:
        summary_policy = ctx.policy.summary
        if summary_policy.strategy == "disabled":
            return

        usable = ctx.capacity.usable_input_budget_units
        pressure_triggered = (
            usable is not None
            and usable > 0
            and ctx.inventory.total_units / usable >= summary_policy.trigger_at
        )

        for source in summary_policy.sources:
            if source not in ctx.policy.allowed_sources:
                continue

            preserve = (
                summary_policy.preserve_recent_messages
                if source == ContextSourceType.SESSION
                else 0
            )
            selection = ctx.summary.inspect(
                source,
                preserve_recent_messages=preserve,
            )
            if selection.candidate_count == 0:
                continue

            key = source.value
            cached = ctx.state.summaries.get(key)
            cached_applied = False
            if cached is not None:
                try:
                    ctx.summary.apply(cached)
                    cached_applied = True
                except ValueError:
                    ctx.state.summaries.pop(key, None)
                    cached = None

            previous_count = len(cached.source_refs) if cached is not None else 0
            refresh_due = (
                selection.candidate_count - previous_count
                >= summary_policy.refresh_after_messages
            )

            should_create = False
            if summary_policy.strategy == "pressure_triggered":
                should_create = pressure_triggered and (
                    cached is None or refresh_due
                )
            elif summary_policy.strategy == "rolling":
                should_create = (
                    (
                        cached is None
                        and selection.candidate_count
                        >= summary_policy.refresh_after_messages
                    )
                    or (cached is not None and refresh_due)
                )

            if not should_create:
                continue

            try:
                summary = await ctx.summary.create(
                    source,
                    target_units=summary_policy.target_units,
                    preserve_recent_messages=preserve,
                )
            except (RuntimeError, ValueError):
                if summary_policy.failure_mode == "fail":
                    raise
                if not cached_applied:
                    ctx.state.summaries.pop(key, None)
                continue

            ctx.state.summaries[key] = summary
            ctx.state.summary_generation += 1
            await ctx.checkpoint(ContextCheckpointBoundary.SUMMARY)


__all__ = [
    "AdaptiveContextManager",
    "AdaptiveContextState",
]
