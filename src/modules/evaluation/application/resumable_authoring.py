from __future__ import annotations

from collections import Counter
from typing import Any
from uuid import UUID

from sqlalchemy import select

from modules.evaluation.application.diagnostic_authoring import (
    DiagnosticEvaluationSuiteAuthoringService,
)
from modules.evaluation.application.token_budget import (
    context_window_from_metadata,
    recommended_generation_output_tokens,
)
from modules.evaluation.application.tool_catalog import build_target_tool_catalog
from modules.evaluation.infra.database.authoring_models import (
    EvaluationAuthoringAttemptModel,
    EvaluationAuthoringCaseSlotModel,
)
from modules.evaluation.infra.database.models import (
    EvaluationAuthoringBatchModel,
    EvaluationAuthoringCallModel,
)
from shared.infra.errors import ConflictError, NotFoundError


_READY_SLOT = "ready"


def _coverage_labels(coverage: dict[str, Any], expected: int) -> list[str]:
    labels: list[str] = []
    for key, count in coverage.items():
        labels.extend([str(key)] * max(0, int(count or 0)))
    if len(labels) < expected:
        labels.extend(["general"] * (expected - len(labels)))
    return labels[:expected]


def _context_with_tool_contract(
    payload: dict[str, Any],
    tool_catalog: dict[str, Any],
) -> dict[str, Any]:
    allowed_names = list(tool_catalog.get("allowed_names") or [])
    return {
        **payload,
        "tool_catalog": tool_catalog,
        "tool_contract": {
            "allowed_names": allowed_names,
            "rules": [
                "Only exact names from allowed_names may appear in expected_contract.tools.",
                "Never invent a Tool name.",
                "Asking a question, requesting information, refusing, responding, and explaining an error are behaviors unless an exact Tool with that name is listed.",
                "When allowed_names is empty, required and forbidden Tool arrays must be empty.",
            ],
        },
    }


class ResumableEvaluationSuiteAuthoringService(
    DiagnosticEvaluationSuiteAuthoringService
):
    """Authoring facade with canonical Tool catalog and per-Use-Case resume."""

    async def preview_context(self, **kwargs) -> dict[str, Any]:
        project_id = kwargs["project_id"]
        target = kwargs["target"]
        async with self._session_factory() as session:
            resolved = await self._target_resolver.resolve(
                session,
                project_id=project_id,
                target_type=str(target.get("target_type") or "agent"),
                source_type=str(target.get("source_type") or "draft"),
                entity_id=UUID(str(target["entity_id"])),
                version_id=(
                    UUID(str(target["version_id"]))
                    if target.get("version_id")
                    else None
                ),
            )
            tool_catalog = await build_target_tool_catalog(
                session,
                target=resolved,
                project_id=project_id,
            )
        data = await super().preview_context(**kwargs)
        data["tool_catalog"] = {
            "status": tool_catalog["status"],
            "source": tool_catalog["source"],
            "tool_count": len(tool_catalog["allowed_names"]),
            "allowed_names": tool_catalog["allowed_names"],
            "immutable": tool_catalog["immutable"],
        }
        return data

    async def generate_draft(self, **kwargs) -> dict[str, Any]:
        project_id = kwargs["project_id"]
        target = kwargs["target"]
        async with self._session_factory() as session:
            resolved = await self._target_resolver.resolve(
                session,
                project_id=project_id,
                target_type=str(target.get("target_type") or "agent"),
                source_type=str(target.get("source_type") or "draft"),
                entity_id=UUID(str(target["entity_id"])),
                version_id=(
                    UUID(str(target["version_id"]))
                    if target.get("version_id")
                    else None
                ),
            )
            tool_catalog = await build_target_tool_catalog(
                session,
                target=resolved,
                project_id=project_id,
            )

        created = await super().generate_draft(**kwargs)
        call_id = UUID(str(created["authoring_call_id"]))
        async with self._session_factory() as session, session.begin():
            call = await session.get(
                EvaluationAuthoringCallModel,
                call_id,
                with_for_update=True,
            )
            if call is None:
                raise NotFoundError("Evaluation authoring call not found")
            call.context_payload = _context_with_tool_contract(
                dict(call.context_payload or {}),
                tool_catalog,
            )
            stats = dict(call.context_stats or {})
            stats["tool_catalog"] = {
                "status": tool_catalog["status"],
                "source": tool_catalog["source"],
                "tool_count": len(tool_catalog["allowed_names"]),
                "immutable": tool_catalog["immutable"],
            }
            call.context_stats = stats

            existing = await session.scalar(
                select(EvaluationAuthoringCaseSlotModel.id)
                .where(EvaluationAuthoringCaseSlotModel.authoring_call_id == call.id)
                .limit(1)
            )
            batches = list(
                (
                    await session.scalars(
                        select(EvaluationAuthoringBatchModel)
                        .where(EvaluationAuthoringBatchModel.authoring_call_id == call.id)
                        .order_by(EvaluationAuthoringBatchModel.batch_index)
                    )
                ).all()
            )
            if existing is None:
                position = 1
                slots: list[EvaluationAuthoringCaseSlotModel] = []
                for batch in batches:
                    labels = _coverage_labels(
                        dict(batch.coverage_request or {}),
                        int(batch.requested_case_count),
                    )
                    for category in labels:
                        slots.append(
                            EvaluationAuthoringCaseSlotModel(
                                authoring_call_id=call.id,
                                authoring_batch_id=batch.id,
                                project_id=project_id,
                                position=position,
                                coverage_category=category,
                                status="planned",
                            )
                        )
                        position += 1
                session.add_all(slots)
                await session.flush()
            return await self._payload(session, call, batches=batches)

    async def resume_authoring_call(
        self,
        *,
        project_id: UUID,
        call_id: UUID,
        provider_model_id: UUID | None = None,
        strategy: str = "retry_failed_and_missing",
    ) -> dict[str, Any]:
        allowed_strategies = {
            "retry_failed_and_missing",
            "repair_tool_references",
            "retry_provider_call",
            "continue_with_new_model",
            "retry_with_larger_output_budget",
        }
        if strategy not in allowed_strategies:
            raise ConflictError("Unsupported authoring resume strategy")

        async with self._session_factory() as session, session.begin():
            call = await session.get(
                EvaluationAuthoringCallModel,
                call_id,
                with_for_update=True,
            )
            if call is None or call.project_id != project_id:
                raise NotFoundError("Evaluation authoring call not found")
            if call.status == "completed":
                raise ConflictError("Completed authoring calls do not require resume")

            slots = list(
                (
                    await session.scalars(
                        select(EvaluationAuthoringCaseSlotModel)
                        .where(
                            EvaluationAuthoringCaseSlotModel.authoring_call_id == call.id
                        )
                        .order_by(EvaluationAuthoringCaseSlotModel.position)
                    )
                ).all()
            )
            eligible = [
                slot
                for slot in slots
                if slot.status not in {_READY_SLOT, "cancelled"}
            ]
            if not eligible:
                raise ConflictError("No incomplete Use Case is eligible for resume")

            request = dict(call.coverage_request or {})
            if (
                provider_model_id is not None
                and provider_model_id != call.generator_provider_model_id
            ):
                provider_model = await self._provider_model(
                    session,
                    project_id=project_id,
                    provider_model_id=provider_model_id,
                )
                credential = await self._provider_credential(
                    session,
                    project_id=project_id,
                    credential_id=provider_model.provider_credential_id,
                )
                resolved = await self._target_resolver.resolve(
                    session,
                    project_id=project_id,
                    target_type=call.target_type,
                    source_type=call.target_source_type,
                    entity_id=call.target_entity_id,
                    version_id=call.target_version_id,
                )
                tool_catalog = await build_target_tool_catalog(
                    session,
                    target=resolved,
                    project_id=project_id,
                )
                context_window = context_window_from_metadata(provider_model.meta or {})
                maximum_input_tokens = int(
                    (call.context_stats or {}).get("maximum_input_tokens") or 16_000
                )
                pack = await self._context_builder.build(
                    session,
                    project_id=project_id,
                    target=resolved,
                    objective=call.objective,
                    maximum_input_tokens=maximum_input_tokens,
                    reserved_output_tokens=recommended_generation_output_tokens(
                        min(10, len(eligible))
                    ),
                    context_window=context_window,
                )
                history = list(request.get("context_history") or [])
                history.append(
                    {
                        "context_hash": call.context_hash,
                        "provider_model_id": str(call.generator_provider_model_id),
                        "model": call.model,
                    }
                )
                request["context_history"] = history[-20:]
                call.generator_provider_model_id = provider_model.id
                call.generator_provider_credential_id = credential.id
                call.provider = credential.provider
                call.model = provider_model.model
                call.context_hash = pack.context_hash
                call.context_payload = _context_with_tool_contract(
                    pack.payload,
                    tool_catalog,
                )
                call.context_stats = {
                    **pack.budget,
                    "context_window": context_window,
                    "tool_catalog": {
                        "status": tool_catalog["status"],
                        "source": tool_catalog["source"],
                        "tool_count": len(tool_catalog["allowed_names"]),
                        "immutable": tool_catalog["immutable"],
                    },
                }

            batch_ids = {slot.authoring_batch_id for slot in eligible}
            batches = list(
                (
                    await session.scalars(
                        select(EvaluationAuthoringBatchModel)
                        .where(EvaluationAuthoringBatchModel.authoring_call_id == call.id)
                        .order_by(EvaluationAuthoringBatchModel.batch_index)
                    )
                ).all()
            )
            for slot in eligible:
                slot.status = "planned"
                slot.failure_category = None
                slot.recommended_action = None
            for batch in batches:
                if batch.id not in batch_ids:
                    continue
                batch.status = "pending"
                batch.error = None
                batch.started_at = None
                batch.completed_at = None
            call.status = "queued"
            call.error = None
            call.completed_at = None
            call.cancel_requested_at = None
            call.lease_owner = None
            call.lease_expires_at = None
            request["last_resume_strategy"] = strategy
            request["resume_count"] = int(request.get("resume_count") or 0) + 1
            call.coverage_request = request
            return await self._payload(session, call, batches=batches)

    async def retry_authoring_call(
        self,
        project_id: UUID,
        call_id: UUID,
    ) -> dict[str, Any]:
        return await self.resume_authoring_call(
            project_id=project_id,
            call_id=call_id,
        )

    async def _payload(
        self,
        session,
        call: EvaluationAuthoringCallModel,
        *,
        batches: list[EvaluationAuthoringBatchModel] | None = None,
    ) -> dict[str, Any]:
        data = await super()._payload(session, call, batches=batches)
        slots = list(
            (
                await session.scalars(
                    select(EvaluationAuthoringCaseSlotModel)
                    .where(EvaluationAuthoringCaseSlotModel.authoring_call_id == call.id)
                    .order_by(EvaluationAuthoringCaseSlotModel.position)
                )
            ).all()
        )
        attempts = list(
            (
                await session.scalars(
                    select(EvaluationAuthoringAttemptModel)
                    .where(EvaluationAuthoringAttemptModel.authoring_call_id == call.id)
                    .order_by(EvaluationAuthoringAttemptModel.created_at)
                )
            ).all()
        )
        status_counts = Counter(slot.status for slot in slots)
        ready = status_counts.get("ready", 0)
        attention = status_counts.get("needs_attention", 0) + status_counts.get(
            "paused", 0
        )
        active = call.status in {
            "queued",
            "running",
            "partial",
            "repairing",
            "cancel_requested",
        }
        has_usage = call.input_tokens is not None or call.output_tokens is not None
        if active and not has_usage:
            usage_status = "pending"
        elif active:
            usage_status = "partial"
        elif has_usage:
            usage_status = "available"
        else:
            usage_status = "not_reported"

        phase = {
            "queued": "preparing_use_cases",
            "running": "generating_use_cases",
            "partial": "generating_remaining_use_cases",
            "repairing": "repairing_use_cases",
            "partially_ready": "use_cases_need_attention",
            "paused_requires_action": "paused_requires_action",
            "completed": "ready_for_review",
            "failed": "generation_failed",
            "failed_internal": "platform_failure",
            "cancel_requested": "cancelling",
            "cancelled": "cancelled",
        }.get(call.status, call.status)

        data.update(
            {
                "phase": phase,
                "ready_case_count": ready,
                "attention_case_count": attention,
                "pending_case_count": max(0, len(slots) - ready - attention),
                "case_progress_percent": (
                    round(ready / len(slots) * 100, 1) if slots else 0
                ),
                "usage_status": usage_status,
                "tool_catalog": (call.context_payload or {}).get("tool_catalog"),
                "case_slots": [
                    {
                        "id": str(slot.id),
                        "position": slot.position,
                        "coverage_category": slot.coverage_category,
                        "status": slot.status,
                        "name": slot.name,
                        "generated_case": slot.generated_case,
                        "validation": slot.validation_result,
                        "failure_category": slot.failure_category,
                        "recommended_action": slot.recommended_action,
                        "source_attempt_id": (
                            str(slot.source_attempt_id)
                            if slot.source_attempt_id
                            else None
                        ),
                    }
                    for slot in slots
                ],
                "attempts": [
                    {
                        "id": str(attempt.id),
                        "batch_id": (
                            str(attempt.authoring_batch_id)
                            if attempt.authoring_batch_id
                            else None
                        ),
                        "provider_model_id": str(attempt.provider_model_id),
                        "provider": attempt.provider,
                        "model": attempt.model,
                        "status": attempt.status,
                        "requested_slot_ids": attempt.requested_slot_ids,
                        "input_tokens": attempt.input_tokens,
                        "output_tokens": attempt.output_tokens,
                        "cost_usd": (
                            float(attempt.cost_usd)
                            if attempt.cost_usd is not None
                            else None
                        ),
                        "latency_ms": attempt.latency_ms,
                        "error_category": attempt.error_category,
                        "error_detail": attempt.error_detail,
                        "started_at": attempt.started_at,
                        "completed_at": attempt.completed_at,
                    }
                    for attempt in attempts
                ],
            }
        )
        data["progress_percent"] = data["case_progress_percent"]
        return data


__all__ = ["ResumableEvaluationSuiteAuthoringService"]
