from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.agent.infra.database.models import ProviderCredentialModel
from modules.agent.infra.database.provider_model_repositories import ProviderModelModel
from modules.evaluation.application.token_budget import context_window_from_metadata
from modules.evaluation.infra.database.models import (
    EvaluationSuiteVersionModel,
    EvaluationTestCaseModel,
)
from modules.evaluation.infra.judge import canonical_hash
from shared.infra.llm_cost import provider_model_pricing_snapshot

DEFAULT_JUDGE_INITIAL_TOKENS = 1_200
DEFAULT_JUDGE_RETRY_TOKENS = 2_048
PLATFORM_JUDGE_OUTPUT_CAP = 4_096
MINIMUM_JUDGE_OUTPUT_TOKENS = 256


def _integer(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _decimal(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _first_integer(source: dict[str, Any], keys: tuple[str, ...]) -> int | None:
    for key in keys:
        parsed = _integer(source.get(key), 0)
        if parsed > 0:
            return parsed
    return None


def _metadata_mapping(metadata: dict[str, Any] | None, key: str) -> dict[str, Any]:
    value = (metadata or {}).get(key)
    return value if isinstance(value, dict) else {}


def model_output_limit(metadata: dict[str, Any] | None) -> int:
    source = metadata or {}
    capabilities = _metadata_mapping(source, "capabilities")
    raw = _metadata_mapping(source, "raw")
    keys = (
        "max_output_tokens",
        "maximum_output_tokens",
        "output_token_limit",
        "max_completion_tokens",
        "completion_token_limit",
    )
    candidates = [
        _first_integer(source, keys),
        _first_integer(capabilities, keys),
        _first_integer(raw, keys),
    ]
    declared = next((value for value in candidates if value is not None), None)
    return max(
        MINIMUM_JUDGE_OUTPUT_TOKENS,
        min(declared or PLATFORM_JUDGE_OUTPUT_CAP, 32_768),
    )


def explicit_reasoning_support(metadata: dict[str, Any] | None) -> bool:
    source = metadata or {}
    capabilities = _metadata_mapping(source, "capabilities")
    for container in (source, capabilities):
        for key in ("supports_reasoning", "reasoning_enabled", "thinking"):
            if container.get(key) is True:
                return True
        reasoning = container.get("reasoning")
        if reasoning is True or isinstance(reasoning, dict):
            return True
    return False


def supported_parameters(metadata: dict[str, Any] | None) -> set[str]:
    source = metadata or {}
    values: list[Any] = []
    for container in (source, _metadata_mapping(source, "raw"), _metadata_mapping(source, "capabilities")):
        current = container.get("supported_parameters")
        if isinstance(current, list):
            values.extend(current)
    return {str(value).strip().lower() for value in values if str(value).strip()}


def judge_response_strategy(provider: str, metadata: dict[str, Any] | None) -> str:
    parameters = supported_parameters(metadata)
    if {"structured_outputs", "json_schema"} & parameters:
        return "json_schema"
    if {"response_format", "json_object", "json_mode"} & parameters:
        return "json_object"
    if provider == "openai":
        return "json_schema"
    if provider == "openrouter":
        return "json_object"
    return "text"


@dataclass(frozen=True)
class JudgeBudget:
    configured_initial_tokens: int
    configured_retry_tokens: int
    effective_initial_tokens: int
    effective_retry_tokens: int
    model_output_limit: int
    platform_output_cap: int
    context_window: int
    maximum_input_tokens: int

    def to_dict(self) -> dict[str, int]:
        return {
            "configured_initial_tokens": self.configured_initial_tokens,
            "configured_retry_tokens": self.configured_retry_tokens,
            "effective_initial_tokens": self.effective_initial_tokens,
            "effective_retry_tokens": self.effective_retry_tokens,
            "model_output_limit": self.model_output_limit,
            "platform_output_cap": self.platform_output_cap,
            "context_window": self.context_window,
            "maximum_input_tokens": self.maximum_input_tokens,
        }


def resolve_judge_budget(
    metadata: dict[str, Any] | None,
    judge_config: dict[str, Any] | None,
) -> JudgeBudget:
    config = judge_config or {}
    declared_limit = model_output_limit(metadata)
    platform_cap = max(
        MINIMUM_JUDGE_OUTPUT_TOKENS,
        min(
            _integer(config.get("platform_output_cap"), PLATFORM_JUDGE_OUTPUT_CAP),
            PLATFORM_JUDGE_OUTPUT_CAP,
        ),
    )
    configured_initial = max(
        MINIMUM_JUDGE_OUTPUT_TOKENS,
        _integer(config.get("max_tokens"), DEFAULT_JUDGE_INITIAL_TOKENS),
    )
    configured_retry = max(
        configured_initial,
        _integer(config.get("maximum_retry_tokens"), DEFAULT_JUDGE_RETRY_TOKENS),
    )
    hard_limit = min(declared_limit, platform_cap)
    effective_retry = max(
        MINIMUM_JUDGE_OUTPUT_TOKENS,
        min(configured_retry, hard_limit),
    )
    effective_initial = max(
        MINIMUM_JUDGE_OUTPUT_TOKENS,
        min(configured_initial, effective_retry),
    )
    context_window = context_window_from_metadata(metadata or {})
    maximum_input = max(
        1_000,
        min(
            _integer(config.get("maximum_input_tokens"), 8_000),
            max(1_000, context_window - effective_retry - 500),
            32_000,
        ),
    )
    return JudgeBudget(
        configured_initial_tokens=configured_initial,
        configured_retry_tokens=configured_retry,
        effective_initial_tokens=effective_initial,
        effective_retry_tokens=effective_retry,
        model_output_limit=declared_limit,
        platform_output_cap=platform_cap,
        context_window=context_window,
        maximum_input_tokens=maximum_input,
    )


def normalized_judge_config(
    metadata: dict[str, Any] | None,
    judge_config: dict[str, Any] | None,
) -> dict[str, Any]:
    config = dict(judge_config or {})
    budget = resolve_judge_budget(metadata, config)
    return {
        **config,
        "temperature": max(0.0, min(float(config.get("temperature", 0.0)), 2.0)),
        "output_budget_policy": "fixed",
        "max_tokens": budget.effective_initial_tokens,
        "maximum_retry_tokens": budget.effective_retry_tokens,
        "maximum_input_tokens": budget.maximum_input_tokens,
        "platform_output_cap": budget.platform_output_cap,
        "reasoning_policy": str(config.get("reasoning_policy") or "provider_default"),
        "reasoning_effort": str(config.get("reasoning_effort") or "none"),
        "attempts": max(1, min(_integer(config.get("attempts"), 3), 4)),
    }


def _credential_remaining_usd(metadata: dict[str, Any] | None) -> Decimal | None:
    source = metadata or {}
    limits = _metadata_mapping(source, "limits")
    billing = _metadata_mapping(source, "billing")
    for container in (source, limits, billing):
        for key in (
            "limit_remaining",
            "credits_remaining",
            "remaining_credits",
            "remaining_usd",
            "balance_usd",
            "balance",
        ):
            parsed = _decimal(container.get(key))
            if parsed is not None and parsed >= 0:
                return parsed
    return None


def _cost(
    *,
    input_tokens: int,
    output_tokens: int,
    pricing: dict[str, Any],
) -> Decimal | None:
    input_rate = _decimal(pricing.get("input_cost_per_token"))
    output_rate = _decimal(pricing.get("output_cost_per_token"))
    if input_rate is None or output_rate is None:
        return None
    return Decimal(input_tokens) * input_rate + Decimal(output_tokens) * output_rate


def judge_model_snapshot(
    provider_model: ProviderModelModel,
    credential: ProviderCredentialModel,
    *,
    judge_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    metadata = provider_model.meta or {}
    budget = resolve_judge_budget(metadata, judge_config)
    pricing = provider_model_pricing_snapshot(
        provider_model_id=provider_model.id,
        provider_credential_id=credential.id,
        provider=credential.provider,
        model=provider_model.model,
        metadata=metadata,
    )
    snapshot = {
        "provider_model_id": str(provider_model.id),
        "display_name": provider_model.name,
        "model": provider_model.model,
        "provider": credential.provider,
        "credential_id": str(credential.id),
        "credential_name": credential.name,
        "credential_status": credential.status,
        "model_status": provider_model.status,
        "capabilities": {
            "supports_reasoning": explicit_reasoning_support(metadata),
            "supported_parameters": sorted(supported_parameters(metadata)),
            "response_strategy": judge_response_strategy(credential.provider, metadata),
        },
        "budget": budget.to_dict(),
        "pricing": pricing,
    }
    return {**snapshot, "snapshot_hash": canonical_hash(snapshot)}


class JudgePreflightService:
    async def list_models(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
    ) -> list[dict[str, Any]]:
        models = list(
            (
                await session.scalars(
                    select(ProviderModelModel)
                    .where(ProviderModelModel.project_id == project_id)
                    .order_by(ProviderModelModel.name, ProviderModelModel.model)
                )
            ).all()
        )
        credential_ids = {item.provider_credential_id for item in models}
        credentials = {
            item.id: item
            for item in (
                await session.scalars(
                    select(ProviderCredentialModel).where(
                        ProviderCredentialModel.id.in_(credential_ids or [UUID(int=0)]),
                        ProviderCredentialModel.project_id == project_id,
                    )
                )
            ).all()
        }
        result: list[dict[str, Any]] = []
        for model in models:
            credential = credentials.get(model.provider_credential_id)
            if credential is None:
                continue
            snapshot = judge_model_snapshot(model, credential)
            blockers: list[dict[str, str]] = []
            if model.status != "active":
                blockers.append({"code": "judge_model_inactive", "message": "Judge Model is not active"})
            if credential.status != "active":
                blockers.append({"code": "judge_credential_inactive", "message": "Judge Model credential is not active"})
            result.append(
                {
                    **snapshot,
                    "eligible": not blockers,
                    "blockers": blockers,
                }
            )
        return result

    async def inspect_suite(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        suite_version: EvaluationSuiteVersionModel,
        repetitions: int,
        target_count: int = 1,
    ) -> dict[str, Any]:
        provider_model = await session.get(
            ProviderModelModel,
            suite_version.judge_provider_model_id,
        )
        blockers: list[dict[str, str]] = []
        warnings: list[dict[str, str]] = []
        if provider_model is None or provider_model.project_id != project_id:
            return {
                "status": "blocked",
                "can_execute": False,
                "blockers": [
                    {
                        "code": "judge_model_unavailable",
                        "message": "The configured Judge Model no longer exists in this Project",
                    }
                ],
                "warnings": [],
            }
        credential = await session.get(
            ProviderCredentialModel,
            provider_model.provider_credential_id,
        )
        if credential is None or credential.project_id != project_id:
            return {
                "status": "blocked",
                "can_execute": False,
                "blockers": [
                    {
                        "code": "judge_credential_invalid",
                        "message": "The Judge Model credential is unavailable for this Project",
                    }
                ],
                "warnings": [],
            }
        if provider_model.status != "active":
            blockers.append(
                {"code": "judge_model_inactive", "message": "The selected Judge Model is not active"}
            )
        if credential.status != "active":
            blockers.append(
                {"code": "judge_credential_invalid", "message": "The selected Judge Model credential is not active"}
            )

        normalized = normalized_judge_config(provider_model.meta or {}, suite_version.judge_config or {})
        snapshot = judge_model_snapshot(
            provider_model,
            credential,
            judge_config=normalized,
        )
        budget = resolve_judge_budget(provider_model.meta or {}, normalized)
        case_count = int(
            await session.scalar(
                select(EvaluationTestCaseModel.id)
                .where(
                    EvaluationTestCaseModel.dataset_version_id
                    == suite_version.dataset_version_id
                )
                .count()
            )
            or 0
        )
        # SQLAlchemy Select has no portable count() method. Recalculate using the
        # already-known Dataset Version rows when a dialect does not expose it.
        if case_count <= 0:
            rows = list(
                (
                    await session.scalars(
                        select(EvaluationTestCaseModel.id).where(
                            EvaluationTestCaseModel.dataset_version_id
                            == suite_version.dataset_version_id
                        )
                    )
                ).all()
            )
            case_count = len(rows)
        call_count = max(case_count, 0) * max(repetitions, 1) * max(target_count, 1)
        pricing = snapshot["pricing"]
        per_call_cost = _cost(
            input_tokens=budget.maximum_input_tokens,
            output_tokens=budget.effective_retry_tokens,
            pricing=pricing,
        )
        worst_case_cost = per_call_cost * call_count if per_call_cost is not None else None
        remaining = _credential_remaining_usd(credential.meta)
        configured_maximum = _decimal((normalized or {}).get("maximum_cost_usd"))

        if not pricing.get("configured"):
            warnings.append(
                {
                    "code": "judge_pricing_unknown",
                    "message": "Judge Model pricing is incomplete; maximum Evaluation cost cannot be proven before execution",
                }
            )
        if remaining is None:
            warnings.append(
                {
                    "code": "judge_affordability_unknown",
                    "message": "The provider did not expose a current credit limit for this credential; the first Judgment will run as a canary",
                }
            )
        elif worst_case_cost is not None and remaining < worst_case_cost:
            blockers.append(
                {
                    "code": "judge_insufficient_credits",
                    "message": (
                        f"The Judge credential exposes ${remaining:.6f} remaining, below the "
                        f"worst-case Judge budget of ${worst_case_cost:.6f}"
                    ),
                }
            )
        if configured_maximum is not None and worst_case_cost is not None and worst_case_cost > configured_maximum:
            blockers.append(
                {
                    "code": "judge_cost_limit_exceeded",
                    "message": (
                        f"Worst-case Judge cost ${worst_case_cost:.6f} exceeds the Suite limit "
                        f"of ${configured_maximum:.6f}"
                    ),
                }
            )

        return {
            "status": "blocked" if blockers else "ready",
            "can_execute": not blockers,
            "blockers": blockers,
            "warnings": warnings,
            "judge_model": snapshot,
            "normalized_judge_config": normalized,
            "case_count": case_count,
            "repetitions": repetitions,
            "target_count": target_count,
            "judge_call_count": call_count,
            "estimated_maximum_cost_usd": float(worst_case_cost)
            if worst_case_cost is not None
            else None,
            "credential_remaining_usd": float(remaining) if remaining is not None else None,
            "preflight_hash": canonical_hash(
                {
                    "suite_version_id": str(suite_version.id),
                    "judge_model_snapshot_hash": snapshot["snapshot_hash"],
                    "normalized_judge_config": normalized,
                    "case_count": case_count,
                    "repetitions": repetitions,
                    "target_count": target_count,
                }
            ),
        }


__all__ = [
    "DEFAULT_JUDGE_INITIAL_TOKENS",
    "DEFAULT_JUDGE_RETRY_TOKENS",
    "JudgeBudget",
    "JudgePreflightService",
    "MINIMUM_JUDGE_OUTPUT_TOKENS",
    "PLATFORM_JUDGE_OUTPUT_CAP",
    "explicit_reasoning_support",
    "judge_model_snapshot",
    "judge_response_strategy",
    "model_output_limit",
    "normalized_judge_config",
    "resolve_judge_budget",
]
