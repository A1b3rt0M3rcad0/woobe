from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.metering.infra.database.models import UsageEventModel


async def record_evaluation_model_usage(
    session: AsyncSession,
    *,
    source_id: UUID,
    project_id: UUID,
    usage_subtype: str,
    provider: str,
    model: str,
    provider_model_id: UUID | None,
    input_tokens: int | None,
    output_tokens: int | None,
    cost_usd: float | None,
    pricing_snapshot: dict[str, Any] | None,
    evaluation_run_id: UUID | None = None,
    evaluation_trial_id: UUID | None = None,
    data: dict[str, Any] | None = None,
) -> None:
    """Persist one idempotent Evaluation-only model usage event.

    Evaluation target runtime remains metered by the canonical Agent/Network paths.
    This projection records only auxiliary Judge and Suite Authoring calls.
    """
    existing = await session.scalar(
        select(UsageEventModel.id).where(UsageEventModel.source_event_id == source_id)
    )
    if existing is not None:
        return

    total_tokens = int(input_tokens or 0) + int(output_tokens or 0)
    cost_status = "priced" if cost_usd is not None else "unpriced"
    session.add(
        UsageEventModel(
            project_id=project_id,
            agent_id=None,
            network_id=None,
            network_execution_id=None,
            network_version_id=None,
            source_event_id=source_id,
            occurred_at=datetime.now(timezone.utc),
            trace_id=None,
            call_id=str(source_id),
            environment="evaluation",
            run_purpose="evaluation",
            evaluation_run_id=evaluation_run_id,
            evaluation_trial_id=evaluation_trial_id,
            comparison_pair_id=None,
            target_side=None,
            agent_release_id=None,
            agent_release_version=None,
            provider=provider,
            model=model,
            provider_model_id=provider_model_id,
            event_type="evaluation_model_call",
            quantity=1.0,
            unit="model_call",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            cost_status=cost_status,
            cost_reason=None if cost_usd is not None else "pricing_unavailable",
            usage_complete=input_tokens is not None and output_tokens is not None,
            pricing_snapshot=pricing_snapshot,
            data={
                "usage_category": "quality_assurance",
                "usage_subtype": usage_subtype,
                "total_tokens": total_tokens,
                **(data or {}),
            },
        )
    )


__all__ = ["record_evaluation_model_usage"]
