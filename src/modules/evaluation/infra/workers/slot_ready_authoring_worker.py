from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from modules.evaluation.infra.database.authoring_models import (
    EvaluationAuthoringCaseSlotModel,
)
from modules.evaluation.infra.database.models import (
    EvaluationAuthoringBatchModel,
    EvaluationAuthoringCallModel,
)
from modules.evaluation.infra.workers.resumable_authoring_worker import (
    ResumableEvaluationAuthoringWorker,
)


class SlotReadyEvaluationAuthoringWorker(ResumableEvaluationAuthoringWorker):
    """Do not call a provider until the case plan is committed."""

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


__all__ = ["SlotReadyEvaluationAuthoringWorker"]
