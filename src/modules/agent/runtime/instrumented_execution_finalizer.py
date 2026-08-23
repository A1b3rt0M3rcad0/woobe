from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from modules.agent.application.dtos.runtime_dtos import AskOutput
from modules.agent.application.interfaces.execution_context import current_execution
from modules.agent.application.use_cases.execution_event_factory import (
    completed_event,
    fallback_event,
    llm_event,
    tool_event,
)
from modules.agent.application.use_cases.trace_event_builder import (
    build_operation_events,
    sequence_events,
)
from modules.agent.runtime.runtime_repositories import (
    build_agent_runtime_repositories,
)
from modules.agent.infra.database.repositories import (
    SQLAlchemyAgentOutboxEventWriter,
)
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork


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


def _event(
    trace_id: str,
    event_type: str,
    occurred_at: str,
    *,
    phase: str,
    status: str,
    started_at: str | None = None,
    ended_at: str | None = None,
    duration_ms: int | float | None = None,
    attributes: dict[str, Any] | None = None,
    span_id: str | None = None,
    parent_span_id: str | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "event_id": str(uuid4()),
        "trace_id": trace_id,
        "root_span_id": trace_id,
        "span_id": span_id or str(uuid4()),
        "parent_span_id": parent_span_id or trace_id,
        "sequence": 0,
        "event_type": event_type,
        "phase": phase,
        "status": status,
        "occurred_at": occurred_at,
        "started_at": started_at,
        "ended_at": ended_at,
        "duration_ms": duration_ms,
        "attributes": attributes or {},
    }


async def finalize_instrumented_execution(owner, **kw):
    session = kw["session"]
    agent = kw["agent"]
    execution = kw["execution"]
    trace_id = kw["trace_id"]
    trace_id_text = str(trace_id)
    usage = kw["usage"]
    context = current_execution.get()
    parse_completed_at = _utc_now()
    persistence_started_at = _utc_now()
    persistence_started = time.monotonic()
    message_id = None

    project_id_text = str(kw["input_dto"].project_id)
    agent_id_text = str(agent.id)
    binding_payload = _model_binding_payload(agent)
    fallback_binding_payload = _fallback_model_binding_payload(agent)
    runtime_binding_payload = _runtime_binding_payload(context, kw["input_dto"])
    trace_binding_payload = {
        **binding_payload,
        **fallback_binding_payload,
        **runtime_binding_payload,
    }

    async with AgentUnitOfWork(owner._session_factory) as uow:
        repositories = build_agent_runtime_repositories(uow)
        outbox = SQLAlchemyAgentOutboxEventWriter(uow)
        if session:
            message = await owner._do_save_assistant_message(
                repositories.messages,
                repositories.sessions,
                outbox,
                session,
                kw["answer"],
                usage,
                agent,
                tool_calls=execution.tool_calls,
            )
            message_id = message.id
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
        if kw["fallback_info"]:
            await outbox.write(
                fallback_event(
                    agent.id,
                    {
                        "trace_id": trace_id_text,
                        "project_id": project_id_text,
                        "agent_id": agent_id_text,
                        **trace_binding_payload,
                        **kw["fallback_info"],
                    },
                )
            )

    persistence_ms = round((time.monotonic() - persistence_started) * 1000)
    persistence_ended_at = _utc_now()
    total_ms = round((time.monotonic() - kw["started_at"]) * 1000)
    execution_completed_at = _utc_now()
    llm_ms = sum(
        int(call.get("latency_ms") or 0)
        for call in execution.llm_calls
    )
    orchestration_ms = max(
        total_ms
        - kw["prepare_latency_ms"]
        - persistence_ms
        - llm_ms
        - execution.tool_wall_latency_ms,
        0,
    )
    http_ms = sum(
        int(item["payload"].get("http_latency_ms") or 0)
        for item in execution.timeline
        if item.get("kind") == "tool"
    )
    cost_details = _cost_diagnostics(execution.llm_calls)
    diagnostics = {
        "schema_version": 4,
        "total_latency_ms": total_ms,
        "prepare_latency_ms": kw["prepare_latency_ms"],
        "llm_runtime_latency_ms": llm_ms,
        "tool_wall_latency_ms": execution.tool_wall_latency_ms,
        "tool_call_duration_sum_ms": execution.tool_call_duration_sum_ms,
        "tool_http_latency_ms": http_ms,
        "persistence_latency_ms": persistence_ms,
        "orchestration_latency_ms": orchestration_ms,
        "llm_call_count": len(execution.llm_calls),
        "tool_call_count": len(execution.tool_calls),
        "usage_complete": kw["usage_complete"],
        "cost_status": kw["cost_status"],
        "cost_reason": cost_details["cost_reason"],
        "cost_statuses": cost_details["cost_statuses"],
        "pricing_ids": cost_details["pricing_ids"],
        "provider_model_id": binding_payload["provider_model_id"],
        "provider_credential_id": binding_payload["provider_credential_id"],
        "fallback_provider_model_id": fallback_binding_payload["fallback_provider_model_id"],
        "fallback_credential_id": fallback_binding_payload["fallback_credential_id"],
        **runtime_binding_payload,
    }

    request_received_at = (
        context.request_received_at if context else execution_completed_at
    )
    execution_started_at = (
        context.execution_started_at if context else request_received_at
    )
    execution_events = [
        _event(
            trace_id_text,
            "http.request.received",
            request_received_at,
            phase="request",
            status="success",
            started_at=request_received_at,
            ended_at=request_received_at,
            duration_ms=0,
            attributes={
                "client_sent_at": context.client_sent_at if context else None,
                **runtime_binding_payload,
            },
            span_id=trace_id_text,
            parent_span_id=None,
        ),
        _event(
            trace_id_text,
            "agent.execution.started",
            execution_started_at,
            phase="execution",
            status="running",
            started_at=execution_started_at,
            span_id=trace_id_text,
            parent_span_id=None,
            attributes={
                **binding_payload["model_binding"],
                "fallback_provider_model_id": fallback_binding_payload["fallback_provider_model_id"],
                **runtime_binding_payload,
            },
        ),
    ]
    if context and context.prepare_started_at:
        prepare_span = str(uuid4())
        execution_events.extend([
            _event(
                trace_id_text,
                "agent.prepare.started",
                context.prepare_started_at,
                phase="prepare",
                status="running",
                started_at=context.prepare_started_at,
                span_id=prepare_span,
            ),
            _event(
                trace_id_text,
                "agent.prepare.completed",
                context.prepare_ended_at or context.prepare_started_at,
                phase="prepare",
                status="success",
                started_at=context.prepare_started_at,
                ended_at=context.prepare_ended_at,
                duration_ms=context.prepare_latency_ms,
                span_id=prepare_span,
            ),
        ])
    execution_events.extend(build_operation_events(trace_id_text, execution.timeline))
    execution_events.append(
        _event(
            trace_id_text,
            "structured_output.parse.completed",
            parse_completed_at,
            phase="structured_output",
            status="success" if kw["output_parse_error"] is None else "error",
            ended_at=parse_completed_at,
            attributes={
                "parsed": kw["parsed_output"] is not None,
                "error": kw["output_parse_error"],
                "duration_measured": False,
            },
        )
    )
    persistence_span = str(uuid4())
    execution_events.extend([
        _event(
            trace_id_text,
            "message.persistence.started",
            persistence_started_at,
            phase="persistence",
            status="running",
            started_at=persistence_started_at,
            span_id=persistence_span,
        ),
        _event(
            trace_id_text,
            "message.persistence.completed",
            persistence_ended_at,
            phase="persistence",
            status="success",
            started_at=persistence_started_at,
            ended_at=persistence_ended_at,
            duration_ms=persistence_ms,
            span_id=persistence_span,
        ),
        _event(
            trace_id_text,
            "agent.execution.completed",
            execution_completed_at,
            phase="execution",
            status="success",
            started_at=execution_started_at,
            ended_at=execution_completed_at,
            duration_ms=total_ms,
            attributes={
                "diagnostics": diagnostics,
                **binding_payload["model_binding"],
                **runtime_binding_payload,
            },
            span_id=trace_id_text,
            parent_span_id=None,
        ),
        _event(
            trace_id_text,
            "http.response.prepared",
            execution_completed_at,
            phase="response",
            status="success",
            ended_at=execution_completed_at,
        ),
    ])
    execution_events = sequence_events(execution_events)

    sources = kw["sources"] or []
    payload = {
        "trace_id": trace_id_text,
        "project_id": project_id_text,
        "agent_id": agent_id_text,
        "session_id": str(session.id) if session else None,
        "message_id": str(message_id) if message_id else None,
        "answer_length": len(kw["answer"]),
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "total_tokens": usage.total_tokens,
        "cost_usd": usage.cost_usd,
        "cost_status": kw["cost_status"],
        "cost_reason": cost_details["cost_reason"],
        "pricing_id": cost_details["pricing_id"],
        "pricing_snapshot": cost_details["pricing_snapshot"],
        "usage_complete": kw["usage_complete"],
        **trace_binding_payload,
        "model": kw["response_model"] or agent.model,
        "provider": kw["response_provider"] or "",
        "latency_ms": total_ms,
        "total_latency_ms": total_ms,
        "runtime_scope": "through_response_persistence",
        **diagnostics,
        "fallback_used": kw["fallback_used"],
        "sources": [source.model_dump() for source in sources],
        "parsed_output": kw["parsed_output"],
        "output_parse_error": kw["output_parse_error"],
        "tool_calls": [tool.model_dump() for tool in execution.tool_calls],
        "llm_calls": execution.llm_calls,
        "execution_events": execution_events,
        "timeline_complete": True,
    }
    if kw["fallback_info"]:
        payload["fallback_info"] = {**kw["fallback_info"], **fallback_binding_payload}
    async with AgentUnitOfWork(owner._session_factory) as uow:
        writer = SQLAlchemyAgentOutboxEventWriter(uow)
        await writer.write(completed_event(agent.id, payload))

    output = AskOutput(
        answer=kw["answer"],
        session_id=session.id if session else None,
        message_id=message_id,
        usage=usage,
        sources=sources,
        tool_calls=execution.tool_calls,
        trace_id=trace_id,
        model=kw["response_model"],
        provider=kw["response_provider"],
        provider_model_id=getattr(agent, "provider_model_id", None),
        provider_credential_id=getattr(agent, "provider_credential_id", None),
        fallback_provider_model_id=getattr(agent, "fallback_provider_model_id", None),
        fallback_credential_id=getattr(agent, "fallback_credential_id", None),
        fallback_used=kw["fallback_used"],
        fallback_info=payload.get("fallback_info"),
        latency_ms=total_ms,
        parsed_output=kw["parsed_output"],
        output_parse_error=kw["output_parse_error"],
    )
    object.__setattr__(output, "execution_events", execution_events)
    object.__setattr__(output, "diagnostics", diagnostics)
    return output