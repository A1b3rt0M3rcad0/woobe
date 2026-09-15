from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from modules.agent.application.interfaces.execution_context import current_execution
from modules.agent.application.interfaces.outbox import OutboxEventWriter
from modules.agent.application.use_cases.execution_event_factory import llm_event, tool_event
from modules.agent.domain.events import AgentDomainEvent, AgentExecutionFailedV1
from modules.agent.domain.run import AgentRunStatus
from modules.agent.infra.database.runtime_repositories import AgentRuntimeRepositories
from modules.agent.infra.execution.execution_instrumentation import (
    InstrumentedExecution,
    aggregate_usage,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id_text(value) -> str | None:
    return str(value) if value else None


def _provider_value(value) -> str | None:
    if value is None:
        return None
    return value.value if hasattr(value, "value") else str(value)


def _model_binding_payload(agent) -> dict[str, Any]:
    return {
        "provider_model_id": _id_text(getattr(agent, "provider_model_id", None)),
        "provider_credential_id": _id_text(getattr(agent, "provider_credential_id", None)),
        "model_binding": {
            "provider_model_id": _id_text(getattr(agent, "provider_model_id", None)),
            "provider_credential_id": _id_text(getattr(agent, "provider_credential_id", None)),
            "provider": _provider_value(getattr(agent, "provider", None)),
            "model": getattr(agent, "model", None),
        },
    }


def _fallback_model_binding_payload(agent) -> dict[str, Any]:
    return {
        "fallback_provider_model_id": _id_text(getattr(agent, "fallback_provider_model_id", None)),
        "fallback_credential_id": _id_text(getattr(agent, "fallback_credential_id", None)),
        "fallback_provider": _provider_value(getattr(agent, "fallback_provider", None)),
        "fallback_model": getattr(agent, "fallback_model", None),
        "fallback_model_binding": {
            "provider_model_id": _id_text(getattr(agent, "fallback_provider_model_id", None)),
            "provider_credential_id": _id_text(getattr(agent, "fallback_credential_id", None)),
            "provider": _provider_value(getattr(agent, "fallback_provider", None)),
            "model": getattr(agent, "fallback_model", None),
        },
    }


def _runtime_binding_payload(context, input_dto) -> dict[str, Any]:
    return {
        "execution_context": (
            context.execution_context
            if context and context.execution_context
            else input_dto.execution_context
        ),
        "execution_strategy": context.execution_strategy if context else None,
        "agent_release_id": _id_text(context.agent_release_id if context else None),
        "agent_release_version": context.agent_release_version if context else None,
    }


def _cost_diagnostics(llm_calls: list[dict[str, Any]]) -> dict[str, Any]:
    pricing_ids = []
    cost_reasons = []
    cost_statuses = []
    first_pricing_snapshot = None
    for call in llm_calls:
        pricing_id = call.get("pricing_id")
        if pricing_id and pricing_id not in pricing_ids:
            pricing_ids.append(pricing_id)
        reason = call.get("cost_reason")
        if reason and reason not in cost_reasons:
            cost_reasons.append(reason)
        status = call.get("cost_status")
        if status and status not in cost_statuses:
            cost_statuses.append(status)
        if first_pricing_snapshot is None and isinstance(call.get("pricing_snapshot"), dict):
            first_pricing_snapshot = call.get("pricing_snapshot")
    return {
        "pricing_ids": pricing_ids,
        "cost_reasons": cost_reasons,
        "cost_statuses": cost_statuses,
        "pricing_id": pricing_ids[0] if pricing_ids else None,
        "cost_reason": "; ".join(cost_reasons) if cost_reasons else None,
        "pricing_snapshot": first_pricing_snapshot,
    }


def _tool_provider_work_ms(timeline: list[dict[str, Any]]) -> int | None:
    values: list[int] = []
    for item in timeline:
        if item.get("kind") != "tool":
            continue
        payload = item.get("payload")
        if not isinstance(payload, dict):
            continue
        value = payload.get("provider_latency_ms")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            values.append(round(float(value)))
    return sum(values) if values else None


def _failed_event(agent_id, payload):
    return AgentExecutionFailedV1(
        payload=payload,
        idempotency_key=AgentDomainEvent.compute_idempotency_key(
            "agent",
            agent_id,
            AgentExecutionFailedV1.event_type,
            str(payload.get("trace_id")),
        ),
    )


def _diagnostics(
    *,
    execution: InstrumentedExecution,
    total_ms: int,
    prepare_latency_ms: int | float | None,
    finalization_work_ms: int,
    usage_complete: bool,
    cost_status: str,
    cost_details: dict[str, Any],
    binding_payload: dict[str, Any],
    fallback_binding_payload: dict[str, Any],
    failure_context: dict[str, Any],
    execution_strategy: str | None,
) -> dict[str, Any]:
    llm_work_ms = sum(
        int(call.get("latency_ms") or 0)
        for call in execution.llm_calls
    )
    tool_wall_ms = int(execution.tool_wall_latency_ms or 0)
    tool_work_ms = int(execution.tool_call_duration_sum_ms or 0)
    provider_work_ms = _tool_provider_work_ms(execution.timeline)
    tool_runtime_overhead_ms = (
        max(tool_work_ms - provider_work_ms, 0)
        if provider_work_ms is not None
        else None
    )
    other_ms = max(
        total_ms
        - int(prepare_latency_ms or 0)
        - llm_work_ms
        - tool_wall_ms
        - finalization_work_ms,
        0,
    )
    return {
        "schema_version": 5,
        "agent_runtime_latency_ms": total_ms,
        "total_latency_ms": total_ms,
        "prepare_latency_ms": prepare_latency_ms or 0,
        "llm_work_latency_ms": llm_work_ms,
        "llm_runtime_latency_ms": llm_work_ms,
        "tool_wall_latency_ms": tool_wall_ms,
        "tool_work_latency_ms": tool_work_ms,
        "tool_call_duration_sum_ms": tool_work_ms,
        "tool_parallelism_ratio": (
            round(tool_work_ms / tool_wall_ms, 3)
            if tool_wall_ms > 0
            else None
        ),
        "tool_provider_work_ms": provider_work_ms,
        "tool_runtime_overhead_ms": tool_runtime_overhead_ms,
        "finalization_work_latency_ms": finalization_work_ms,
        "persistence_latency_ms": finalization_work_ms,
        "other_latency_ms": other_ms,
        "unaccounted_latency_ms": other_ms,
        "orchestration_latency_ms": None,
        "llm_call_count": len(execution.llm_calls),
        "tool_call_count": len(execution.tool_calls),
        "usage_complete": usage_complete,
        "cost_status": cost_status,
        "cost_reason": cost_details["cost_reason"],
        "cost_statuses": cost_details["cost_statuses"],
        "pricing_ids": cost_details["pricing_ids"],
        "provider_model_id": binding_payload["provider_model_id"],
        "provider_credential_id": binding_payload["provider_credential_id"],
        "fallback_provider_model_id": fallback_binding_payload["fallback_provider_model_id"],
        "fallback_credential_id": fallback_binding_payload["fallback_credential_id"],
        "execution_strategy": execution_strategy,
        "failure_phase": failure_context.get("phase"),
        "failure_call_index": failure_context.get("call_index"),
        "upstream_status": failure_context.get("upstream_status"),
        "upstream_error_code": failure_context.get("upstream_error_code"),
        "partial_result_available": failure_context.get("partial_result_available") is True,
    }


async def finalize_failed_instrumented_execution(
    owner,
    *,
    session,
    agent,
    input_dto,
    trace_id,
    error: str,
    execution: InstrumentedExecution,
    started_at: float,
    prepare_latency_ms: int | float | None = None,
) -> None:
    context = current_execution.get()
    run_id = context.run_id if context else None
    trace_id_text = str(trace_id)
    project_id_text = str(input_dto.project_id)
    agent_id_text = str(agent.id)
    aggregate, usage_complete, cost_status = aggregate_usage(execution.llm_calls)
    cost_details = _cost_diagnostics(execution.llm_calls)
    binding_payload = _model_binding_payload(agent)
    fallback_binding_payload = _fallback_model_binding_payload(agent)
    runtime_binding_payload = _runtime_binding_payload(context, input_dto)
    trace_binding_payload = {
        **binding_payload,
        **fallback_binding_payload,
        **runtime_binding_payload,
    }
    failure_context = execution.failure_context or {}

    preliminary_total_ms = round((time.monotonic() - started_at) * 1000)
    preliminary_diagnostics = _diagnostics(
        execution=execution,
        total_ms=preliminary_total_ms,
        prepare_latency_ms=prepare_latency_ms,
        finalization_work_ms=0,
        usage_complete=usage_complete,
        cost_status=cost_status,
        cost_details=cost_details,
        binding_payload=binding_payload,
        fallback_binding_payload=fallback_binding_payload,
        failure_context=failure_context,
        execution_strategy=runtime_binding_payload["execution_strategy"],
    )
    payload = {
        "run_id": str(run_id) if run_id else None,
        "trace_id": trace_id_text,
        "project_id": project_id_text,
        "agent_id": agent_id_text,
        "session_id": str(session.id) if session else None,
        "error": error,
        "input_tokens": aggregate.input_tokens,
        "output_tokens": aggregate.output_tokens,
        "total_tokens": aggregate.total_tokens,
        "cost_usd": aggregate.cost_usd,
        "cost_status": cost_status,
        "cost_reason": cost_details["cost_reason"],
        "pricing_id": cost_details["pricing_id"],
        "pricing_snapshot": cost_details["pricing_snapshot"],
        "usage_complete": usage_complete,
        **trace_binding_payload,
        "model": getattr(agent, "model", None),
        "provider": _provider_value(getattr(agent, "provider", None)),
        "latency_ms": preliminary_total_ms,
        "total_latency_ms": preliminary_total_ms,
        "runtime_scope": "failed_execution_terminal_persistence_pending",
        **preliminary_diagnostics,
        "tool_calls": [tool.model_dump() for tool in execution.tool_calls],
        "llm_calls": execution.llm_calls,
        "diagnostics": preliminary_diagnostics,
        "timeline_complete": False,
        "failed_at": _utc_now(),
    }
    await owner._hot_terminal_pending(terminal_status="failed", result=payload)

    async def persist_failure(
        repositories: AgentRuntimeRepositories,
        outbox: OutboxEventWriter,
    ) -> None:
        finalization_started = time.monotonic()
        for item in sorted(execution.timeline, key=lambda value: value.get("occurred_at", "")):
            event_payload = {
                "run_id": str(run_id) if run_id else None,
                "trace_id": trace_id_text,
                "project_id": project_id_text,
                "agent_id": agent_id_text,
                **trace_binding_payload,
                **item["payload"],
            }
            event = (
                llm_event(agent.id, event_payload)
                if item["kind"] == "llm"
                else tool_event(agent.id, event_payload)
            )
            await outbox.write(event)

        finalization_work_ms = round(
            (time.monotonic() - finalization_started) * 1000
        )
        total_ms = round((time.monotonic() - started_at) * 1000)
        diagnostics = _diagnostics(
            execution=execution,
            total_ms=total_ms,
            prepare_latency_ms=prepare_latency_ms,
            finalization_work_ms=finalization_work_ms,
            usage_complete=usage_complete,
            cost_status=cost_status,
            cost_details=cost_details,
            binding_payload=binding_payload,
            fallback_binding_payload=fallback_binding_payload,
            failure_context=failure_context,
            execution_strategy=runtime_binding_payload["execution_strategy"],
        )
        payload.update(
            {
                "latency_ms": total_ms,
                "total_latency_ms": total_ms,
                "runtime_scope": "failed_execution_through_terminal_persistence_work_pre_commit",
                **diagnostics,
                "diagnostics": diagnostics,
                "failed_at": _utc_now(),
            }
        )
        await outbox.write(_failed_event(agent.id, payload))
        if run_id is not None:
            run = await repositories.runs.get_by_id(run_id)
            if run is not None:
                run.status = AgentRunStatus.FAILED
                run.failure_code = str(
                    failure_context.get("phase") or "runtime_error"
                )
                run.failure_detail = error[:8000]
                run.usage = (
                    aggregate.model_dump()
                    if hasattr(aggregate, "model_dump")
                    else None
                )
                run.result = payload
                run.completed_at = datetime.now(timezone.utc)
                await repositories.runs.save(run)

    await owner._transactions.run(persist_failure)
    if context is not None:
        context.terminal_persisted = True
    await owner._hot_persisted("failed")
