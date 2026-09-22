from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import uuid6

from modules.agent.application.dtos.runtime_dtos import AskOutput
from modules.agent.application.interfaces.execution_context import current_execution
from modules.agent.infra.execution.trace_event_builder import build_execution_timeline_events
from modules.agent.domain.entities import Message
from modules.agent.domain.enums import MessageRole
from modules.agent.domain.errors import MessageNotFoundError
from modules.agent.domain.events import AgentMessageCreatedV1
from modules.agent.infra.execution.agent_run_metrics import build_agent_run_metrics
from modules.agent.infra.execution.execution_instrumentation import aggregate_usage
from shared.contracts.time import utc_now
from shared.runtime.event_schema import EVENT_JOURNAL_STORAGE_VERSION

logger = logging.getLogger(__name__)


def _id_text(value: Any) -> str | None:
    return str(value) if value else None


def _provider_value(value: Any) -> str | None:
    if value is None:
        return None
    return value.value if hasattr(value, "value") else str(value)


def _datetime_value(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _recorder():
    context = current_execution.get()
    recorder = context.run_event_recorder if context is not None else None
    if recorder is None:
        raise RuntimeError("Durable Agent Run journal recorder is not bound")
    return context, recorder


async def _materialize_assistant_session_message(
    owner: Any,
    *,
    message_id: Any,
    session: Any,
    agent: Any,
    answer: str,
    usage: Any | None,
    data: dict[str, Any],
    created_at: datetime | None = None,
) -> Any:
    """Make the completed turn immediately visible to the Session read model.

    The durable ``run.completed`` journal event remains the terminal authority. This
    short PostgreSQL projection closes the user-visible/context-consistency window
    between that durable event and the asynchronous journal projector. The async
    projector keeps the same message id and remains the recovery/idempotency path.
    """

    async def persist(repositories, outbox):
        try:
            existing = await repositories.messages.get_by_id(message_id)
        except MessageNotFoundError:
            existing = None
        if existing is not None:
            return existing

        message = Message(
            id=message_id,
            project_id=session.project_id,
            agent_id=session.agent_id,
            session_id=session.id,
            role=MessageRole.ASSISTANT,
            content=answer,
            input_tokens=getattr(usage, "input_tokens", None),
            output_tokens=getattr(usage, "output_tokens", None),
            cost_usd=getattr(usage, "cost_usd", None),
            data=dict(data),
            created_at=created_at,
            updated_at=created_at,
        )
        created = await repositories.messages.create(message)
        message_time = created_at or _datetime_value(utc_now())
        if (
            message_time is not None
            and (
                session.last_message_at is None
                or message_time > session.last_message_at
            )
        ):
            session.last_message_at = message_time
        try:
            await repositories.sessions.update(session)
        except Exception as exc:
            logger.warning(
                "Failed to update Session after synchronous Assistant message projection: %s",
                exc,
            )
        await outbox.write(
            AgentMessageCreatedV1.create(
                message_id=created.id,
                session_id=session.id,
                project_id=session.project_id,
                agent_id=agent.id,
                role="assistant",
            )
        )
        return created

    return await owner._transactions.run(persist)


async def _materialize_intermediate_messages(
    owner: Any,
    *,
    context: Any,
    session: Any,
    agent: Any,
) -> None:
    for item in list(context.intermediate_messages or []):
        try:
            message_id = UUID(str(item["message_id"]))
        except (KeyError, TypeError, ValueError):
            continue
        content = item.get("content")
        if not isinstance(content, str) or not content:
            continue
        await _materialize_assistant_session_message(
            owner,
            message_id=message_id,
            session=session,
            agent=agent,
            answer=content,
            usage=None,
            data={
                "run_id": str(context.run_id),
                "trace_id": str(context.trace_id) if context.trace_id else None,
                "phase": item.get("phase"),
                "output_mode": "intermediate",
                "provider": item.get("provider"),
                "model": item.get("model"),
                "partial": bool(item.get("partial")),
            },
            created_at=_datetime_value(item.get("completed_at")),
        )


class EventJournalAgentRunPersistence:
    storage_version = EVENT_JOURNAL_STORAGE_VERSION

    async def complete(self, owner: Any, **kw: Any) -> AskOutput:
        context, recorder = _recorder()
        execution = kw["execution"]
        agent = kw["agent"]
        session = kw["session"]
        usage = kw["usage"]
        completed_at = datetime.now(timezone.utc).isoformat()
        metrics = build_agent_run_metrics(
            context=context,
            execution=execution,
            binding=agent,
            fallback_used=kw["fallback_used"],
            finalization_work_ms=0,
            prepare_latency_ms=kw.get("prepare_latency_ms"),
            usage=usage,
            usage_complete=kw.get("usage_complete"),
            cost_status=kw.get("cost_status"),
            completed_at=completed_at,
        )
        canonical_usage = metrics.usage
        execution_events = build_execution_timeline_events(
            str(kw["trace_id"]),
            context=context,
            timeline=list(execution.timeline),
            completed_at=metrics.completed_at,
            total_latency_ms=metrics.total_latency_ms,
            output_parse_error=kw.get("output_parse_error"),
            completion_attributes={"diagnostics": metrics.diagnostics},
            include_http_boundaries=True,
        )
        message_id = context.output_message_id or uuid6.uuid7()
        context.output_message_id = message_id
        sources = kw.get("sources") or []
        source_payloads = [
            source.model_dump() if hasattr(source, "model_dump") else source
            for source in sources
        ]
        tool_payloads = [
            call.model_dump() if hasattr(call, "model_dump") else call
            for call in execution.tool_calls
        ]
        payload = {
            "run_id": str(context.run_id),
            "trace_id": str(kw["trace_id"]),
            "project_id": str(kw["input_dto"].project_id),
            "agent_id": str(agent.id),
            "session_id": str(session.id),
            "message_id": str(message_id),
            "answer": kw["answer"],
            "usage": canonical_usage.model_dump(),
            "input_tokens": canonical_usage.input_tokens,
            "output_tokens": canonical_usage.output_tokens,
            "total_tokens": canonical_usage.total_tokens,
            "cost_usd": canonical_usage.cost_usd,
            "provider": kw.get("response_provider") or _provider_value(agent.provider),
            "model": kw.get("response_model") or agent.model,
            "provider_model_id": _id_text(getattr(agent, "provider_model_id", None)),
            "provider_credential_id": _id_text(
                getattr(agent, "provider_credential_id", None)
            ),
            "fallback_provider_model_id": _id_text(
                getattr(agent, "fallback_provider_model_id", None)
            ),
            "fallback_credential_id": _id_text(
                getattr(agent, "fallback_credential_id", None)
            ),
            "fallback_used": bool(kw["fallback_used"]),
            "fallback_info": kw.get("fallback_info"),
            "sources": source_payloads,
            "tool_calls": tool_payloads,
            # Kept as a compact compatibility summary. Canonical invocation facts are
            # already separate model.invocation.* journal events.
            "llm_calls": list(execution.llm_calls),
            "parsed_output": kw.get("parsed_output"),
            "output_parse_error": kw.get("output_parse_error"),
            "diagnostics": metrics.diagnostics,
            "latency_ms": metrics.total_latency_ms,
            "started_at": metrics.started_at,
            "completed_at": metrics.completed_at,
            "execution_events": execution_events,
            "timeline_complete": True,
        }
        await owner._hot_terminal_pending(terminal_status="completed", result=payload)
        await recorder.emit("run.completed", payload, durable=True)

        # Standalone and Network Agent chats expose the same semantic Session turn:
        # user input + persisted Assistant output with the common runtime metadata.
        # Network adds its own execution/invocation identifiers on top of this shape.
        assistant_message_data = {
            "run_id": payload["run_id"],
            "trace_id": payload["trace_id"],
            "provider": payload["provider"],
            "model": payload["model"],
            "latency_ms": payload["latency_ms"],
            "tool_calls": list(tool_payloads),
            "sources": list(source_payloads),
            "parsed_output": payload["parsed_output"],
            "output_parse_error": payload["output_parse_error"],
            "cancelled": False,
            "partial": False,
            "output_mode": "final",
        }

        # Standalone Session history is an interactive correctness boundary: the
        # next user turn can start immediately after this method returns. Persist
        # completed intermediate Assistant messages first, then the terminal answer,
        # while Mongo remains the durable recovery authority.
        try:
            await _materialize_intermediate_messages(
                owner,
                context=context,
                session=session,
                agent=agent,
            )
            await _materialize_assistant_session_message(
                owner,
                message_id=message_id,
                session=session,
                agent=agent,
                answer=kw["answer"],
                usage=canonical_usage,
                data=assistant_message_data,
            )
        except Exception as exc:
            # The terminal event is already durable. A projection failure must
            # not rewrite the completed Run as failed; the async projector will
            # retry the same deterministic message id.
            logger.warning(
                "Durable Agent Run %s completed but synchronous Assistant Session "
                "message projection failed; async projector will retry: %s",
                context.run_id,
                exc,
            )

        context.terminal_persisted = True
        await owner._hot_persisted("completed")
        output = AskOutput(
            run_id=context.run_id,
            answer=kw["answer"],
            session_id=session.id,
            message_id=message_id,
            usage=canonical_usage,
            sources=sources,
            tool_calls=execution.tool_calls,
            trace_id=kw["trace_id"],
            model=kw.get("response_model"),
            provider=kw.get("response_provider"),
            provider_model_id=getattr(agent, "provider_model_id", None),
            provider_credential_id=getattr(agent, "provider_credential_id", None),
            fallback_provider_model_id=getattr(
                agent, "fallback_provider_model_id", None
            ),
            fallback_credential_id=getattr(agent, "fallback_credential_id", None),
            fallback_used=bool(kw["fallback_used"]),
            fallback_info=kw.get("fallback_info"),
            latency_ms=metrics.total_latency_ms,
            parsed_output=kw.get("parsed_output"),
            output_parse_error=kw.get("output_parse_error"),
            execution_events=execution_events,
            diagnostics=metrics.diagnostics,
        )
        return output

    async def fail(self, owner: Any, **kw: Any) -> None:
        context, recorder = _recorder()
        execution = kw["execution"]
        session = kw["session"]
        aggregate, usage_complete, cost_status = aggregate_usage(execution.llm_calls)
        metrics = build_agent_run_metrics(
            context=context,
            execution=execution,
            binding=kw["agent"],
            fallback_used=False,
            finalization_work_ms=0,
            prepare_latency_ms=kw.get("prepare_latency_ms"),
            usage=aggregate,
            usage_complete=usage_complete,
            cost_status=cost_status,
        )
        failure_context = execution.failure_context or {}
        payload = {
            "run_id": str(context.run_id),
            "trace_id": str(kw["trace_id"]),
            "project_id": str(kw["input_dto"].project_id),
            "agent_id": str(kw["agent"].id),
            "session_id": str(session.id),
            "error": str(kw["error"]),
            "failure_code": str(failure_context.get("phase") or "runtime_error"),
            "usage": aggregate.model_dump(),
            "tool_calls": [
                call.model_dump() if hasattr(call, "model_dump") else call
                for call in execution.tool_calls
            ],
            "llm_calls": list(execution.llm_calls),
            "diagnostics": metrics.diagnostics,
            "latency_ms": metrics.total_latency_ms,
            "completed_at": metrics.completed_at,
            "timeline_complete": False,
        }
        await owner._hot_terminal_pending(terminal_status="failed", result=payload)
        await recorder.emit("run.failed", payload, durable=True)
        context.terminal_persisted = True
        await owner._hot_persisted("failed")

    async def prepare_failure(
        self,
        owner: Any,
        *,
        input_dto: Any,
        error: Exception,
    ) -> bool:
        context, recorder = _recorder()
        payload = {
            "run_id": str(context.run_id),
            "trace_id": str(context.trace_id) if context.trace_id else None,
            "project_id": str(input_dto.project_id),
            "agent_id": str(context.agent_id or input_dto.agent_id),
            "session_id": str(recorder.session_id),
            "error": str(error),
            "failure_code": "prepare_failed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        await owner._hot_terminal_pending(terminal_status="failed", result=payload)
        await recorder.emit("run.failed", payload, durable=True)
        context.terminal_persisted = True
        await owner._hot_persisted("failed")
        return True
