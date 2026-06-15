from __future__ import annotations

import importlib
import logging
import uuid
from uuid import UUID

from modules.agent.domain.ports.trace_recorder import TraceRecorder

logger = logging.getLogger(__name__)


class ObservabilityTraceRecorder(TraceRecorder):

    def __init__(self, uow: object) -> None:
        self._uow = uow

    async def create_trace(
        self,
        project_id: UUID,
        agent_id: UUID,
        session_id: UUID | None,
        tenant_id: UUID | None,
        user_id: UUID | None,
        provider: str,
        model: str,
        trace_id: UUID | None = None,
    ) -> UUID:
        try:
            obs_entities = importlib.import_module("modules.observability.domain.entities")
            obs_enums = importlib.import_module("modules.observability.domain.enums")
            repos_mod = importlib.import_module("modules.observability.infra.database.repositories")

            trace = obs_entities.Trace(
                project_id=project_id,
                agent_id=agent_id,
                session_id=session_id,
                tenant_id=tenant_id,
                user_id=user_id,
                status=obs_enums.TraceStatus.running,
                provider=provider,
                model=model,
            )
            saved = await repos_mod.SQLAlchemyTraceRepository(self._uow).save(trace)
            return saved.id
        except Exception:
            logger.exception("Failed to create trace")
            raise

    async def record_event(
        self,
        trace_id: UUID,
        project_id: UUID,
        event_type: str,
        latency_ms: float | None = None,
        payload: dict | None = None,
    ) -> None:
        try:
            obs_entities = importlib.import_module("modules.observability.domain.entities")
            repos_mod = importlib.import_module("modules.observability.infra.database.repositories")

            event = obs_entities.TraceEvent(
                trace_id=trace_id,
                project_id=project_id,
                event_type=event_type,
                latency_ms=latency_ms,
                payload=payload or {},
            )
            await repos_mod.SQLAlchemyTraceEventRepository(self._uow).save(event)
        except Exception:
            logger.exception("Failed to record trace event")

    async def fail_trace(self, trace_id: UUID, error: str) -> None:
        try:
            obs_enums = importlib.import_module("modules.observability.domain.enums")
            repos_mod = importlib.import_module("modules.observability.infra.database.repositories")

            repo = repos_mod.SQLAlchemyTraceRepository(self._uow)
            trace = await repo.get_by_id(trace_id)
            if trace:
                trace.status = obs_enums.TraceStatus.failed
                trace.error = error
                await repo.save(trace)
        except Exception:
            logger.exception("Failed to fail trace")

    async def complete_trace(
        self,
        trace_id: UUID,
        answer: str,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
        cost_usd: float,
        model: str,
        provider: str,
        latency_ms: float | None = None,
        message_id: UUID | None = None,
        sources: list | None = None,
        parsed_output: dict | None = None,
        output_parse_error: str | None = None,
        tool_calls: list | None = None,
        fallback_used: bool = False,
        fallback_info: dict | None = None,
        json_format_latency_ms: int | None = None,
    ) -> None:
        try:
            obs_enums = importlib.import_module("modules.observability.domain.enums")
            obs_entities = importlib.import_module("modules.observability.domain.entities")
            repos_mod = importlib.import_module("modules.observability.infra.database.repositories")

            repo = repos_mod.SQLAlchemyTraceRepository(self._uow)
            trace = await repo.get_by_id(trace_id)
            if trace:
                trace.status = obs_enums.TraceStatus.completed
                trace.total_latency_ms = latency_ms
                trace.model = model
                trace.provider = provider
                trace.fallback_used = fallback_used
                data = {
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": total_tokens,
                    "cost_usd": cost_usd,
                    "sources": [s.model_dump() for s in sources] if sources else None,
                    "tool_calls": tool_calls or None,
                    "parsed_output": parsed_output,
                    "output_parse_error": output_parse_error,
                    "json_format_latency_ms": json_format_latency_ms,
                }
                if fallback_info:
                    data["fallback_info"] = fallback_info
                trace.data = data
                await repo.save(trace)

            event = obs_entities.TraceEvent(
                trace_id=trace_id,
                project_id=trace.project_id if trace else uuid.uuid4(),
                event_type=obs_enums.TraceEventType.info,
                latency_ms=latency_ms,
                payload={
                    "event": "ask.completed",
                    "answer_length": len(answer),
                    "message_id": str(message_id) if message_id else None,
                },
            )
            if fallback_info:
                event.payload["fallback_info"] = fallback_info
            await repos_mod.SQLAlchemyTraceEventRepository(self._uow).save(event)
        except Exception:
            logger.exception("Failed to complete trace")
