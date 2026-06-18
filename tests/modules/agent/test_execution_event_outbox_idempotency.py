from __future__ import annotations

import uuid6

from modules.agent.domain.events import AgentExecutionLLMCompletedV1
from modules.agent.infra.messaging.event_mappers import domain_event_to_outbox


def _llm_event(trace_id: str, call_id: str) -> AgentExecutionLLMCompletedV1:
    return AgentExecutionLLMCompletedV1(
        payload={
            "trace_id": trace_id,
            "call_id": call_id,
            "call_index": 1,
        },
        idempotency_key="legacy-key",
        correlation_id=uuid6.uuid7(),
    )


def test_distinct_llm_calls_in_same_trace_have_distinct_outbox_keys():
    trace_id = str(uuid6.uuid7())

    first = domain_event_to_outbox(_llm_event(trace_id, "call-1"))
    second = domain_event_to_outbox(_llm_event(trace_id, "call-2"))

    assert first.idempotency_key != second.idempotency_key


def test_retry_of_same_llm_call_has_same_outbox_key():
    trace_id = str(uuid6.uuid7())

    first = domain_event_to_outbox(_llm_event(trace_id, "call-1"))
    retry = domain_event_to_outbox(_llm_event(trace_id, "call-1"))

    assert first.idempotency_key == retry.idempotency_key
