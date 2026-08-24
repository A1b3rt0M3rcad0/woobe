from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from modules.agent.application.use_cases.execution_event_factory import llm_event, tool_event
from modules.agent.domain.events import AgentDomainEvent, AgentExecutionFailedV1
from modules.agent.infra.database.repositories import SQLAlchemyAgentOutboxEventWriter
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
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
    trace_id_text = str(trace_id)
    project_id_text = str(input_dto.project_id)
    agent_id_text = str(agent.id)
    aggregate, usage_complete, cost_status = aggregate_usage(execution.llm_calls)
    cost_details = _cost_diagnostics(execution.llm_calls)
    binding_payload = _model_binding_payload(agent)
    fallback_binding_payload = _fallback_model_binding_payload(agent)
    trace_binding_payload = {**binding_payload, **fallback_binding_payload}
    failure_context = execution.failure_context or {}

    total_ms = round((time.monotonic() - started_at) * 1000)
    llm_ms = sum(int(call.get("latency_ms") or 0) for call in execution.llm_calls)
    http_ms = sum(
        int(item["payload"].get("http_latency_ms") or 0)
        for item in execution.timeline
        if item.get("kind") == "tool"
    )
    tool_ms = execution.tool_wall_latency_ms
    orchestration_ms = max(
        total_ms - int(prepare_latency_ms or 0) - llm_ms - tool_ms,
        0,
    )
    failed_at = _utc_now()
    diagnostics = {
        "schema_version": 4,
        "total_latency_ms": total_ms,
        "prepare_latency_ms": prepare_latency_ms or 0,
        "llm_runtime_latency_ms": llm_ms,
        "tool_wall_latency_ms": tool_ms,
        "tool_call_duration_sum_ms": execution.tool_call_duration_sum_ms,
        "tool_http_latency_ms": http_ms,
        "orchestration_latency_ms": orchestration_ms,
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
        "failure_phase": failure_context.get("phase"),
        "failure_call_index": failure_context.get("call_index"),
        "upstream_status": failure_context.get("upstream_status"),
        "upstream_error_code": failure_context.get("upstream_error_code"),
        "partial_result_available": failure_context.get("partial_result_available") is True,
    }
    payload = {
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
        "latency_ms": total_ms,
        "total_latency_ms": total_ms,
        "runtime_scope": "failed_execution_with_collected_telemetry",
        **diagnostics,
        "tool_calls": [tool.model_dump() for tool in execution.tool_calls],
        "llm_calls": execution.llm_calls,
        "diagnostics": diagnostics,
        "timeline_complete": False,
        "failed_at": failed_at,
    }

    async with AgentUnitOfWork(owner._session_factory) as uow:
        outbox = SQLAlchemyAgentOutboxEventWriter(uow)
        for item in sorted(
            execution.timeline,
            key=lambda value: value.get("occurred_at", ""),
        ):
            event_payload = {
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
        await outbox.write(_failed_event(agent.id, payload))
