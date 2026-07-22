from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select

from modules.evaluation.application.secure_authoring import (
    SecureEvaluationSuiteAuthoringService,
)
from modules.evaluation.domain.authoring_contract import (
    generation_failure_metadata,
    normalize_authoring_payload,
)
from modules.evaluation.infra.database.models import (
    EvaluationAuthoringBatchModel,
    EvaluationAuthoringCallModel,
)
from shared.infra.errors import ConflictError, NotFoundError


_TERMINAL_BATCHES = {"completed", "failed", "cancelled"}


def _phase(status: str) -> str:
    return {
        "queued": "queued",
        "running": "generating",
        "partial": "processing_remaining_batches",
        "cancel_requested": "cancelling",
        "completed": "ready_for_review",
        "failed": "failed",
        "cancelled": "cancelled",
    }.get(status, status)


def _failure_for_batch(batch: EvaluationAuthoringBatchModel) -> dict[str, Any]:
    validation = (
        batch.validation_result
        if isinstance(batch.validation_result, dict)
        else {}
    )
    stored = (
        validation.get("failure")
        if isinstance(validation.get("failure"), dict)
        else None
    )
    return stored or generation_failure_metadata(batch.error, validation)


class DiagnosticEvaluationSuiteAuthoringService(SecureEvaluationSuiteAuthoringService):
    """Secure authoring facade with canonical normalization and user-facing diagnostics."""

    async def preview_context(self, **kwargs) -> dict[str, Any]:
        case_count = int(kwargs.get("case_count") or 0)
        batch_count = max(1, (case_count + 9) // 10)
        preview_kwargs = {**kwargs, "case_count": min(max(case_count, 1), 10)}
        data = await super().preview_context(**preview_kwargs)
        per_call_cost = data.get("estimated_cost_usd")
        data["requested_case_count"] = case_count
        data["estimated_batch_count"] = batch_count
        data["estimated_total_cost_usd"] = (
            float(per_call_cost) * batch_count if per_call_cost is not None else None
        )
        data["estimated_maximum_provider_calls"] = batch_count * 2
        return data

    async def validate_draft(
        self,
        payload: dict[str, Any],
        *,
        project_id: UUID | None = None,
        reference_target: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized, normalization_warnings = normalize_authoring_payload(payload)
        validation = await super().validate_draft(
            normalized,
            project_id=project_id,
            reference_target=reference_target,
        )
        return {
            **validation,
            "warnings": [
                *normalization_warnings,
                *validation.get("warnings", []),
            ],
            "normalization_warnings": normalization_warnings,
        }

    async def create_composed_suite(self, **kwargs) -> dict[str, Any]:
        normalized, warnings = normalize_authoring_payload(kwargs["cases_payload"])
        metadata = dict(kwargs.get("authoring_metadata") or {})
        if warnings:
            metadata["normalization_warnings"] = warnings
        return await super().create_composed_suite(
            **{
                **kwargs,
                "cases_payload": normalized,
                "authoring_metadata": metadata,
            }
        )

    async def retry_authoring_call(
        self,
        project_id: UUID,
        call_id: UUID,
    ) -> dict[str, Any]:
        async with self._session_factory() as session, session.begin():
            call = await session.get(
                EvaluationAuthoringCallModel,
                call_id,
                with_for_update=True,
            )
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
            retryable: list[EvaluationAuthoringBatchModel] = []
            for item in batches:
                failure = _failure_for_batch(item)
                if (
                    item.status == "failed"
                    and bool(failure.get("retryable"))
                    and int(item.attempt or 0) < 3
                ):
                    retryable.append(item)
            if not retryable:
                raise ConflictError(
                    "No failed authoring batch is retryable. Review the failure action or change the generation settings."
                )
            for item in retryable:
                validation = (
                    item.validation_result
                    if isinstance(item.validation_result, dict)
                    else {}
                )
                item.validation_result = {
                    **validation,
                    "failure": _failure_for_batch(item),
                }
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
        data = await super()._payload(session, call, batches=batches)
        now = datetime.now(timezone.utc)
        started_at = call.created_at
        if started_at is not None and started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)
        elapsed_seconds = (
            max(0, round((now - started_at).total_seconds()))
            if started_at is not None
            else None
        )
        processed = sum(1 for item in batches if item.status in _TERMINAL_BATCHES)
        data.update(
            {
                "phase": _phase(call.status),
                "processed_batch_count": processed,
                "processed_percent": (
                    round(processed / call.total_batch_count * 100, 1)
                    if call.total_batch_count
                    else 0
                ),
                "created_at": call.created_at,
                "elapsed_seconds": elapsed_seconds,
                "target": {
                    "target_type": call.target_type,
                    "source_type": call.target_source_type,
                    "entity_id": str(call.target_entity_id),
                    "version_id": str(call.target_version_id)
                    if call.target_version_id
                    else None,
                    "snapshot_hash": call.target_snapshot_hash,
                },
            }
        )
        enriched_batches: list[dict[str, Any]] = []
        serialized = {item["id"]: item for item in data.get("batches", [])}
        for batch in batches:
            item = dict(serialized.get(str(batch.id)) or {})
            validation = (
                batch.validation_result
                if isinstance(batch.validation_result, dict)
                else {}
            )
            failure = _failure_for_batch(batch)
            attempts = (
                validation.get("attempts")
                if isinstance(validation.get("attempts"), list)
                else []
            )
            returned = int(
                validation.get("returned_case_count")
                or len((batch.generated_payload or {}).get("cases") or [])
            )
            valid = int(validation.get("valid_case_count") or validation.get("case_count") or 0)
            invalid = int(
                validation.get("invalid_case_count")
                or len(validation.get("errors", []))
            )
            item.update(
                {
                    "returned_case_count": returned,
                    "valid_case_count": valid,
                    "invalid_case_count": invalid,
                    "failure_category": failure.get("category"),
                    "retryable": bool(failure.get("retryable")),
                    "recommended_action": failure.get("recommended_action"),
                    "validation_errors": validation.get("errors", [])[:20],
                    "normalization_warnings": validation.get(
                        "normalization_warnings", []
                    ),
                    "attempts": attempts,
                    "started_at": batch.started_at,
                    "completed_at": batch.completed_at,
                }
            )
            enriched_batches.append(item)
        data["batches"] = enriched_batches
        return data


__all__ = ["DiagnosticEvaluationSuiteAuthoringService"]
