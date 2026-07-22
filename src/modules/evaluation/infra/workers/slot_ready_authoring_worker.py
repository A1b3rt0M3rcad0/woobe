from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select

from modules.evaluation.application.metering import record_evaluation_model_usage
from modules.evaluation.infra.database.authoring_models import (
    EvaluationAuthoringAttemptModel,
    EvaluationAuthoringCaseSlotModel,
)
from modules.evaluation.infra.database.models import (
    EvaluationAuthoringBatchModel,
    EvaluationAuthoringCallModel,
)
from modules.evaluation.infra.workers.authoring_worker import _signature
from modules.evaluation.infra.workers.resumable_authoring_worker import (
    ResumableEvaluationAuthoringWorker,
    _provider_action_failure,
)


class SlotReadyEvaluationAuthoringWorker(ResumableEvaluationAuthoringWorker):
    """Require a committed case plan and meter each provider attempt."""

    async def _claim(self) -> tuple[UUID, UUID] | None:
        claimed = await super()._claim()
        if claimed is None:
            return None
        call_id, batch_id = claimed
        async with self._session_factory() as session:
            slot_id = await session.scalar(
                select(EvaluationAuthoringCaseSlotModel.id)
                .where(
                    EvaluationAuthoringCaseSlotModel.authoring_batch_id == batch_id
                )
                .limit(1)
            )
        if slot_id is not None:
            return claimed

        async with self._session_factory() as session, session.begin():
            call = await session.get(
                EvaluationAuthoringCallModel,
                call_id,
                with_for_update=True,
            )
            batch = await session.get(
                EvaluationAuthoringBatchModel,
                batch_id,
                with_for_update=True,
            )
            if batch is not None and batch.status == "running":
                batch.status = "pending"
                batch.attempt = max(0, int(batch.attempt or 0) - 1)
                batch.started_at = None
            if call is not None:
                call.status = "queued"
                call.lease_owner = None
                call.lease_expires_at = None
        return None

    async def _record_batch_usage(self, session, call, batch, result) -> None:
        attempt = await session.scalar(
            select(EvaluationAuthoringAttemptModel)
            .where(EvaluationAuthoringAttemptModel.authoring_batch_id == batch.id)
            .order_by(EvaluationAuthoringAttemptModel.created_at.desc())
            .limit(1)
        )
        if attempt is None:
            await super()._record_batch_usage(session, call, batch, result)
            return
        await record_evaluation_model_usage(
            session,
            source_id=attempt.id,
            project_id=call.project_id,
            usage_subtype="suite_authoring",
            provider=attempt.provider,
            model=attempt.model,
            provider_model_id=attempt.provider_model_id,
            input_tokens=attempt.input_tokens,
            output_tokens=attempt.output_tokens,
            cost_usd=(
                float(attempt.cost_usd)
                if attempt.cost_usd is not None
                else None
            ),
            pricing_snapshot=attempt.pricing_snapshot,
            data={
                "authoring_call_id": str(call.id),
                "authoring_batch_id": str(batch.id),
                "authoring_attempt_id": str(attempt.id),
                "batch_index": batch.batch_index,
                "batch_status": batch.status,
                "requested_slot_ids": attempt.requested_slot_ids,
                "error_category": attempt.error_category,
            },
        )

    async def _complete_locked(self, session, call, slots) -> None:
        seen: dict[str, EvaluationAuthoringCaseSlotModel] = {}
        duplicates: list[EvaluationAuthoringCaseSlotModel] = []
        for slot in sorted(slots, key=lambda item: item.position):
            case = slot.generated_case
            if not isinstance(case, dict):
                continue
            signature = _signature(case)
            if not signature:
                continue
            if signature in seen:
                duplicates.append(slot)
            else:
                seen[signature] = slot
        if duplicates:
            for slot in duplicates:
                slot.status = "needs_attention"
                slot.failure_category = "duplicate_cases"
                slot.recommended_action = "repair_duplicate_cases"
                validation = dict(slot.validation_result or {})
                slot.validation_result = {
                    **validation,
                    "valid": False,
                    "errors": [
                        *list(validation.get("errors") or []),
                        {
                            "path": f"cases[{slot.position - 1}]",
                            "code": "duplicate_across_attempts",
                            "message": (
                                "This Use Case duplicates a question already preserved "
                                "by the authoring call."
                            ),
                        },
                    ],
                }
            call.status = "partially_ready"
            call.error = f"{len(duplicates)} duplicated Use Case(s) require repair"
            call.completed_at = datetime.now(timezone.utc)
            return
        await super()._complete_locked(session, call, slots)

    async def _fail_batch(self, call_id: UUID, batch_id: UUID, detail: str) -> None:
        action = _provider_action_failure(detail)
        if action is None:
            await super()._fail_batch(call_id, batch_id, detail)
            return

        async with self._session_factory() as session, session.begin():
            call = await session.get(
                EvaluationAuthoringCallModel,
                call_id,
                with_for_update=True,
            )
            batch = await session.get(
                EvaluationAuthoringBatchModel,
                batch_id,
                with_for_update=True,
            )
            if call is None or batch is None:
                return
            batch.status = "paused"
            batch.error = detail[:2000]
            batch.completed_at = datetime.now(timezone.utc)
            slots = list(
                (
                    await session.scalars(
                        select(EvaluationAuthoringCaseSlotModel).where(
                            EvaluationAuthoringCaseSlotModel.authoring_batch_id
                            == batch.id,
                            EvaluationAuthoringCaseSlotModel.status != "ready",
                        )
                    )
                ).all()
            )
            for slot in slots:
                slot.status = "paused"
                slot.failure_category = str(action["category"])
                slot.recommended_action = str(action["recommended_action"])
                validation = dict(slot.validation_result or {})
                slot.validation_result = {
                    **validation,
                    "valid": False,
                    "errors": [
                        *list(validation.get("errors") or []),
                        {
                            "path": "provider",
                            "code": action["category"],
                            "message": detail[:500],
                        },
                    ],
                }
            call.lease_owner = None
            call.lease_expires_at = None
            await self._refresh_call_locked(session, call)


__all__ = ["SlotReadyEvaluationAuthoringWorker"]
