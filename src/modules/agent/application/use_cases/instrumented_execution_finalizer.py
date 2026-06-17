import time

from modules.agent.application.dtos.runtime_dtos import AskOutput
from modules.agent.application.use_cases.execution_event_factory import (
    completed_event, fallback_event, llm_event, tool_event,
)
from modules.agent.infra.database.repositories import SQLAlchemyAgentOutboxEventWriter
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork


async def finalize_instrumented_execution(owner, **kw):
    session = kw["session"]
    agent = kw["agent"]
    execution = kw["execution"]
    trace_id = kw["trace_id"]
    usage = kw["usage"]
    started = time.monotonic()
    message_id = None

    async with AgentUnitOfWork(owner._session_factory) as uow:
        outbox = SQLAlchemyAgentOutboxEventWriter(uow)
        if session:
            msg = await owner._do_save_assistant_message(
                uow.messages, uow.sessions, outbox, session, kw["answer"],
                usage, agent, tool_calls=execution.tool_calls,
            )
            message_id = msg.id
        for item in sorted(execution.timeline, key=lambda x: x.get("occurred_at", "")):
            payload = {"trace_id": str(trace_id), **item["payload"]}
            event = llm_event(agent.id, payload) if item["kind"] == "llm" else tool_event(agent.id, payload)
            await outbox.write(event)
        if kw["fallback_info"]:
            payload = {"trace_id": str(trace_id), **kw["fallback_info"]}
            await outbox.write(fallback_event(agent.id, payload))

    persist_ms = round((time.monotonic() - started) * 1000)
    total_ms = round((time.monotonic() - kw["started_at"]) * 1000)
    llm_ms = sum(int(x.get("latency_ms") or 0) for x in execution.llm_calls)
    orchestration_ms = max(
        total_ms - kw["prepare_latency_ms"] - persist_ms
        - llm_ms - execution.tool_wall_latency_ms,
        0,
    )
    http_ms = sum(
        int(x["payload"].get("http_latency_ms") or 0)
        for x in execution.timeline if x.get("kind") == "tool"
    )
    sources = kw["sources"] or []
    payload = {
        "trace_id": str(trace_id),
        "project_id": str(kw["input_dto"].project_id),
        "agent_id": str(agent.id),
        "session_id": str(session.id) if session else None,
        "message_id": str(message_id) if message_id else None,
        "answer_length": len(kw["answer"]),
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "total_tokens": usage.total_tokens,
        "cost_usd": usage.cost_usd,
        "cost_status": kw["cost_status"],
        "usage_complete": kw["usage_complete"],
        "model": kw["response_model"] or agent.model,
        "provider": kw["response_provider"] or "",
        "latency_ms": total_ms,
        "total_latency_ms": total_ms,
        "runtime_scope": "through_response_persistence",
        "prepare_latency_ms": kw["prepare_latency_ms"],
        "persistence_latency_ms": persist_ms,
        "orchestration_latency_ms": orchestration_ms,
        "llm_runtime_latency_ms": llm_ms,
        "tool_wall_latency_ms": execution.tool_wall_latency_ms,
        "tool_call_duration_sum_ms": execution.tool_call_duration_sum_ms,
        "tool_http_latency_ms": http_ms,
        "fallback_used": kw["fallback_used"],
        "sources": [x.model_dump() for x in sources],
        "parsed_output": kw["parsed_output"],
        "output_parse_error": kw["output_parse_error"],
        "tool_calls": [x.model_dump() for x in execution.tool_calls],
        "llm_calls": execution.llm_calls,
        "timeline_complete": True,
    }
    if kw["fallback_info"]:
        payload["fallback_info"] = kw["fallback_info"]
    async with AgentUnitOfWork(owner._session_factory) as uow:
        await SQLAlchemyAgentOutboxEventWriter(uow).write(completed_event(agent.id, payload))

    return AskOutput(
        answer=kw["answer"], session_id=session.id if session else None,
        message_id=message_id, usage=usage, sources=sources,
        tool_calls=execution.tool_calls, trace_id=trace_id,
        model=kw["response_model"], provider=kw["response_provider"],
        fallback_used=kw["fallback_used"], fallback_info=kw["fallback_info"],
        latency_ms=total_ms, parsed_output=kw["parsed_output"],
        output_parse_error=kw["output_parse_error"],
    )
