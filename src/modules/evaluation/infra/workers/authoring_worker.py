from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from modules.evaluation.application.metering import record_evaluation_model_usage
from modules.evaluation.application.suite_authoring import _validate_tool_references
from modules.evaluation.domain.authoring_contract import generation_failure_metadata
from modules.evaluation.domain.contracts import validate_suite_draft
from modules.evaluation.infra.database.models import (
    EvaluationAuthoringBatchModel,
    EvaluationAuthoringCallModel,
)
from modules.evaluation.infra.generator import SuiteGeneratorGateway
from shared.infra.config import Settings


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _signature(case: dict[str, Any]) -> str:
    payload = case.get("input_payload") if isinstance(case.get("input_payload"), dict) else {}
    message = (
        case.get("message")
        or payload.get("message")
        or payload.get("input")
        or payload.get("prompt")
        or ""
    )
    return " ".join(str(message).lower().split())


def _failure_summary(validation: dict[str, Any], fallback: str | None) -> str:
    failure = validation.get("failure") if isinstance(validation.get("failure"), dict) else {}
    category = str(failure.get("category") or "generation_failed")
    errors = [
        str(item.get("message") or "invalid batch")
        for item in validation.get("errors", [])[:3]
        if isinstance(item, dict)
    ]
    detail = "; ".join(errors) or str(fallback or "Generator returned no valid cases")
    return f"{category}: {detail}"[:2000]


class EvaluationAuthoringWorker:
    def __init__(
        self,
        session_factory: async_sessionmaker,
        *,
        settings: Settings | None = None,
        worker_id: str | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._generator = SuiteGeneratorGateway(settings)
        self._worker_id = worker_id or f"evaluation-authoring-worker:{uuid4()}"

    async def run(self) -> None:
        claimed = await self._claim()
        if claimed is None:
            return
        call_id, batch_id = claimed
        try:
            await self._process(call_id, batch_id)
        except Exception as exc:
            await self._fail_batch(call_id, batch_id, f"{type(exc).__name__}: {exc}")

    async def _claim(self) -> tuple[UUID, UUID] | None:
        async with self._session_factory() as session, session.begin():
            now = _now()
            call = await session.scalar(
                select(EvaluationAuthoringCallModel)
                .where(
                    EvaluationAuthoringCallModel.status.in_(
                        {"queued", "running", "partial", "cancel_requested"}
                    ),
                    EvaluationAuthoringCallModel.lease_expires_at.is_(None)
                    | (EvaluationAuthoringCallModel.lease_expires_at < now),
                )
                .order_by(EvaluationAuthoringCallModel.created_at)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if call is None:
                return None
            if call.cancel_requested_at is not None or call.status == "cancel_requested":
                await self._cancel_locked(session, call)
                return None
            batch = await session.scalar(
                select(EvaluationAuthoringBatchModel)
                .where(
                    EvaluationAuthoringBatchModel.authoring_call_id == call.id,
                    EvaluationAuthoringBatchModel.status == "pending",
                )
                .order_by(EvaluationAuthoringBatchModel.batch_index)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if batch is None:
                await self._finalize_locked(session, call)
                return None
            call.status = "running"
            call.lease_owner = self._worker_id
            call.lease_expires_at = now + timedelta(minutes=10)
            batch.status = "running"
            batch.attempt = int(batch.attempt or 0) + 1
            batch.started_at = now
            batch.error = None
            return call.id, batch.id

    async def _process(self, call_id: UUID, batch_id: UUID) -> None:
        should_cancel = False
        previous_validation: dict[str, Any] | None = None
        async with self._session_factory() as session:
            call = await session.get(EvaluationAuthoringCallModel, call_id)
            batch = await session.get(EvaluationAuthoringBatchModel, batch_id)
            if call is None or batch is None:
                return
            should_cancel = call.cancel_requested_at is not None
            if not should_cancel:
                completed = list(
                    (
                        await session.scalars(
                            select(EvaluationAuthoringBatchModel)
                            .where(
                                EvaluationAuthoringBatchModel.authoring_call_id == call.id,
                                EvaluationAuthoringBatchModel.status == "completed",
                            )
                            .order_by(EvaluationAuthoringBatchModel.batch_index)
                        )
                    ).all()
                )
                prior_cases = [
                    case
                    for item in completed
                    for case in ((item.generated_payload or {}).get("cases") or [])
                    if isinstance(case, dict)
                ]
                prior_signatures = {
                    _signature(case) for case in prior_cases if _signature(case)
                }
                stored_context = dict(call.context_payload or {})
                context_payload = {
                    **stored_context,
                    "already_generated_case_signatures": [
                        {"name": case.get("name"), "message": _signature(case)[:500]}
                        for case in prior_cases[-50:]
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
                project_id = call.project_id
                provider_model_id = call.generator_provider_model_id
                objective = call.objective
                requested_case_count = batch.requested_case_count
                coverage_request = dict(batch.coverage_request or {})
                previous_validation = (
                    dict(batch.validation_result)
                    if isinstance(batch.validation_result, dict)
                    else None
                )
                repair_context = None
                if previous_validation:
                    repair_context = {
                        "attempt": batch.attempt,
                        "previous_errors": previous_validation.get("errors", [])[:20],
                        "previous_failure": previous_validation.get("failure"),
                        "previous_valid_cases": (batch.generated_payload or {}).get("cases", []),
                    }
                result = await self._generator.generate(
                    session,
                    project_id=project_id,
                    provider_model_id=provider_model_id,
                    context_pack=context_payload,
                    objective=objective,
                    case_count=requested_case_count,
                    coverage=coverage_request,
                    error_case_ratio=float(request.get("error_case_ratio") or 0),
                    language=str(request.get("language") or "pt-BR"),
                    maximum_cost_usd=remaining_cost,
                    repair_context=repair_context,
                )

        if should_cancel:
            await self._cancel_by_id(call_id)
            return

        payload = result.payload or {}
        validation = (
            _validate_tool_references(
                result.validation or validate_suite_draft(payload),
                context_pack=stored_context,
            )
            if result.payload
            else {
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
                "returned_case_count": 0,
                "valid_case_count": 0,
                "invalid_case_count": 1,
                "cases": [],
            }
        )
        returned_cases = validation.get("cases") or []
        duplicate_signatures = [
            value
            for value in (
                _signature(case) for case in returned_cases if isinstance(case, dict)
            )
            if value and value in prior_signatures
        ]
        if duplicate_signatures:
            validation = {
                **validation,
                "valid": False,
                "errors": [
                    *validation.get("errors", []),
                    {
                        "path": "cases",
                        "code": "duplicate_across_batches",
                        "message": (
                            "The batch repeated one or more questions generated by "
                            "previous batches."
                        ),
                    },
                ],
            }
        if validation.get("case_count") != requested_case_count:
            validation = {
                **validation,
                "valid": False,
                "errors": [
                    *validation.get("errors", []),
                    {
                        "path": "cases",
                        "code": "batch_case_count_mismatch",
                        "message": (
                            f"Batch returned {validation.get('case_count', 0)} of "
                            f"{requested_case_count} requested cases."
                        ),
                    },
                ],
            }

        failure = generation_failure_metadata(result.error, validation)
        if result.failure_category and not validation.get("errors"):
            failure = {
                "category": result.failure_category,
                "retryable": result.retryable,
                "recommended_action": result.recommended_action,
            }
        validation = {
            **validation,
            "returned_case_count": int(
                validation.get("returned_case_count")
                or (len(payload.get("cases") or []) if isinstance(payload.get("cases"), list) else 0)
            ),
            "valid_case_count": int(validation.get("case_count") or 0),
            "invalid_case_count": len(validation.get("errors", [])),
            "failure": failure if not validation.get("valid") else None,
            "normalization_warnings": list(result.normalization_warnings),
            "attempts": [
                *(
                    previous_validation.get("attempts", [])
                    if isinstance(previous_validation, dict)
                    and isinstance(previous_validation.get("attempts"), list)
                    else []
                ),
                {
                    "attempt": int(getattr(result, "attempt", 0) or 0),
                    "worker_attempt": None,
                    "returned_case_count": int(
                        validation.get("returned_case_count") or 0
                    ),
                    "valid_case_count": int(validation.get("case_count") or 0),
                    "invalid_case_count": len(validation.get("errors", [])),
                    "input_tokens": result.input_tokens,
                    "output_tokens": result.output_tokens,
                    "cost_usd": result.cost_usd,
                    "latency_ms": result.latency_ms,
                    "completed_at": result.completed_at.isoformat(),
                },
            ],
        }

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

            attempts = list(validation.get("attempts") or [])
            if attempts:
                attempts[-1]["worker_attempt"] = int(batch.attempt or 0)
                validation["attempts"] = attempts
            batch.input_tokens = int(batch.input_tokens or 0) + int(result.input_tokens or 0)
            batch.output_tokens = int(batch.output_tokens or 0) + int(result.output_tokens or 0)
            accumulated_cost = float(batch.cost_usd or 0) + float(result.cost_usd or 0)
            batch.cost_usd = accumulated_cost or None
            batch.pricing_snapshot = result.pricing_snapshot
            batch.validation_result = validation
            batch.completed_at = result.completed_at
            batch.generated_payload = (
                {
                    "suite": (
                        payload.get("suite")
                        if isinstance(payload.get("suite"), dict)
                        else {}
                    ),
                    "coverage": batch.coverage_request,
                    "cases": validation.get("cases") or [],
                }
                if result.payload
                else None
            )

            if call.cancel_requested_at is not None:
                await self._record_batch_usage(session, call, batch, result)
                await self._cancel_locked(session, call)
                return

            terminal = False
            if result.payload and validation.get("valid"):
                batch.status = "completed"
                batch.error = None
                terminal = True
            else:
                batch.error = _failure_summary(validation, result.error)
                can_retry = bool(failure.get("retryable")) and int(batch.attempt or 0) < 2
                if can_retry:
                    batch.status = "pending"
                    batch.completed_at = None
                else:
                    batch.status = "failed"
                    terminal = True

            if terminal:
                await self._record_batch_usage(session, call, batch, result)

            call.lease_owner = None
            call.lease_expires_at = None
            await self._refresh_call_locked(session, call)

    async def _record_batch_usage(self, session, call, batch, result) -> None:
        await record_evaluation_model_usage(
            session,
            source_id=batch.id,
            project_id=call.project_id,
            usage_subtype="suite_authoring",
            provider=result.provider,
            model=result.model,
            provider_model_id=result.provider_model_id,
            input_tokens=batch.input_tokens,
            output_tokens=batch.output_tokens,
            cost_usd=float(batch.cost_usd) if batch.cost_usd is not None else None,
            pricing_snapshot=batch.pricing_snapshot,
            data={
                "authoring_call_id": str(call.id),
                "authoring_batch_id": str(batch.id),
                "batch_index": batch.batch_index,
                "batch_status": batch.status,
                "attempts": batch.attempt,
                "failure": (
                    batch.validation_result.get("failure")
                    if isinstance(batch.validation_result, dict)
                    else None
                ),
            },
        )

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
        completed = [item for item in batches if item.status == "completed"]
        failed = [item for item in batches if item.status == "failed"]
        pending = [item for item in batches if item.status in {"pending", "running"}]
        call.completed_batch_count = len(completed)
        call.input_tokens = sum(int(item.input_tokens or 0) for item in batches) or None
        call.output_tokens = sum(int(item.output_tokens or 0) for item in batches) or None
        call.cost_usd = sum(float(item.cost_usd or 0) for item in batches) or None
        call.pricing_snapshot = next(
            (item.pricing_snapshot for item in reversed(batches) if item.pricing_snapshot),
            None,
        )
        if len(completed) == call.total_batch_count:
            await self._complete_locked(call, batches)
        elif pending:
            call.status = "partial" if completed or failed else "queued"
            call.error = (
                f"{len(failed)} batch(es) require attention while remaining batches continue"
                if failed
                else None
            )
            call.completed_at = None
        elif failed:
            call.status = "failed"
            call.error = f"{len(failed)} authoring batch(es) failed"
            call.completed_at = _now()
        else:
            call.status = "queued"
            call.completed_at = None

    async def _complete_locked(
        self,
        call: EvaluationAuthoringCallModel,
        batches: list[EvaluationAuthoringBatchModel],
    ) -> None:
        cases = [
            case
            for batch in batches
            for case in ((batch.generated_payload or {}).get("cases") or [])
            if isinstance(case, dict)
        ]
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
                "suggested_name": (
                    first_suite.get("suggested_name") or "Generated Evaluator Suite"
                ),
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
        if (
            validation.get("valid")
            and validation.get("case_count") == call.requested_case_count
        ):
            call.status = "completed"
            call.generated_payload = {
                **draft,
                "cases": validation.get("cases") or [],
            }
            call.validation_result = validation
            call.error = None
            call.completed_at = _now()
        else:
            call.status = "failed"
            call.validation_result = validation
            call.error = "Generated batches did not produce a valid complete Suite draft"
            call.completed_at = _now()

    async def _finalize_locked(self, session, call: EvaluationAuthoringCallModel) -> None:
        await self._refresh_call_locked(session, call)
        call.lease_owner = None
        call.lease_expires_at = None

    async def _cancel_by_id(self, call_id: UUID) -> None:
        async with self._session_factory() as session, session.begin():
            call = await session.get(
                EvaluationAuthoringCallModel,
                call_id,
                with_for_update=True,
            )
            if call is not None:
                await self._cancel_locked(session, call)

    async def _cancel_locked(self, session, call: EvaluationAuthoringCallModel) -> None:
        batches = list(
            (
                await session.scalars(
                    select(EvaluationAuthoringBatchModel).where(
                        EvaluationAuthoringBatchModel.authoring_call_id == call.id,
                        EvaluationAuthoringBatchModel.status.in_({"pending", "running"}),
                    )
                )
            ).all()
        )
        for batch in batches:
            batch.status = "cancelled"
            batch.error = "Authoring cancelled by user"
            batch.completed_at = _now()
        call.status = "cancelled"
        call.error = "Authoring cancelled by user"
        call.completed_at = _now()
        call.lease_owner = None
        call.lease_expires_at = None

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
                batch.validation_result = {
                    "valid": False,
                    "errors": [
                        {
                            "path": "worker",
                            "code": "worker_processing_error",
                            "message": detail[:500],
                        }
                    ],
                    "warnings": [],
                    "coverage": {},
                    "case_count": 0,
                    "cases": [],
                    "failure": {
                        "category": "worker_processing_error",
                        "retryable": retryable,
                        "recommended_action": "retry_provider_call" if retryable else "contact_support",
                    },
                }
                batch.completed_at = None if retryable else _now()
            if call is not None:
                call.lease_owner = None
                call.lease_expires_at = None
                await self._refresh_call_locked(session, call)


__all__ = ["EvaluationAuthoringWorker"]
