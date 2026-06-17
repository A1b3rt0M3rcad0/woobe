from __future__ import annotations

from typing import Any, Callable
from uuid import UUID

from modules.agent.domain.events import AgentDomainEvent
from modules.agent.infra.database.repositories import SQLAlchemyAgentOutboxEventWriter
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork


class StructuredOutputEventPublisher:
    """Publish structured-output parsing results after execution commit."""

    EVENT_TYPE = "agent.execution.output_parsed.v1"

    def __init__(self, session_factory: Callable[..., Any]) -> None:
        self._session_factory = session_factory

    async def publish(
        self,
        *,
        project_id: UUID,
        agent_id: UUID,
        session_id: UUID | None,
        done_payload: dict[str, Any],
    ) -> None:
        trace_id_raw = done_payload.get("trace_id")
        if not trace_id_raw:
            return

        parsed_output = done_payload.get("parsed_output")
        output_parse_error = done_payload.get("output_parse_error")
        if parsed_output is None and output_parse_error is None:
            return

        trace_id = UUID(str(trace_id_raw))
        payload = {
            "trace_id": str(trace_id),
            "project_id": str(project_id),
            "agent_id": str(agent_id),
            "session_id": str(session_id) if session_id else None,
            "parsed_output": parsed_output,
            "output_parse_error": output_parse_error,
        }
        event = AgentDomainEvent(
            event_type=self.EVENT_TYPE,
            routing_key=self.EVENT_TYPE,
            payload=payload,
            idempotency_key=AgentDomainEvent.compute_idempotency_key(
                aggregate_type="agent",
                aggregate_id=agent_id,
                event_type=self.EVENT_TYPE,
                discriminator=str(trace_id),
            ),
        )

        async with AgentUnitOfWork(self._session_factory) as uow:
            outbox = SQLAlchemyAgentOutboxEventWriter(uow)
            await outbox.write(event)
