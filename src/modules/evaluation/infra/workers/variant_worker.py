from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import async_sessionmaker

from modules.evaluation.infra.database.models import (
    EvaluationTargetModel,
    EvaluationTestCaseModel,
    EvaluationTrialModel,
)
from modules.evaluation.infra.workers.concurrent_worker import (
    ConcurrentOutcomeAwareEvaluationRunProcessor,
    ConcurrentOutcomeAwareEvaluationRunWorker,
)
from shared.infra.config import Settings


class VariantAwareConcurrentEvaluationRunProcessor(
    ConcurrentOutcomeAwareEvaluationRunProcessor
):
    """Execute model variants and expose user-facing Judge failure taxonomy."""

    async def _execute_agent(
        self,
        trial: EvaluationTrialModel,
        target: EvaluationTargetModel,
        case: EvaluationTestCaseModel,
    ) -> tuple[dict[str, Any], dict[str, Any], None, UUID | None]:
        snapshot = target.snapshot or {}
        if not isinstance(snapshot.get("evaluation_variant"), dict):
            return await super()._execute_agent(trial, target, case)

        # The canonical Agent runtime applies snapshot_override for draft-style
        # invocations. A lightweight proxy keeps persisted target provenance
        # unchanged while executing the frozen derived configuration.
        runtime_target = SimpleNamespace(
            entity_id=target.entity_id,
            agent_release_id=None,
            snapshot=snapshot,
            source_type="draft",
            side=target.side,
        )
        return await super()._execute_agent(trial, runtime_target, case)

    async def _persist_final_result(self, **kwargs) -> None:
        await super()._persist_final_result(**kwargs)
        judge = kwargs["judge"]
        trial = kwargs["trial"]
        async with self._session_factory() as session, session.begin():
            row = await session.get(
                EvaluationTrialModel,
                trial.id,
                with_for_update=True,
            )
            if row is None:
                return
            metrics = dict(row.metrics or {})
            previous_judge_cost = float(
                metrics.get("judge_retry_previous_cost_usd") or 0
            )
            current_judge_cost = float(metrics.get("judge_cost_usd") or 0)
            if previous_judge_cost:
                metrics["judge_cost_usd"] = (
                    previous_judge_cost + current_judge_cost
                )
                metrics["judge_latest_attempt_cost_usd"] = current_judge_cost
                row.metrics = metrics

            if judge.structured_result is not None:
                return
            technical_error = str(judge.error or "")
            lowered = technical_error.lower()
            if "judge_output_length_limit" in lowered:
                code = "judge_output_length_limit"
                detail = (
                    "The Judge exhausted its output budget before completing the "
                    "structured score. Agent evidence was preserved and the judgment "
                    "can be retried without re-running the Agent or Tools."
                )
            elif "json" in lowered or "parse" in lowered:
                code = "judge_invalid_json"
                detail = (
                    "The Judge returned an invalid structured score. Agent evidence was "
                    "preserved and the judgment can be retried."
                )
            else:
                code = "judge_failed"
                detail = (
                    "The Judge could not complete this score. Agent evidence was "
                    "preserved for a judgment-only retry."
                )
            row.failure_code = code
            row.failure_detail = detail
            metrics = dict(row.metrics or {})
            metrics["judge_failure_code"] = code
            row.metrics = metrics


class VariantAwareConcurrentEvaluationRunWorker(
    ConcurrentOutcomeAwareEvaluationRunWorker
):
    def __init__(
        self,
        session_factory: async_sessionmaker,
        *,
        settings: Settings | None = None,
        worker_id: str | None = None,
    ) -> None:
        super().__init__(
            session_factory,
            settings=settings,
            worker_id=worker_id,
        )
        self._processor = VariantAwareConcurrentEvaluationRunProcessor(
            session_factory,
            settings=settings,
        )


__all__ = [
    "VariantAwareConcurrentEvaluationRunProcessor",
    "VariantAwareConcurrentEvaluationRunWorker",
]
