from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from modules.evaluation.application.failure_taxonomy import (
    canonical_judge_failure_code,
)
from modules.evaluation.application.human_decision_service import _target_manifest
from modules.evaluation.infra.database.models import (
    EvaluationCheckResultModel,
    EvaluationDatasetVersionModel,
    EvaluationRunModel,
    EvaluationSuiteModel,
    EvaluationSuiteVersionModel,
    EvaluationTargetModel,
    EvaluationTestCaseModel,
    EvaluationTrialModel,
    EvaluatorModelCallModel,
)
from shared.infra.errors import NotFoundError

_DIAGNOSTICS_SCHEMA_VERSION = "evaluation-run-diagnostics-v1"
_EXPECTED_ADAPTIVE_GATEWAY = "adaptive-judge-v4"
_EXPECTED_REPAIR_GATEWAY = "resilient-judge-v1"
_MAX_STRING_LENGTH = 20_000
_MAX_COLLECTION_ITEMS = 2_000
_MAX_DEPTH = 14

_SENSITIVE_KEYS = {
    "authorization",
    "proxy_authorization",
    "api_key",
    "apikey",
    "access_token",
    "refresh_token",
    "client_secret",
    "encrypted_secret",
    "secret",
    "password",
    "cookie",
    "set_cookie",
    "x_api_key",
}
_SENSITIVE_HEADER_KEYS = {
    "authorization",
    "proxy-authorization",
    "x-api-key",
    "api-key",
    "cookie",
    "set-cookie",
}


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def _text_fingerprint(value: str | None) -> str | None:
    if not value:
        return None
    return sha256(value.encode("utf-8", errors="replace")).hexdigest()


def _payload_fingerprint(value: Any) -> str | None:
    if value is None:
        return None
    try:
        raw = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
    except (TypeError, ValueError):
        raw = str(value)
    return _text_fingerprint(raw)


def _redact_text(value: str) -> str:
    text = value
    text = re.sub(
        r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{8,}",
        "Bearer <redacted>",
        text,
    )
    text = re.sub(
        r"(?i)\b(sk|pk|rk)-[A-Za-z0-9_-]{8,}",
        r"\1-<redacted>",
        text,
    )
    text = re.sub(
        r"(?i)([?&](?:access_token|refresh_token|api_key|apikey|key|token)=)[^&\s]+",
        r"\1<redacted>",
        text,
    )
    text = re.sub(
        r"(?i)(\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret|password)\b\s*[:=]\s*)[^\s,;]+",
        r"\1<redacted>",
        text,
    )
    if len(text) > _MAX_STRING_LENGTH:
        omitted = len(text) - _MAX_STRING_LENGTH
        return f"{text[:_MAX_STRING_LENGTH]}\n… <{omitted} characters omitted>"
    return text


def _is_sensitive_key(key: str) -> bool:
    normalized = key.strip().lower().replace("-", "_")
    if normalized in _SENSITIVE_KEYS:
        return True
    if normalized.endswith("_secret") or normalized.endswith("_password"):
        return True
    if normalized.endswith("_token") and not normalized.endswith("_tokens"):
        return True
    return False


def _redact(value: Any, *, key: str | None = None, depth: int = 0) -> Any:
    if key is not None and _is_sensitive_key(key):
        return "<redacted>"
    if depth >= _MAX_DEPTH:
        return "<maximum depth reached>"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str):
        return _redact_text(value)
    if isinstance(value, dict):
        output: dict[str, Any] = {}
        for index, (raw_key, raw_value) in enumerate(value.items()):
            if index >= _MAX_COLLECTION_ITEMS:
                output["_truncated"] = (
                    f"{len(value) - _MAX_COLLECTION_ITEMS} mapping entries omitted"
                )
                break
            name = str(raw_key)
            if key and key.lower() == "headers" and name.lower() in _SENSITIVE_HEADER_KEYS:
                output[name] = "<redacted>"
            else:
                output[name] = _redact(raw_value, key=name, depth=depth + 1)
        return output
    if isinstance(value, (list, tuple, set)):
        values = list(value)
        output = [
            _redact(item, depth=depth + 1)
            for item in values[:_MAX_COLLECTION_ITEMS]
        ]
        if len(values) > _MAX_COLLECTION_ITEMS:
            output.append(
                f"<{len(values) - _MAX_COLLECTION_ITEMS} collection items omitted>"
            )
        return output
    return _redact_text(str(value))


def _diagnostics(call: EvaluatorModelCallModel | None) -> dict[str, Any]:
    if call is None or not isinstance(call.pricing_snapshot, dict):
        return {}
    value = call.pricing_snapshot.get("_evaluation_judge")
    return value if isinstance(value, dict) else {}


def _attempt_count(diagnostics: dict[str, Any]) -> int:
    primary = diagnostics.get("attempts")
    repair = diagnostics.get("repair_attempts")
    return len(primary if isinstance(primary, list) else []) + len(
        repair if isinstance(repair, list) else []
    )


def _error_signature(value: str | None) -> str:
    if not value:
        return "none"
    normalized = " ".join(value.split())
    normalized = re.sub(r"\b[0-9a-f]{8}-[0-9a-f-]{27,}\b", "<uuid>", normalized, flags=re.I)
    normalized = re.sub(r"\b\d{4,}\b", "<number>", normalized)
    return normalized[:600]


class EvaluationRunDiagnosticsService:
    """Build a deep, project-scoped and secret-redacted Evaluation log bundle."""

    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory

    async def get_run_diagnostics(
        self,
        *,
        project_id: UUID,
        run_id: UUID,
    ) -> dict[str, Any]:
        async with self._session_factory() as session:
            run = await session.get(EvaluationRunModel, run_id)
            if run is None or run.project_id != project_id:
                raise NotFoundError("Evaluation Run not found")

            suite_version = await session.get(
                EvaluationSuiteVersionModel,
                run.suite_version_id,
            )
            suite = (
                await session.get(EvaluationSuiteModel, suite_version.suite_id)
                if suite_version is not None
                else None
            )
            dataset_version = (
                await session.get(
                    EvaluationDatasetVersionModel,
                    suite_version.dataset_version_id,
                )
                if suite_version is not None
                else None
            )
            targets = list(
                (
                    await session.scalars(
                        select(EvaluationTargetModel)
                        .where(EvaluationTargetModel.evaluation_run_id == run.id)
                        .order_by(EvaluationTargetModel.created_at)
                    )
                ).all()
            )
            trials = list(
                (
                    await session.scalars(
                        select(EvaluationTrialModel)
                        .where(EvaluationTrialModel.evaluation_run_id == run.id)
                        .order_by(EvaluationTrialModel.execution_order)
                    )
                ).all()
            )
            trial_ids = [item.id for item in trials]
            case_ids = [item.test_case_id for item in trials]
            cases = {
                item.id: item
                for item in (
                    await session.scalars(
                        select(EvaluationTestCaseModel).where(
                            EvaluationTestCaseModel.id.in_(case_ids or [UUID(int=0)])
                        )
                    )
                ).all()
            }
            calls = list(
                (
                    await session.scalars(
                        select(EvaluatorModelCallModel)
                        .where(EvaluatorModelCallModel.evaluation_run_id == run.id)
                        .order_by(EvaluatorModelCallModel.created_at)
                    )
                ).all()
            )
            checks = list(
                (
                    await session.scalars(
                        select(EvaluationCheckResultModel)
                        .where(
                            EvaluationCheckResultModel.evaluation_trial_id.in_(
                                trial_ids or [UUID(int=0)]
                            )
                        )
                        .order_by(EvaluationCheckResultModel.created_at)
                    )
                ).all()
            )

        targets_by_id = {item.id: item for item in targets}
        calls_by_trial = {item.evaluation_trial_id: item for item in calls}
        checks_by_trial: dict[UUID, list[EvaluationCheckResultModel]] = {}
        for item in checks:
            checks_by_trial.setdefault(item.evaluation_trial_id, []).append(item)

        timeline: list[dict[str, Any]] = []

        def event(
            stage: str,
            at: datetime | None,
            message: str,
            *,
            status: str = "info",
            trial_id: UUID | None = None,
            details: dict[str, Any] | None = None,
        ) -> None:
            if at is None:
                return
            timeline.append(
                {
                    "at": at.isoformat(),
                    "stage": stage,
                    "status": status,
                    "message": message,
                    "trial_id": str(trial_id) if trial_id else None,
                    "details": _redact(details or {}),
                }
            )

        event("run_created", run.created_at, "Evaluation Run was created")
        event("run_started", run.started_at, "Evaluation worker started the Run")
        if run.cancel_requested_at:
            event(
                "cancel_requested",
                run.cancel_requested_at,
                "Cancellation was requested",
                status="warning",
            )
        event(
            "run_completed",
            run.completed_at,
            f"Evaluation Run reached {run.status}",
            status="error" if run.status == "failed" else "info",
            details={"failure_code": run.failure_code, "failure_detail": run.failure_detail},
        )

        failure_counter: Counter[str] = Counter()
        error_counter: Counter[str] = Counter()
        trial_logs: list[dict[str, Any]] = []
        runtime_completed_count = 0
        judge_started_count = 0
        conclusive_count = 0

        for trial in trials:
            target = targets_by_id.get(trial.evaluation_target_id)
            case = cases.get(trial.test_case_id)
            call = calls_by_trial.get(trial.id)
            diagnostics = _diagnostics(call)
            canonical = canonical_judge_failure_code(
                failure_code=trial.failure_code,
                failure_detail=trial.failure_detail,
                judge_status=call.status if call else None,
                judge_error=call.error if call else None,
            )
            if canonical:
                failure_counter[canonical] += 1
            error = call.error if call and call.error else trial.failure_detail
            if error:
                error_counter[_error_signature(error)] += 1

            runtime_completed = bool(
                trial.runtime_completed_at
                or (trial.metrics or {}).get("runtime_completed")
                or trial.output_payload is not None
            )
            runtime_completed_count += int(runtime_completed)
            judge_started_count += int(bool(trial.judge_started_at))
            conclusive_count += int(trial.score is not None and trial.passed is not None)

            event(
                "trial_started",
                trial.started_at,
                f"Trial {trial.execution_order} started",
                trial_id=trial.id,
                details={
                    "case": case.name if case else None,
                    "repetition": trial.repetition,
                    "target": target.display_version if target else None,
                    "attempt": trial.attempt,
                },
            )
            event(
                "runtime_completed",
                trial.runtime_completed_at,
                "Target runtime evidence was persisted",
                trial_id=trial.id,
                details={
                    "trace_id": trial.root_trace_id,
                    "agent_run_id": trial.agent_run_id,
                    "network_execution_id": trial.network_execution_id,
                    "output_fingerprint": _payload_fingerprint(trial.output_payload),
                },
            )
            event(
                "judge_started",
                trial.judge_started_at,
                "Judge processing started",
                trial_id=trial.id,
            )
            if call is not None:
                event(
                    "judge_call_started",
                    call.started_at,
                    f"Judge provider call started with {call.provider}/{call.model}",
                    trial_id=trial.id,
                    details={
                        "model_call_id": call.id,
                        "judge_config_hash": call.judge_config_hash,
                        "rubric_hash": call.rubric_hash,
                    },
                )
                event(
                    "judge_call_completed",
                    call.completed_at,
                    f"Judge provider call ended with {call.status}",
                    status="error" if call.status != "completed" else "info",
                    trial_id=trial.id,
                    details={
                        "model_call_id": call.id,
                        "input_tokens": call.input_tokens,
                        "output_tokens": call.output_tokens,
                        "cost_usd": call.cost_usd,
                        "latency_ms": call.latency_ms,
                        "error": call.error,
                        "diagnostic_attempts": _attempt_count(diagnostics),
                    },
                )
            event(
                "trial_completed",
                trial.completed_at,
                f"Trial ended as {trial.status}",
                status=(
                    "error"
                    if trial.failure_code or trial.status in {"failed", "inconclusive"}
                    else "info"
                ),
                trial_id=trial.id,
                details={
                    "failure_code": canonical or trial.failure_code,
                    "failure_detail": trial.failure_detail,
                    "score": trial.score,
                    "passed": trial.passed,
                },
            )

            trial_logs.append(
                {
                    "id": str(trial.id),
                    "execution_order": trial.execution_order,
                    "repetition": trial.repetition,
                    "pair_key": trial.pair_key,
                    "attempt": trial.attempt,
                    "status": trial.status,
                    "target": {
                        "id": str(target.id) if target else None,
                        "side": target.side if target else None,
                        "display_name": target.display_name if target else None,
                        "display_version": target.display_version if target else None,
                        "snapshot_hash": target.snapshot_hash if target else None,
                    },
                    "case": (
                        {
                            "id": str(case.id),
                            "position": case.position,
                            "name": case.name,
                            "case_type": case.case_type,
                            "input_payload": _redact(case.input_payload),
                            "initial_context": _redact(case.initial_context),
                            "expected_contract": _redact(case.expected_contract),
                        }
                        if case
                        else None
                    ),
                    "timestamps": {
                        "created_at": _iso(trial.created_at),
                        "started_at": _iso(trial.started_at),
                        "runtime_completed_at": _iso(trial.runtime_completed_at),
                        "judge_started_at": _iso(trial.judge_started_at),
                        "judge_completed_at": _iso(trial.judge_completed_at),
                        "completed_at": _iso(trial.completed_at),
                    },
                    "runtime": {
                        "completed": runtime_completed,
                        "trace_id": str(trial.root_trace_id) if trial.root_trace_id else None,
                        "agent_run_id": str(trial.agent_run_id) if trial.agent_run_id else None,
                        "network_execution_id": (
                            str(trial.network_execution_id)
                            if trial.network_execution_id
                            else None
                        ),
                        "output_fingerprint": _payload_fingerprint(trial.output_payload),
                        "output": _redact(trial.output_payload),
                        "metrics": _redact(trial.metrics),
                        "observed_outcome": _redact(trial.observed_outcome),
                    },
                    "judgment": {
                        "started": bool(trial.judge_started_at),
                        "completed": bool(trial.judge_completed_at),
                        "canonical_failure_code": canonical,
                        "failure_origin": trial.failure_origin,
                        "failure_stage": trial.failure_stage,
                        "failure_code": trial.failure_code,
                        "failure_detail": _redact(trial.failure_detail),
                        "score": trial.score,
                        "passed": trial.passed,
                        "model_call_id": str(call.id) if call else None,
                        "model_call_present": call is not None,
                        "diagnostics_present": bool(diagnostics),
                        "diagnostic_attempt_count": _attempt_count(diagnostics),
                        "gateway_version": diagnostics.get("gateway_version"),
                        "repair_gateway_version": diagnostics.get(
                            "repair_gateway_version"
                        ),
                        "final_response_mode": diagnostics.get("final_response_mode"),
                        "final_inference_profile": diagnostics.get(
                            "final_inference_profile"
                        ),
                        "final_error_code": diagnostics.get("final_error_code"),
                    },
                    "checks": [
                        {
                            "id": str(check.id),
                            "evaluator_key": check.evaluator_key,
                            "evaluator_type": check.evaluator_type,
                            "dimension": check.dimension,
                            "status": check.status,
                            "score": check.score,
                            "weight": check.weight,
                            "blocking": check.blocking,
                            "reason": _redact(check.reason),
                            "evidence": _redact(check.evidence),
                            "created_at": _iso(check.created_at),
                        }
                        for check in checks_by_trial.get(trial.id, [])
                    ],
                }
            )

        call_logs: list[dict[str, Any]] = []
        diagnostics_present = 0
        repair_markers = 0
        adaptive_markers = 0
        for call in calls:
            diagnostics = _diagnostics(call)
            diagnostics_present += int(bool(diagnostics))
            adaptive_markers += int(
                diagnostics.get("gateway_version") == _EXPECTED_ADAPTIVE_GATEWAY
            )
            repair_markers += int(
                diagnostics.get("repair_gateway_version") == _EXPECTED_REPAIR_GATEWAY
            )
            canonical = canonical_judge_failure_code(
                failure_code=None,
                failure_detail=None,
                judge_status=call.status,
                judge_error=call.error,
            )
            call_logs.append(
                {
                    "id": str(call.id),
                    "trial_id": str(call.evaluation_trial_id),
                    "status": call.status,
                    "provider_model_id": str(call.provider_model_id),
                    "provider": call.provider,
                    "model": call.model,
                    "judge_config_hash": call.judge_config_hash,
                    "rubric_hash": call.rubric_hash,
                    "input_tokens": call.input_tokens,
                    "output_tokens": call.output_tokens,
                    "cost_usd": float(call.cost_usd)
                    if call.cost_usd is not None
                    else None,
                    "cost_status": call.cost_status,
                    "cost_reason": _redact(call.cost_reason),
                    "latency_ms": call.latency_ms,
                    "started_at": _iso(call.started_at),
                    "completed_at": _iso(call.completed_at),
                    "created_at": _iso(call.created_at),
                    "canonical_failure_code": canonical,
                    "error": _redact(call.error),
                    "error_fingerprint": _text_fingerprint(call.error),
                    "structured_result": _redact(call.structured_result),
                    "diagnostics": _redact(diagnostics),
                    "pricing": _redact(
                        {
                            key: value
                            for key, value in (call.pricing_snapshot or {}).items()
                            if key != "_evaluation_judge"
                        }
                    ),
                }
            )

        timeline.sort(key=lambda item: (item["at"], item["stage"], item.get("trial_id") or ""))

        signals: list[dict[str, str]] = []
        failed_calls = [item for item in calls if item.status != "completed"]
        if runtime_completed_count == len(trials) and trials:
            signals.append(
                {
                    "severity": "info",
                    "code": "runtime_evidence_complete",
                    "message": "All target executions produced persisted runtime evidence; the failure boundary is after target execution.",
                }
            )
        if judge_started_count and len(calls) < judge_started_count:
            signals.append(
                {
                    "severity": "error",
                    "code": "judge_call_not_persisted",
                    "message": f"{judge_started_count - len(calls)} Trial(s) entered judging without a persisted model call row.",
                }
            )
        if failed_calls and diagnostics_present < len(failed_calls):
            signals.append(
                {
                    "severity": "warning",
                    "code": "judge_diagnostics_missing",
                    "message": f"{len(failed_calls) - diagnostics_present} failed Judge call(s) have no persisted adaptive diagnostics.",
                }
            )
        if failed_calls and repair_markers == 0:
            signals.append(
                {
                    "severity": "warning",
                    "code": "resilient_gateway_not_observed",
                    "message": "No resilient-judge-v1 repair marker was persisted. The worker may not have been restarted, the Run may predate that gateway, or the failure occurred before repair execution.",
                }
            )
        if calls and adaptive_markers == 0:
            signals.append(
                {
                    "severity": "warning",
                    "code": "adaptive_gateway_version_not_observed",
                    "message": "No adaptive-judge-v4 marker was persisted in model-call diagnostics.",
                }
            )
        if failed_calls and all(item.cost_usd is None for item in failed_calls):
            signals.append(
                {
                    "severity": "warning",
                    "code": "judge_usage_unreported",
                    "message": "Every failed Judge call has unknown cost and token usage, which commonly indicates failure before a usable provider response was normalized.",
                }
            )
        if error_counter:
            signature, count = error_counter.most_common(1)[0]
            if count > 1:
                signals.append(
                    {
                        "severity": "error",
                        "code": "repeated_judge_failure_signature",
                        "message": f"The same normalized error signature affected {count} Trial(s): {signature}",
                    }
                )

        failure_groups = [
            {"code": code, "count": count}
            for code, count in failure_counter.most_common()
        ]
        repeated_errors = [
            {"signature": signature, "count": count}
            for signature, count in error_counter.most_common()
        ]

        return {
            "schema_version": _DIAGNOSTICS_SCHEMA_VERSION,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "security": {
                "redacted": True,
                "policy": "Secrets, credentials, Authorization headers, cookies and token values are removed. Large strings and collections are bounded.",
            },
            "summary": {
                "run_id": str(run.id),
                "run_status": run.status,
                "assessment_status": (
                    (run.aggregate_result or {}).get("assessment", {}).get("status")
                    if isinstance((run.aggregate_result or {}).get("assessment"), dict)
                    else None
                ),
                "total_trials": len(trials),
                "runtime_completed": runtime_completed_count,
                "judge_started": judge_started_count,
                "judge_calls": len(calls),
                "judge_calls_completed": sum(
                    1 for item in calls if item.status == "completed"
                ),
                "judge_calls_failed": len(failed_calls),
                "judge_diagnostics_present": diagnostics_present,
                "adaptive_gateway_markers": adaptive_markers,
                "resilient_repair_markers": repair_markers,
                "conclusive_trials": conclusive_count,
                "inconclusive_trials": len(trials) - conclusive_count,
                "measured_total_cost": float(run.measured_total_cost)
                if run.measured_total_cost is not None
                else None,
            },
            "signals": signals,
            "failure_groups": failure_groups,
            "repeated_errors": repeated_errors,
            "run": {
                "id": str(run.id),
                "project_id": str(run.project_id),
                "evaluation_id": str(run.evaluation_id)
                if getattr(run, "evaluation_id", None)
                else None,
                "suite_version_id": str(run.suite_version_id),
                "mode": run.mode,
                "status": run.status,
                "repetitions": run.repetitions,
                "execution_order": run.execution_order,
                "execution_policy": _redact(run.execution_policy),
                "randomization_seed": run.randomization_seed,
                "failure_code": run.failure_code,
                "failure_detail": _redact(run.failure_detail),
                "aggregate_result": _redact(run.aggregate_result),
                "estimated_preflight_cost": float(run.estimated_preflight_cost)
                if run.estimated_preflight_cost is not None
                else None,
                "measured_total_cost": float(run.measured_total_cost)
                if run.measured_total_cost is not None
                else None,
                "timestamps": {
                    "created_at": _iso(run.created_at),
                    "updated_at": _iso(run.updated_at),
                    "started_at": _iso(run.started_at),
                    "completed_at": _iso(run.completed_at),
                    "cancel_requested_at": _iso(run.cancel_requested_at),
                    "lease_expires_at": _iso(run.lease_expires_at),
                },
            },
            "suite": {
                "id": str(suite.id) if suite else None,
                "name": suite.name if suite else None,
                "suite_version_id": str(suite_version.id) if suite_version else None,
                "version": suite_version.version if suite_version else None,
                "suite_hash": suite_version.suite_hash if suite_version else None,
                "dataset_version_id": str(dataset_version.id)
                if dataset_version
                else None,
                "dataset_version": dataset_version.version if dataset_version else None,
                "dataset_content_hash": dataset_version.content_hash
                if dataset_version
                else None,
                "judge_provider_model_id": str(suite_version.judge_provider_model_id)
                if suite_version
                else None,
                "judge_config": _redact(suite_version.judge_config)
                if suite_version
                else None,
                "rubric": _redact(suite_version.rubric) if suite_version else None,
                "deterministic_checks": _redact(
                    suite_version.deterministic_checks
                )
                if suite_version
                else None,
                "acceptance_policy": _redact(suite_version.acceptance_policy)
                if suite_version
                else None,
            },
            "targets": [
                {
                    "id": str(target.id),
                    "side": target.side,
                    "target_type": target.target_type,
                    "source_type": target.source_type,
                    "entity_id": str(target.entity_id),
                    "environment": target.environment,
                    "display_name": target.display_name,
                    "display_version": target.display_version,
                    "snapshot_hash": target.snapshot_hash,
                    "composition_hash": target.composition_hash,
                    "manifest": _redact(_target_manifest(target)),
                }
                for target in targets
            ],
            "timeline": timeline,
            "judge_calls": call_logs,
            "trials": trial_logs,
        }


__all__ = [
    "EvaluationRunDiagnosticsService",
    "_redact",
]
