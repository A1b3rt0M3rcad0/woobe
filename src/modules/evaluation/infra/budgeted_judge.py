from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from modules.agent.infra.database.provider_model_repositories import ProviderModelModel
from modules.evaluation.application.token_budget import (
    budget_sections,
    context_window_from_metadata,
)
from modules.evaluation.infra.judge import EvaluatorModelGateway, JudgeResult


class BudgetedEvaluatorModelGateway(EvaluatorModelGateway):
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
        provider_model = await session.get(ProviderModelModel, provider_model_id)
        metadata = provider_model.meta if provider_model is not None else {}
        context_window = context_window_from_metadata(metadata or {})
        configured_input = int(judge_config.get("maximum_input_tokens", 8000))
        configured_output = min(int(judge_config.get("max_tokens", 800)), 1200)
        budgeted = budget_sections(
            [
                ("test_case", case_payload, 10, True),
                ("target_output", target_output, 10, True),
                ("rubric", rubric, 8, True),
                ("operational_evidence", operational_evidence, 5, False),
            ],
            maximum_input_tokens=max(2000, min(configured_input, 32_000)),
            reserved_output_tokens=max(256, configured_output),
            safety_margin_tokens=500,
            context_window=context_window,
        )
        payload = budgeted.payload
        evidence = payload.get("operational_evidence")
        if not isinstance(evidence, dict):
            evidence = {"compacted_evidence": evidence}
        evidence = {
            **evidence,
            "judge_context_budget": budgeted.report.to_dict(),
        }
        normalized_config = {
            **judge_config,
            "max_tokens": configured_output,
            "maximum_payload_chars": min(
                int(judge_config.get("maximum_payload_chars", 120_000)),
                max(10_000, configured_input * 4),
            ),
        }
        return await super().judge(
            session,
            project_id=project_id,
            provider_model_id=provider_model_id,
            rubric=payload.get("rubric") if isinstance(payload.get("rubric"), dict) else rubric,
            judge_config=normalized_config,
            case_payload=payload.get("test_case") if isinstance(payload.get("test_case"), dict) else case_payload,
            target_output=payload.get("target_output") if isinstance(payload.get("target_output"), dict) else target_output,
            operational_evidence=evidence,
        )


__all__ = ["BudgetedEvaluatorModelGateway"]
