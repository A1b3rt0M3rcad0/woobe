from uuid import uuid4

from modules.agent.application.use_cases.execution_event_factory import (
    llm_event,
    tool_event,
)


def test_per_call_event_keys_are_unique():
    agent_id = uuid4()
    first = llm_event(
        agent_id,
        {"trace_id": "trace", "call_id": "one"},
    )
    second = llm_event(
        agent_id,
        {"trace_id": "trace", "call_id": "two"},
    )
    tool = tool_event(
        agent_id,
        {"trace_id": "trace", "tool_call_id": "tool"},
    )
    assert first.idempotency_key != second.idempotency_key
    assert first.idempotency_key != tool.idempotency_key
