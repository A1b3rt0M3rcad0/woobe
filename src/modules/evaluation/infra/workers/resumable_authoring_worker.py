from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select

from modules.evaluation.application.suite_authoring import _validate_tool_references
from modules.evaluation.application.tool_reference_repair import (
    grouped_unknown_tools,
    repair_generated_tool_references,
)
from modules.evaluation.domain.authoring_contract import generation_failure_metadata
from modules.evaluation.domain.contracts import validate_suite_draft
from modules.evaluation.infra.database.authoring_models import (
    EvaluationAuthoringAttemptModel,
    EvaluationAuthoringCaseSlotModel,
)
from modules.evaluation.infra.database.models import (
    EvaluationAuthoringBatchModel,
    EvaluationAuthoringCallModel,
)
from modules.evaluation.infra.workers.authoring_worker import (
    EvaluationAuthoringWorker,
    _signature,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _case_error_indexes(errors: list[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    result: dict[int, list[dict[str, Any]]] = {}
    for issue in errors:
        match = re.search(r"cases\[(\d+)\]", str(issue.get("path") or ""))
        if match:
            result.setdefault(int(match.group(1)), []).append(issue)
    return result


def _provider_action_failure(error: str | None) -> dict[str, Any] | None:
    lowered = str(error or "").lower()
    if any(
        token in lowered
        for token in (
            "insufficient_quota",
            "insufficient quota",
            "insufficient credits",
            "insufficient balance",
            "credit balance",
            "quota exhausted",
            "billing required",
            "payment required",
            "status code 402",
            "http 402",
        )
    ):
        return {
            "category": "provider_insufficient_balance",
            "retryable": False,
            "recommended_action": "restore_balance_or_change_model",
            "pausable": True,
        }
    if any(token in lowered for token in ("401", "403", "unauthorized", "credential")):
        return {
            "category": "credential_error",
            "retryable": False,
            "recommended_action": "change_model_or_credential",
            "pausable": True,
        }
    return None


class ResumableEvaluationAuthoringWorker(EvaluationAuthoringWorker):
    """Persist generated Test Cases independently and resume only missing slots."""

    async def _process(self, call_id: UUID, batch_id: UUID) -> None:
        async with self._session_factory() as session, session.begin():
            call = await session.get(EvaluationAuthoringCallModel, call_id)
            batch = await session.get(EvaluationAuthoringBatchModel, batch_id)
            if call is None or batch is None:
                return
            if call.cancel_requested_at is not None:
                await self._cancel_locked(session, call)
                return
            slots = list(
                (
                    await session.scalars(
                        select(EvaluationAuthoringCaseSlotModel)
                        .where(
                            EvaluationAuthoringCaseSlotModel.authoring_batch_id == batch.id
                        )
                        .order_by(EvaluationAuthoringCaseSlotModel.position)
                    )
                ).all()
            )
            pending_slots = [
                slot for slot in slots if slot.status not in {"ready", "cancelled"}
            ]
            if not pending_slots:
                batch.status = "completed"
                batch.completed_at = _now()
                await self._refresh_call_locked(session, call)
                return
            for slot in pending_slots:
                slot.status = "generating"

            all_ready = list(
                (
                    await session.scalars(
                        select(EvaluationAuthoringCaseSlotModel)
                        .where(
                            EvaluationAuthoringCaseSlotModel.authoring_call_id == call.id,
                            EvaluationAuthoringCaseSlotModel.status == "ready",
                        )
                        .order_by(EvaluationAuthoringCaseSlotModel.position)
                    )
                ).all()
            )
            prior_cases = [
                slot.generated_case
                for slot in all_ready
                if isinstance(slot.generated_case, dict)
            ]
            stored_context = dict(call.context_payload or {})
            context_payload = {
                **stored_context,
                "already_generated_case_signatures": [
                    {
                        "name": case.get("name"),
                        "message": _signature(case)[:500],
                    }
                    for case in prior_cases[-50:]
                ],
                "requested_use_cases": [
                    {
                        "slot_id": str(slot.id),
                        "position": slot.position,
                        "coverage_category": slot.coverage_category,
                    }
                    for slot in pending_slots
                ],
            }
            request = dict(call.coverage_request or {})
            maximum_cost = request.get("maximum_cost_usd")
            spent = float(call.cost_usd or 0)
            remaining_cost = (
                max(0.000001, float(maximum_cost) - spent)
                if maximum_cost is not None
                else None
            )
            coverage = dict(Counter(slot.coverage_category for slot in pending_slots))
            repair_context = {
                "attempt": batch.attempt,
                "previous_errors": [
                    issue
                    for slot in pending_slots
                    for issue in (
                        (slot.validation_result or {}).get("errors", [])
                        if isinstance(slot.validation_result, dict)
                        else []
                    )
                ][:30],
                "previous_cases": [
                    slot.generated_case
                    for slot in pending_slots
                    if isinstance(slot.generated_case, dict)
                ],
                "instruction": (
                    "Generate only the requested unresolved Use Cases. Preserve the "
                    "intent of previous cases and use only exact Tool names from "
                    "tool_catalog.allowed_names. Conversational actions are behavior, "
                    "not Tools."
                ),
            }
            attempt = EvaluationAuthoringAttemptModel(
                authoring_call_id=call.id,
                authoring_batch_id=batch.id,
                project_id=call.project_id,
                provider_model_id=call.generator_provider_model_id,
                provider_credential_id=call.generator_provider_credential_id,
                provider=call.provider,
                model=call.model,
                status="running",
                requested_slot_ids=[str(slot.id) for slot in pending_slots],
                started_at=_now(),
            )
            session.add(attempt)
            await session.flush()
            attempt_id = attempt.id
            provider_model_id = call.generator_provider_model_id
            project_id = call.project_id
            objective = call.objective
            error_case_ratio = float(request.get("error_case_ratio") or 0)
            language = str(request.get("language") or "pt-BR")

        async with self._session_factory() as session:
            result = await self._generator.generate(
                session,
                project_id=project_id,
                provider_model_id=provider_model_id,
                context_pack=context_payload,
                objective=objective,
                case_count=len(pending_slots),
                coverage=coverage,
                error_case_ratio=error_case_ratio,
                language=language,
                maximum_cost_usd=remaining_cost,
                repair_context=repair_context,
            )

        payload = result.payload or {}
        allowed_names = list(
            ((stored_context.get("tool_catalog") or {}).get("allowed_names") or [])
        )
        repair_warnings: list[dict[str, Any]] = []
        tool_errors: list[dict[str, Any]] = []
        if result.payload:
            payload, repair_warnings, tool_errors = repair_generated_tool_references(
                payload,
                allowed_names=allowed_names,
            )
            validation = _validate_tool_references(
                validate_suite_draft(payload),
                context_pack=stored_context,
            )
            existing = {
                (str(item.get("path")), str(item.get("message")))
                for item in validation.get("errors", [])
                if isinstance(item, dict)
            }
            validation = {
                **validation,
                "errors": [
                    *validation.get("errors", []),
                    *[
                        issue
                        for issue in tool_errors
                        if (str(issue.get("path")), str(issue.get("message")))
                        not in existing
                    ],
                ],
                "warnings": [
                    *repair_warnings,
                    *validation.get("warnings", []),
                ],
                "normalization_warnings": [
                    *list(result.normalization_warnings),
                    *repair_warnings,
                ],
            }
        else:
            validation = {
                "valid": False,
                "errors": [
                    {
                        "path": "generator",
                        "code": result.failure_category or "generation_failed",
                        "message": result.error or "Generator returned no payload",
                    }
                ],
                "warnings": [],
                "coverage": {},
                "case_count": 0,
                "cases": [],
            }

        provider_failure = _provider_action_failure(result.error)
        if tool_errors:
            failure = {
                "category": "tool_reference_mismatch",
                "retryable": True,
                "recommended_action": "repair_tool_references",
                "grouped_tool_errors": grouped_unknown_tools(tool_errors),
            }
        else:
            failure = provider_failure or generation_failure_metadata(
                result.error,
                validation,
            )
        errors = list(validation.get("errors", []))
        errors_by_index = _case_error_indexes(errors)
        generated_cases = list(validation.get("cases") or payload.get("cases") or [])

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
            attempt = await session.get(
                EvaluationAuthoringAttemptModel,
                attempt_id,
                with_for_update=True,
            )
            if call is None or batch is None or attempt is None:
                return
            slots = list(
                (
                    await session.scalars(
                        select(EvaluationAuthoringCaseSlotModel)
                        .where(
                            EvaluationAuthoringCaseSlotModel.id.in_(
                                [slot.id for slot in pending_slots]
                            )
                        )
                        .order_by(EvaluationAuthoringCaseSlotModel.position)
                    )
                ).all()
            )

            attempt.input_tokens = result.input_tokens
            attempt.output_tokens = result.output_tokens
            attempt.cost_usd = result.cost_usd
            attempt.pricing_snapshot = result.pricing_snapshot
            attempt.latency_ms = result.latency_ms
            attempt.error_category = failure.get("category")
            attempt.error_detail = result.error
            attempt.completed_at = result.completed_at

            pausable = bool(failure.get("pausable"))
            retryable = bool(failure.get("retryable"))
            for index, slot in enumerate(slots):
                case = generated_cases[index] if index < len(generated_cases) else None
                slot_errors = errors_by_index.get(index, [])
                slot.source_attempt_id = attempt.id
                if isinstance(case, dict):
                    slot.generated_case = case
                    slot.name = str(case.get("name") or f"Use Case {slot.position}")[:255]
                slot.validation_result = {
                    "valid": bool(case) and not slot_errors,
                    "errors": slot_errors,
                    "warnings": repair_warnings,
                }
                if isinstance(case, dict) and not slot_errors:
                    slot.status = "ready"
                    slot.failure_category = None
                    slot.recommended_action = None
                elif pausable:
                    slot.status = "paused"
                    slot.failure_category = str(failure.get("category") or "provider_action")
                    slot.recommended_action = failure.get("recommended_action")
                elif retryable and int(batch.attempt or 0) < 2:
                    slot.status = "planned"
                    slot.failure_category = str(failure.get("category") or "generation_failed")
                    slot.recommended_action = failure.get("recommended_action")
                else:
                    slot.status = "needs_attention"
                    slot.failure_category = str(failure.get("category") or "generation_failed")
                    slot.recommended_action = failure.get("recommended_action")

            batch.input_tokens = int(batch.input_tokens or 0) + int(result.input_tokens or 0)
            batch.output_tokens = int(batch.output_tokens or 0) + int(result.output_tokens or 0)
            accumulated_cost = float(batch.cost_usd or 0) + float(result.cost_usd or 0)
            batch.cost_usd = accumulated_cost or None
            batch.pricing_snapshot = result.pricing_snapshot
            batch.validation_result = {
                **validation,
                "failure": failure,
                "grouped_tool_errors": failure.get("grouped_tool_errors", []),
                "requested_slot_ids": [str(slot.id) for slot in slots],
            }

            all_batch_slots = list(
                (
                    await session.scalars(
                        select(EvaluationAuthoringCaseSlotModel)
                        .where(
                            EvaluationAuthoringCaseSlotModel.authoring_batch_id == batch.id
                        )
                        .order_by(EvaluationAuthoringCaseSlotModel.position)
                    )
                ).all()
            )
            ready_cases = [
                slot.generated_case
                for slot in all_batch_slots
                if slot.status == "ready" and isinstance(slot.generated_case, dict)
            ]
            batch.generated_payload = {
                "suite": payload.get("suite") if isinstance(payload.get("suite"), dict) else {},
                "coverage": batch.coverage_request,
                "cases": ready_cases,
            }
            if len(ready_cases) == len(all_batch_slots):
                batch.status = "completed"
                batch.error = None
                batch.completed_at = result.completed_at
                attempt.status = "completed"
                await self._record_batch_usage(session, call, batch, result)
            elif pausable:
                batch.status = "paused"
                batch.error = str(result.error or failure.get("category"))[:2000]
                batch.completed_at = result.completed_at
                attempt.status = "paused"
                await self._record_batch_usage(session, call, batch, result)
            elif retryable and int(batch.attempt or 0) < 2:
                batch.status = "pending"
                batch.error = str(result.error or failure.get("category"))[:2000]
                batch.completed_at = None
                attempt.status = "retry_scheduled"
            else:
                batch.status = "failed"
                batch.error = str(result.error or failure.get("category"))[:2000]
                batch.completed_at = result.completed_at
                attempt.status = "failed"
                await self._record_batch_usage(session, call, batch, result)

            call.lease_owner = None
            call.lease_expires_at = None
            await self._refresh_call_locked(session, call)

    async def _refresh_call_locked(
        self,
        session,
        call: EvaluationAuthoringCallModel,
    ) -> None:
        batches = list(
            (
                await session.scalars(
                    select(EvaluationAuthoringBatchModel)
                    .where(EvaluationAuthoringBatchModel.authoring_call_id == call.id)
                    .order_by(EvaluationAuthoringBatchModel.batch_index)
                )
            ).all()
        )
        slots = list(
            (
                await session.scalars(
                    select(EvaluationAuthoringCaseSlotModel)
                    .where(EvaluationAuthoringCaseSlotModel.authoring_call_id == call.id)
                    .order_by(EvaluationAuthoringCaseSlotModel.position)
                )
            ).all()
        )
        call.completed_batch_count = sum(1 for batch in batches if batch.status == "completed")
        call.input_tokens = sum(int(batch.input_tokens or 0) for batch in batches) or None
        call.output_tokens = sum(int(batch.output_tokens or 0) for batch in batches) or None
        call.cost_usd = sum(float(batch.cost_usd or 0) for batch in batches) or None
        call.pricing_snapshot = next(
            (batch.pricing_snapshot for batch in reversed(batches) if batch.pricing_snapshot),
            None,
        )
        ready = [slot for slot in slots if slot.status == "ready"]
        pending = [slot for slot in slots if slot.status in {"planned", "generating"}]
        paused = [slot for slot in slots if slot.status == "paused"]
        attention = [slot for slot in slots if slot.status == "needs_attention"]

        if slots and len(ready) == len(slots):
            await self._complete_locked(session, call, slots)
        elif pending:
            call.status = "partial" if ready else "queued"
            call.error = None
            call.completed_at = None
        elif paused:
            call.status = "paused_requires_action"
            call.error = (
                f"{len(paused)} Use Case(s) are paused until the provider balance, "
                "credential, or generator model is updated."
            )
            call.completed_at = None
        elif attention:
            call.status = "partially_ready" if ready else "failed"
            call.error = f"{len(attention)} Use Case(s) require attention"
            call.completed_at = _now()
        else:
            call.status = "failed_internal"
            call.error = "Evaluator Suite authoring has no resolvable Use Cases"
            call.completed_at = _now()

    async def _complete_locked(
        self,
        session,
        call: EvaluationAuthoringCallModel,
        slots: list[EvaluationAuthoringCaseSlotModel],
    ) -> None:
        cases = [
            slot.generated_case
            for slot in slots
            if slot.status == "ready" and isinstance(slot.generated_case, dict)
        ]
        batches = list(
            (
                await session.scalars(
                    select(EvaluationAuthoringBatchModel)
                    .where(EvaluationAuthoringBatchModel.authoring_call_id == call.id)
                    .order_by(EvaluationAuthoringBatchModel.batch_index)
                )
            ).all()
        )
        first_suite = next(
            (
                (batch.generated_payload or {}).get("suite")
                for batch in batches
                if isinstance((batch.generated_payload or {}).get("suite"), dict)
            ),
            {},
        )
        draft = {
            "schema_version": 1,
            "suite": {
                "suggested_name": first_suite.get("suggested_name")
                or "Generated Evaluator Suite",
                "description": first_suite.get("description") or "",
                "objective": call.objective,
            },
            "coverage": (call.coverage_request or {}).get("allocation") or {},
            "cases": cases,
        }
        validation = _validate_tool_references(
            validate_suite_draft(draft),
            context_pack=call.context_payload or {},
        )
        if validation.get("valid") and len(cases) == call.requested_case_count:
            call.status = "completed"
            call.generated_payload = {**draft, "cases": validation.get("cases") or []}
            call.validation_result = validation
            call.error = None
            call.completed_at = _now()
        else:
            call.status = "partially_ready" if cases else "failed"
            call.validation_result = validation
            call.error = "Generated Use Cases did not produce a valid complete Suite draft"
            call.completed_at = _now()

    async def _cancel_locked(self, session, call: EvaluationAuthoringCallModel) -> None:
        await super()._cancel_locked(session, call)
        slots = list(
            (
                await session.scalars(
                    select(EvaluationAuthoringCaseSlotModel).where(
                        EvaluationAuthoringCaseSlotModel.authoring_call_id == call.id,
                        EvaluationAuthoringCaseSlotModel.status.notin_({"ready", "cancelled"}),
                    )
                )
            ).all()
        )
        for slot in slots:
            slot.status = "cancelled"
            slot.failure_category = "cancelled"
            slot.recommended_action = None

    async def _fail_batch(self, call_id: UUID, batch_id: UUID, detail: str) -> None:
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
            if batch is not None:
                retryable = int(batch.attempt or 0) < 2
                batch.status = "pending" if retryable else "failed"
                batch.error = detail[:2000]
                batch.completed_at = None if retryable else _now()
                slots = list(
                    (
                        await session.scalars(
                            select(EvaluationAuthoringCaseSlotModel).where(
                                EvaluationAuthoringCaseSlotModel.authoring_batch_id == batch.id,
                                EvaluationAuthoringCaseSlotModel.status != "ready",
                            )
                        )
                    ).all()
                )
                for slot in slots:
                    slot.status = "planned" if retryable else "needs_attention"
                    slot.failure_category = "worker_processing_error"
                    slot.recommended_action = (
                        "retry_provider_call" if retryable else "contact_support"
                    )
            if call is not None:
                call.lease_owner = None
                call.lease_expires_at = None
                await self._refresh_call_locked(session, call)


__all__ = ["ResumableEvaluationAuthoringWorker"]
