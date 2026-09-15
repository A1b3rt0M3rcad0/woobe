from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from modules.agent.application.interfaces.execution import InstrumentedExecution
from modules.agent.application.interfaces.execution_context import current_execution
from modules.agent.infra.execution.agent_recovery_checkpoint import (
    StrategyExecutionResume,
    checkpoint_strategy_boundary,
    clone_execution,
    load_strategy_execution_resume,
)

CheckpointFn = Callable[..., Awaitable[None]]
ResumeLoader = Callable[..., StrategyExecutionResume | None]
_STRATEGY_RESUME_POLICY = "continue_execution_strategy"


@dataclass(frozen=True, slots=True)
class StrategyRecoveryCapability:
    """Persist and restore opaque continuation cursors for one execution Strategy."""

    strategy_name: str
    checkpoint_fn: CheckpointFn = checkpoint_strategy_boundary
    resume_loader: ResumeLoader = load_strategy_execution_resume

    def load(self) -> StrategyExecutionResume | None:
        context = current_execution.get()
        value = getattr(context, "resume_state", None) if context is not None else None
        is_strategy_checkpoint = (
            isinstance(value, dict)
            and value.get("resume_policy") == _STRATEGY_RESUME_POLICY
        )
        if is_strategy_checkpoint:
            stored_strategy = value.get("execution_strategy")
            if stored_strategy != self.strategy_name:
                raise RuntimeError(
                    "Execution Strategy recovery checkpoint mismatch: "
                    f"expected {self.strategy_name}, got {stored_strategy}"
                )

        resume = self.resume_loader(value, strategy_name=self.strategy_name)
        if resume is None:
            if is_strategy_checkpoint:
                raise RuntimeError("Invalid Execution Strategy recovery checkpoint")
            return None
        if context is not None:
            context.execution = clone_execution(resume.execution)
            context.resume_state = None
        return resume

    async def checkpoint(
        self,
        *,
        phase: str,
        messages: list[Any],
        base_message_count: int,
        execution: InstrumentedExecution,
        cursor: dict[str, Any],
    ) -> None:
        await self.checkpoint_fn(
            strategy_name=self.strategy_name,
            phase=phase,
            messages=messages,
            base_message_count=base_message_count,
            execution=execution,
            cursor=cursor,
        )
