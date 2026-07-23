from __future__ import annotations

from dataclasses import replace
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from modules.agent.infra.database.provider_model_repositories import ProviderModelModel
from modules.evaluation.application.judge_policy import normalized_judge_config
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
    """Final runtime guard for provider JSON that violates the Judge score contract.

    Some OpenAI-compatible providers return a syntactically valid object with
    ``score: null`` even when JSON mode is requested. The legacy normalizer then
    raises ``TypeError: float(None)``. That is a structured-response failure, not
    a target failure or an unknown provider outage, so route it through the
    governed compact repair path.
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
        safe_config = sanitize_judge_config(judge_config)
        result = await super().judge(
            session,
            project_id=project_id,
            provider_model_id=provider_model_id,
            rubric=rubric,
            judge_config=safe_config,
            case_payload=case_payload,
            target_output=target_output,
            operational_evidence=operational_evidence,
        )
        if result.structured_result is not None or not is_null_score_contract_error(result.error):
            return result

        provider_model = await session.get(ProviderModelModel, provider_model_id)
        if provider_model is None or provider_model.project_id != project_id:
            return result

        normalized = normalized_judge_config(provider_model.meta or {}, safe_config)
        primary = replace(
            result,
            error=(
                "judge_invalid_json: Judge structured response returned a null or "
                f"non-numeric score; {result.error or 'score contract violated'}"
            ),
        )
        return await self._repair(
            session,
            project_id=project_id,
            provider_model=provider_model,
            primary=primary,
            normalized_config=normalized,
            rubric=rubric,
            case_payload=case_payload,
            target_output=target_output,
            operational_evidence=operational_evidence,
        )


__all__ = [
    "RuntimeSafeEvaluatorModelGateway",
    "is_null_score_contract_error",
    "sanitize_judge_config",
]
