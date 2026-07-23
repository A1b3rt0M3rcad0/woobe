from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from modules.evaluation.infra.governed_budgeted_judge import (
    GovernedBudgetedEvaluatorModelGateway,
)
from modules.evaluation.infra.judge import JudgeResult


_NULL_SCORE_SIGNATURES = (
    "float() argument must be a string or a real number, not 'nonetype'",
    "judge score must be numeric",
)


def sanitize_judge_config(value: dict[str, Any] | None) -> dict[str, Any]:
    """Treat explicit JSON nulls as omitted optional Judge settings."""

    return {
        str(key): item
        for key, item in dict(value or {}).items()
        if item is not None
    }


def is_null_score_contract_error(value: Any) -> bool:
    text = str(value or "").lower()
    return any(marker in text for marker in _NULL_SCORE_SIGNATURES)


class RuntimeSafeEvaluatorModelGateway(GovernedBudgetedEvaluatorModelGateway):
    """Normalize nullable Run configuration before governed Judge execution.

    Structured-response failures such as ``score: null`` are classified by the
    canonical failure taxonomy as ``judge_invalid_json``. The governed gateway
    then performs its existing bounded compact repair exactly once.
    """

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
    ) -> JudgeResult:
        return await super().judge(
            session,
            project_id=project_id,
            provider_model_id=provider_model_id,
            rubric=rubric,
            judge_config=sanitize_judge_config(judge_config),
            case_payload=case_payload,
            target_output=target_output,
            operational_evidence=operational_evidence,
        )


__all__ = [
    "RuntimeSafeEvaluatorModelGateway",
    "is_null_score_contract_error",
    "sanitize_judge_config",
]
