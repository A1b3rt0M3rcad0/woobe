from __future__ import annotations

import uuid6

from modules.agent.domain.events import (
    AgentDomainEvent,
    AgentExecutionCompletedV1,
    AgentExecutionLLMCompletedV1,
    AgentExecutionToolCompletedV1,
    AgentFallbackTriggeredV1,
)


def _make(cls, agent_id, payload, discriminator):
    key = AgentDomainEvent.compute_idempotency_key(
        "agent", agent_id, cls.event_type, discriminator
    )
    return cls(
        payload=payload,
        idempotency_key=key,
        correlation_id=uuid6.uuid7(),
    )


def llm_event(agent_id, payload):
    marker = payload.get("call_id") or payload.get("call_index")
    return _make(
        AgentExecutionLLMCompletedV1,
        agent_id,
        payload,
        f"{payload.get('trace_id')}:{marker}",
    )


def tool_event(agent_id, payload):
    return _make(
        AgentExecutionToolCompletedV1,
        agent_id,
        payload,
        f"{payload.get('trace_id')}:{payload.get('tool_call_id')}",
    )


def completed_event(agent_id, payload):
    return _make(
        AgentExecutionCompletedV1,
        agent_id,
        payload,
        str(payload.get("trace_id")),
    )


def fallback_event(agent_id, payload):
    return _make(
        AgentFallbackTriggeredV1,
        agent_id,
        payload,
        str(payload.get("trace_id")),
    )
