from __future__ import annotations

from dataclasses import replace
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from modules.agent.infra.database.provider_model_repositories import ProviderModelModel
from modules.evaluation.application.token_budget import (
    budget_sections,
    context_window_from_metadata,
)
from modules.evaluation.infra.adaptive_judge import (
    AdaptiveEvaluatorModelGateway,
    judge_output_token_limit,
    recommended_judge_output_tokens,
)
from modules.evaluation.infra.judge import JudgeResult


def _declares_reasoning(metadata: dict[str, Any]) -> bool:
    for key in ("supports_reasoning", "reasoning_enabled", "thinking"):
        if metadata.get(key) is True:
            return True
    reasoning = metadata.get("reasoning")
    return reasoning is True or isinstance(reasoning, dict)


def _reasoning_policy(metadata: dict[str, Any], judge_config: dict[str, Any]) -> str:
    configured = judge_config.get("reasoning_policy")
    if configured is not None:
        return str(configured)
    # Model names are not a reliable capability contract. When the Provider Model
    # did not explicitly declare reasoning support, use provider defaults and avoid
    # sending speculative `reasoning` or `thinking` controls.
    return "disabled" if _declares_reasoning(metadata) else "provider_default"


class BudgetedEvaluatorModelGateway(AdaptiveEvaluatorModelGateway):
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
        model = provider_model.model if provider_model is not None else ""
        context_window = context_window_from_metadata(metadata or {})
        configured_input = int(judge_config.get("maximum_input_tokens", 8000))
        configured_output = recommended_judge_output_tokens(
            model,
            metadata or {},
            judge_config,
        )
        model_output_ceiling = judge_output_token_limit(model, metadata or {})
        try:
            configured_retry = int(judge_config.get("maximum_retry_tokens") or 0)
        except (TypeError, ValueError):
            configured_retry = 0
        policy = str(judge_config.get("output_budget_policy") or "auto").lower()
        if policy == "fixed":
            retry_ceiling = max(configured_output, configured_retry or configured_output)
        elif configured_retry <= 8192:
            retry_ceiling = model_output_ceiling
        else:
            retry_ceiling = configured_retry
        retry_ceiling = min(max(retry_ceiling, configured_output), model_output_ceiling)

        case_with_policy = {
            **case_payload,
            "outcome_judging_policy": {
                "success": "Judge the public response against the expected behavior.",
                "refusal": (
                    "A safe, policy-compliant refusal is the intended successful behavior "
                    "when it matches the supplied criteria."
                ),
                "handled_error": (
                    "A controlled public error or recovery response is the intended successful "
                    "behavior when it matches the supplied criteria."
                ),
                "expected_failure": (
                    "A runtime failure may be correct only when its observed origin, stage and "
                    "code satisfy the explicit expected_outcome contract."
                ),
                "platform_failure": (
                    "Worker, persistence, snapshot, lease, cancellation or internal platform "
                    "failures must be inconclusive and never passed."
                ),
            },
        }
        budgeted = budget_sections(
            [
                ("test_case", case_with_policy, 10, True),
                ("target_output", target_output, 10, True),
                ("rubric", rubric, 8, True),
                ("operational_evidence", operational_evidence, 5, False),
            ],
            maximum_input_tokens=max(2000, min(configured_input, 32_000)),
            reserved_output_tokens=max(512, retry_ceiling),
            safety_margin_tokens=500,
            context_window=context_window,
        )
        payload = budgeted.payload
        evidence = payload.get("operational_evidence")
        if not isinstance(evidence, dict):
            evidence = {"compacted_evidence": evidence}
        report = budgeted.report.to_dict()
        evidence = {**evidence, "judge_context_budget": report}
        normalized_config = {
            **judge_config,
            "output_budget_policy": judge_config.get("output_budget_policy", "auto"),
            "reasoning_policy": _reasoning_policy(metadata or {}, judge_config),
            "reasoning_effort": judge_config.get("reasoning_effort", "none"),
            "max_tokens": configured_output,
            "maximum_retry_tokens": retry_ceiling,
            # Two provider-control fallbacks plus three effective Judge calls fit in this
            # bounded six-attempt envelope without allowing unbounded external retries.
            "attempts": max(6, int(judge_config.get("attempts", 2))),
            "maximum_payload_chars": min(
                int(judge_config.get("maximum_payload_chars", 120_000)),
                max(10_000, configured_input * 4),
            ),
        }
        result = await super().judge(
            session,
            project_id=project_id,
            provider_model_id=provider_model_id,
            rubric=payload.get("rubric") if isinstance(payload.get("rubric"), dict) else rubric,
            judge_config=normalized_config,
            case_payload=(
                payload.get("test_case")
                if isinstance(payload.get("test_case"), dict)
                else case_with_policy
            ),
            target_output=(
                payload.get("target_output")
                if isinstance(payload.get("target_output"), dict)
                else target_output
            ),
            operational_evidence=evidence,
        )
        if result.structured_result is None:
            return result
        return replace(
            result,
            structured_result={
                **result.structured_result,
                "context_budget": report,
            },
        )


__all__ = [
    "BudgetedEvaluatorModelGateway",
    "_declares_reasoning",
    "_reasoning_policy",
]
