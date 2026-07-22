from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from sqlalchemy import select

from modules.evaluation.application.resumable_authoring import (
    ResumableEvaluationSuiteAuthoringService,
    _context_with_tool_contract,
    _coverage_labels,
)
from modules.evaluation.application.tool_catalog import build_target_tool_catalog
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
    """Adds legacy backfill and explicit target-bound Tool validation."""

    async def _ensure_tool_catalog(
        self,
        session,
        call: EvaluationAuthoringCallModel,
    ) -> None:
        context = dict(call.context_payload or {})
        if isinstance(context.get("tool_catalog"), dict):
            return
        resolved = await self._target_resolver.resolve(
            session,
            project_id=call.project_id,
            target_type=call.target_type,
            source_type=call.target_source_type,
            entity_id=call.target_entity_id,
            version_id=call.target_version_id,
        )
        catalog = await build_target_tool_catalog(
            session,
            target=resolved,
            project_id=call.project_id,
        )
        call.context_payload = _context_with_tool_contract(context, catalog)
        stats = dict(call.context_stats or {})
        stats["tool_catalog"] = {
            "status": catalog["status"],
            "source": catalog["source"],
            "tool_count": len(catalog["allowed_names"]),
            "immutable": catalog["immutable"],
            "legacy_backfill": True,
        }
        call.context_stats = stats

    async def _ensure_case_slots(
        self,
        session,
        call: EvaluationAuthoringCallModel,
        batches: list[EvaluationAuthoringBatchModel],
    ) -> None:
        await self._ensure_tool_catalog(session, call)
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

    async def validate_draft(
        self,
        payload: dict[str, Any],
        *,
        project_id: UUID | None = None,
        reference_target: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        validation = await super().validate_draft(
            payload,
            project_id=project_id,
            reference_target=reference_target,
        )
        if reference_target is None or project_id is None:
            return validation

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
            catalog = await build_target_tool_catalog(
                session,
                target=resolved,
                project_id=project_id,
            )

        allowed = {
            str(name).casefold(): str(name)
            for name in catalog.get("allowed_names", [])
        }
        errors = list(validation.get("errors") or [])
        existing = {
            (str(issue.get("path") or ""), str(issue.get("message") or ""))
            for issue in errors
            if isinstance(issue, dict)
        }
        for index, case in enumerate(validation.get("cases") or []):
            contract = case.get("expected_contract") if isinstance(case, dict) else None
            tools = contract.get("tools") if isinstance(contract, dict) else None
            if not isinstance(tools, dict):
                continue
            for field in ("required", "forbidden"):
                values = tools.get(field)
                if not isinstance(values, list):
                    continue
                for value in values:
                    name = str(value).strip()
                    if not name or name.casefold() in allowed:
                        continue
                    path = f"cases[{index}].expected_contract.tools.{field}"
                    message = (
                        f"Tool '{name}' is not available in the selected snapshot."
                    )
                    if (path, message) not in existing:
                        errors.append(
                            {
                                "path": path,
                                "code": "unknown_tool",
                                "tool_name": name,
                                "message": message,
                            }
                        )
                        existing.add((path, message))

        reference = dict(validation.get("reference") or {})
        reference["tool_catalog"] = {
            "status": catalog.get("status"),
            "source": catalog.get("source"),
            "allowed_names": catalog.get("allowed_names", []),
            "immutable": catalog.get("immutable", False),
        }
        return {
            **validation,
            "valid": not errors,
            "errors": errors,
            "reference": reference,
        }

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
