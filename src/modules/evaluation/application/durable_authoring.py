from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from modules.evaluation.application.suite_authoring import (
    EvaluationSuiteAuthoringService,
    _allocate_coverage,
    _validate_tool_references,
)
from modules.evaluation.application.token_budget import (
    context_window_from_metadata,
    recommended_generation_output_tokens,
)
from modules.evaluation.domain.contracts import validate_suite_draft
from modules.evaluation.infra.database.models import (
    EvaluationAuthoringBatchModel,
    EvaluationAuthoringCallModel,
)
from shared.infra.errors import ConflictError, NotFoundError, ValidationError
from shared.infra.llm_cost import calculate_llm_cost, provider_model_pricing_snapshot


_TERMINAL_AUTHORING = {"completed", "failed", "cancelled"}


def _split_coverage(allocation: dict[str, int], batch_size: int = 10) -> list[dict[str, int]]:
    labels: list[str] = []
    for key, count in allocation.items():
        labels.extend([key] * max(0, int(count)))
    batches: list[dict[str, int]] = []
    for offset in range(0, len(labels), batch_size):
        batches.append(dict(Counter(labels[offset : offset + batch_size])))
    return batches


def _draft_uses_tools(draft: dict[str, Any]) -> bool:
    for case in draft.get("cases") or []:
        if not isinstance(case, dict):
            continue
        contract = case.get("expected_contract")
        tools = contract.get("tools") if isinstance(contract, dict) else None
        if not isinstance(tools, dict):
            continue
        if any(isinstance(tools.get(key), list) and tools.get(key) for key in ("required", "forbidden")):
            return True
    return False


class DurableEvaluationSuiteAuthoringService(EvaluationSuiteAuthoringService):
    """Asynchronous, resumable authoring facade over the canonical Suite service."""

    def __init__(self, session_factory: async_sessionmaker) -> None:
        super().__init__(session_factory)
        self._session_factory = session_factory

    async def generate_draft(
        self,
        *,
        project_id: UUID,
        target: dict[str, Any],
        generator_provider_model_id: UUID,
        objective: str,
        case_count: int,
        coverage: dict[str, Any] | None,
        error_case_ratio: float,
        language: str,
        maximum_input_tokens: int,
        maximum_cost_usd: float | None,
        created_by: UUID | None,
    ) -> dict[str, Any]:
        case_count = self._validate_case_count(case_count)
        objective = objective.strip()
        if len(objective) < 10:
            raise ValidationError("Suite generation objective must contain at least 10 characters")
        error_case_ratio = max(0.0, min(float(error_case_ratio), 0.8))
        allocation = _allocate_coverage(case_count, coverage, error_case_ratio)
        batch_allocations = _split_coverage(allocation)
        if not batch_allocations:
            raise ValidationError("Suite generation requires at least one Test Case")

        async with self._session_factory() as session, session.begin():
            provider_model = await self._provider_model(
                session,
                project_id=project_id,
                provider_model_id=generator_provider_model_id,
            )
            credential = await self._provider_credential(
                session,
                project_id=project_id,
                credential_id=provider_model.provider_credential_id,
            )
            resolved = await self._target_resolver.resolve(
                session,
                project_id=project_id,
                target_type=str(target.get("target_type") or "agent"),
                source_type=str(target.get("source_type") or "draft"),
                entity_id=UUID(str(target["entity_id"])),
                version_id=UUID(str(target["version_id"])) if target.get("version_id") else None,
            )
            maximum_batch_size = max(sum(item.values()) for item in batch_allocations)
            reserved_output = recommended_generation_output_tokens(maximum_batch_size)
            context_window = context_window_from_metadata(provider_model.meta or {})
            pack = await self._context_builder.build(
                session,
                project_id=project_id,
                target=resolved,
                objective=objective,
                maximum_input_tokens=maximum_input_tokens,
                reserved_output_tokens=reserved_output,
                context_window=context_window,
            )
            pricing = provider_model_pricing_snapshot(
                provider_model_id=provider_model.id,
                provider_credential_id=provider_model.provider_credential_id,
                provider=credential.provider,
                model=provider_model.model,
                metadata=provider_model.meta or {},
            )
            estimated = calculate_llm_cost(
                input_tokens=int(pack.budget.get("estimated_input_tokens") or 0) * len(batch_allocations),
                output_tokens=sum(
                    recommended_generation_output_tokens(sum(item.values()))
                    for item in batch_allocations
                ),
                pricing_snapshot=pricing,
            )
            if (
                maximum_cost_usd is not None
                and estimated["cost_usd"] is not None
                and float(estimated["cost_usd"]) > float(maximum_cost_usd)
            ):
                raise ValidationError("Estimated Suite generation cost exceeds the configured cost limit")

            call = EvaluationAuthoringCallModel(
                project_id=project_id,
                target_type=resolved.target_type,
                target_entity_id=resolved.entity_id,
                target_source_type=resolved.source_type,
                target_version_id=UUID(str(target["version_id"])) if target.get("version_id") else None,
                target_snapshot_hash=resolved.snapshot_hash,
                generator_provider_model_id=provider_model.id,
                generator_provider_credential_id=provider_model.provider_credential_id,
                provider=credential.provider,
                model=provider_model.model,
                objective=objective,
                requested_case_count=case_count,
                coverage_request={
                    "allocation": allocation,
                    "error_case_ratio": error_case_ratio,
                    "language": language,
                    "maximum_cost_usd": maximum_cost_usd,
                },
                status="queued",
                prompt_version=self._generator.PROMPT_VERSION,
                context_hash=pack.context_hash,
                context_stats={
                    **pack.budget,
                    "context_window": context_window,
                    "estimated_total_cost_usd": estimated["cost_usd"],
                },
                context_payload=pack.payload,
                total_batch_count=len(batch_allocations),
                completed_batch_count=0,
                created_by=created_by,
            )
            session.add(call)
            await session.flush()
            session.add_all(
                [
                    EvaluationAuthoringBatchModel(
                        authoring_call_id=call.id,
                        project_id=project_id,
                        batch_index=index,
                        requested_case_count=sum(batch.values()),
                        coverage_request=batch,
                        status="pending",
                    )
                    for index, batch in enumerate(batch_allocations, start=1)
                ]
            )
            await session.flush()
            return await self._payload(session, call)

    async def get_authoring_call(self, project_id: UUID, call_id: UUID) -> dict[str, Any]:
        async with self._session_factory() as session:
            call = await session.get(EvaluationAuthoringCallModel, call_id)
            if call is None or call.project_id != project_id:
                raise NotFoundError("Evaluation authoring call not found")
            return await self._payload(session, call)

    async def cancel_authoring_call(self, project_id: UUID, call_id: UUID) -> dict[str, Any]:
        async with self._session_factory() as session, session.begin():
            call = await session.get(EvaluationAuthoringCallModel, call_id, with_for_update=True)
            if call is None or call.project_id != project_id:
                raise NotFoundError("Evaluation authoring call not found")
            if call.status not in _TERMINAL_AUTHORING:
                call.cancel_requested_at = datetime.now(timezone.utc)
                call.status = "cancel_requested"
            return await self._payload(session, call)

    async def retry_authoring_call(self, project_id: UUID, call_id: UUID) -> dict[str, Any]:
        async with self._session_factory() as session, session.begin():
            call = await session.get(EvaluationAuthoringCallModel, call_id, with_for_update=True)
            if call is None or call.project_id != project_id:
                raise NotFoundError("Evaluation authoring call not found")
            batches = list(
                (
                    await session.scalars(
                        select(EvaluationAuthoringBatchModel)
                        .where(EvaluationAuthoringBatchModel.authoring_call_id == call.id)
                        .order_by(EvaluationAuthoringBatchModel.batch_index)
                    )
                ).all()
            )
            retryable = [item for item in batches if item.status == "failed" and int(item.attempt or 0) < 3]
            if not retryable:
                raise ConflictError("No failed authoring batch is eligible for retry")
            for item in retryable:
                item.status = "pending"
                item.error = None
                item.started_at = None
                item.completed_at = None
            call.status = "queued"
            call.error = None
            call.completed_at = None
            call.cancel_requested_at = None
            call.lease_owner = None
            call.lease_expires_at = None
            return await self._payload(session, call, batches=batches)

    async def validate_draft(
        self,
        payload: dict[str, Any],
        *,
        project_id: UUID | None = None,
        reference_target: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        validation = validate_suite_draft(payload)
        if reference_target is None:
            if _draft_uses_tools(payload):
                errors = [
                    *validation.get("errors", []),
                    {
                        "path": "reference_target",
                        "code": "reference_target_required",
                        "message": "A reference target is required when Test Cases require or forbid concrete Tools.",
                    },
                ]
                return {**validation, "valid": False, "errors": errors}
            return {
                **validation,
                "reference": {"mode": "generic", "snapshot_hash": None},
            }
        if project_id is None:
            raise ValidationError("Project is required for target-bound validation")
        async with self._session_factory() as session:
            resolved = await self._target_resolver.resolve(
                session,
                project_id=project_id,
                target_type=str(reference_target.get("target_type") or "agent"),
                source_type=str(reference_target.get("source_type") or "draft"),
                entity_id=UUID(str(reference_target["entity_id"])),
                version_id=(
                    UUID(str(reference_target["version_id"]))
                    if reference_target.get("version_id")
                    else None
                ),
            )
            pack = await self._context_builder.build(
                session,
                project_id=project_id,
                target=resolved,
                objective="Validate Evaluator Suite references against the selected target snapshot",
                maximum_input_tokens=16_000,
                reserved_output_tokens=1_000,
                context_window=32_000,
            )
            validation = _validate_tool_references(validation, context_pack=pack.payload)
            return {
                **validation,
                "reference": {
                    "mode": "target_bound",
                    "target_type": resolved.target_type,
                    "source_type": resolved.source_type,
                    "entity_id": str(resolved.entity_id),
                    "display_name": resolved.display_name,
                    "display_version": resolved.display_version,
                    "snapshot_hash": resolved.snapshot_hash,
                    "context_hash": pack.context_hash,
                },
            }

    async def _payload(
        self,
        session,
        call: EvaluationAuthoringCallModel,
        *,
        batches: list[EvaluationAuthoringBatchModel] | None = None,
    ) -> dict[str, Any]:
        if batches is None:
            batches = list(
                (
                    await session.scalars(
                        select(EvaluationAuthoringBatchModel)
                        .where(EvaluationAuthoringBatchModel.authoring_call_id == call.id)
                        .order_by(EvaluationAuthoringBatchModel.batch_index)
                    )
                ).all()
            )
        return {
            "authoring_call_id": str(call.id),
            "authoring_source": "ai_generated",
            "status": call.status,
            "source_snapshot_hash": call.target_snapshot_hash,
            "source_context_hash": call.context_hash,
            "requested_case_count": call.requested_case_count,
            "completed_batch_count": call.completed_batch_count,
            "total_batch_count": call.total_batch_count,
            "progress_percent": (
                round(call.completed_batch_count / call.total_batch_count * 100, 1)
                if call.total_batch_count
                else 0
            ),
            "generator": {
                "provider_model_id": str(call.generator_provider_model_id),
                "provider": call.provider,
                "model": call.model,
                "input_tokens": call.input_tokens,
                "output_tokens": call.output_tokens,
                "cost_usd": float(call.cost_usd) if call.cost_usd is not None else None,
                "error": call.error,
            },
            "context_budget": call.context_stats,
            "validation": call.validation_result,
            "draft": call.generated_payload,
            "cancel_requested_at": call.cancel_requested_at,
            "completed_at": call.completed_at,
            "batches": [
                {
                    "id": str(item.id),
                    "batch_index": item.batch_index,
                    "requested_case_count": item.requested_case_count,
                    "coverage": item.coverage_request,
                    "status": item.status,
                    "attempt": item.attempt,
                    "input_tokens": item.input_tokens,
                    "output_tokens": item.output_tokens,
                    "cost_usd": float(item.cost_usd) if item.cost_usd is not None else None,
                    "error": item.error,
                    "case_count": len((item.generated_payload or {}).get("cases") or []),
                }
                for item in batches
            ],
        }


__all__ = ["DurableEvaluationSuiteAuthoringService"]
