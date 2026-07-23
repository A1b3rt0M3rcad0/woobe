from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from modules.evaluation.application.run_judge import (
    selected_judge_config,
    selected_judge_provider_model_id,
)
from modules.evaluation.infra.budgeted_judge import BudgetedEvaluatorModelGateway
from modules.evaluation.infra.database.models import EvaluationRunModel
from modules.evaluation.infra.governed_judge import GovernedEvaluatorModelGateway


class GovernedBudgetedEvaluatorModelGateway(
    BudgetedEvaluatorModelGateway,
    GovernedEvaluatorModelGateway,
):
    """Apply context compaction and honor the immutable Judge selected by the Run."""

    async def judge(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        provider_model_id: UUID,
        rubric: dict[str, Any],
        judge_config: dict[str, Any],
        case_payload: dict[str, Any],
        target_output: dict[str, Any],
        operational_evidence: dict[str, Any],
    ):
        selected_model_id = provider_model_id
        selected_config = judge_config
        raw_run_id = operational_evidence.get("evaluation_run_id")
        if raw_run_id:
            try:
                run = await session.get(EvaluationRunModel, UUID(str(raw_run_id)))
            except (TypeError, ValueError):
                run = None
            if run is not None and run.project_id == project_id:
                selected_model_id = selected_judge_provider_model_id(
                    run,
                    provider_model_id,
                )
                selected_config = selected_judge_config(run, judge_config)

        return await super().judge(
            session,
            project_id=project_id,
            provider_model_id=selected_model_id,
            rubric=rubric,
            judge_config=selected_config,
            case_payload=case_payload,
            target_output=target_output,
            operational_evidence=operational_evidence,
        )


__all__ = ["GovernedBudgetedEvaluatorModelGateway"]
