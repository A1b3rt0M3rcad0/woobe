from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

import uuid6

from modules.agent.domain.events import AgentDomainEvent


@dataclass(frozen=True)
class AgentExecutionCancelledV1(AgentDomainEvent):
    event_type: str = "agent.execution.cancelled.v1"
    event_version: int = 1
    routing_key: str = "agent.execution.cancelled.v1"

    @classmethod
    def create(
        cls,
        *,
        agent_id: UUID,
        session_id: UUID | None,
        payload: dict[str, Any],
        correlation_id: UUID | None = None,
        causation_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AgentExecutionCancelledV1:
        trace_id = str(payload.get("trace_id") or "")
        return cls(
            payload=payload,
            idempotency_key=cls.compute_idempotency_key(
                aggregate_type="agent",
                aggregate_id=agent_id,
                event_type="agent.execution.cancelled.v1",
                discriminator=trace_id or str(session_id),
            ),
            correlation_id=correlation_id or uuid6.uuid7(),
            causation_id=causation_id,
            metadata=metadata,
        )
