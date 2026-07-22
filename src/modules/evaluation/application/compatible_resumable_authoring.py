from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from sqlalchemy import select

from modules.evaluation.application.resumable_authoring import (
    ResumableEvaluationSuiteAuthoringService,
    _coverage_labels,
)
from modules.evaluation.infra.database.authoring_models import (
    EvaluationAuthoringCaseSlotModel,
)
from modules.evaluation.infra.database.models import (
    EvaluationAuthoringBatchModel,
    EvaluationAuthoringCallModel,
)
from shared.infra.errors import NotFoundError


def _issues_by_case(validation: dict[str, Any]) -> dict[int, list[dict[str, Any]]]:
    grouped: dict[int, list[dict[str, Any]]] = {}
    for issue in validation.get("errors", []):
        if not isinstance(issue, dict):
            continue
        match = re.search(r"cases\[(\d+)\]", str(issue.get("path") or ""))
        if match:
            grouped.setdefault(int(match.group(1)), []).append(issue)
    return grouped


class CompatibleResumableEvaluationSuiteAuthoringService(
    ResumableEvaluationSuiteAuthoringService
):
    """Lazily converts pre-0059 authoring calls into per-case slots."""

    async def _ensure_case_slots(
        self,
        session,
        call: EvaluationAuthoringCallModel,
        batches: list[EvaluationAuthoringBatchModel],
    ) -> None:
        exists = await session.scalar(
            select(EvaluationAuthoringCaseSlotModel.id)
            .where(EvaluationAuthoringCaseSlotModel.authoring_call_id == call.id)
            .limit(1)
        )
        if exists is not None:
            return

        position = 1
        slots: list[EvaluationAuthoringCaseSlotModel] = []
        for batch in batches:
            labels = _coverage_labels(
                dict(batch.coverage_request or {}),
                int(batch.requested_case_count),
            )
            cases = [
                item
                for item in ((batch.generated_payload or {}).get("cases") or [])
                if isinstance(item, dict)
            ]
            validation = (
                dict(batch.validation_result)
                if isinstance(batch.validation_result, dict)
                else {}
            )
            errors_by_case = _issues_by_case(validation)
            failure = (
                validation.get("failure")
                if isinstance(validation.get("failure"), dict)
                else {}
            )
            for local_index, category in enumerate(labels):
                case = cases[local_index] if local_index < len(cases) else None
                case_errors = errors_by_case.get(local_index, [])
                if batch.status == "completed" and case is not None and not case_errors:
                    status = "ready"
                elif batch.status == "cancelled":
                    status = "cancelled"
                elif batch.status == "paused":
                    status = "paused"
                elif batch.status in {"pending", "running"}:
                    status = "planned"
                else:
                    status = "needs_attention"
                slots.append(
                    EvaluationAuthoringCaseSlotModel(
                        authoring_call_id=call.id,
                        authoring_batch_id=batch.id,
                        project_id=call.project_id,
                        position=position,
                        coverage_category=category,
                        status=status,
                        name=(
                            str(case.get("name") or f"Use Case {position}")[:255]
                            if case is not None
                            else None
                        ),
                        generated_case=case,
                        validation_result={
                            "valid": status == "ready",
                            "errors": case_errors,
                            "warnings": validation.get("warnings", []),
                            "legacy_backfill": True,
                        },
                        failure_category=(
                            None if status == "ready" else failure.get("category")
                        ),
                        recommended_action=(
                            None
                            if status == "ready"
                            else failure.get("recommended_action")
                        ),
                    )
                )
                position += 1
        session.add_all(slots)
        await session.flush()

    async def get_authoring_call(
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
            await self._ensure_case_slots(session, call, batches)
            return await self._payload(session, call, batches=batches)

    async def resume_authoring_call(
        self,
        *,
        project_id: UUID,
        call_id: UUID,
        provider_model_id: UUID | None = None,
        strategy: str = "retry_failed_and_missing",
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
            await self._ensure_case_slots(session, call, batches)
        return await super().resume_authoring_call(
            project_id=project_id,
            call_id=call_id,
            provider_model_id=provider_model_id,
            strategy=strategy,
        )


__all__ = ["CompatibleResumableEvaluationSuiteAuthoringService"]
