from __future__ import annotations

from uuid import uuid4

import pytest

from modules.network.application.runtime import (
    AgentInvocationResult,
    NetworkExecutionSnapshot,
)
from modules.network.infra.runtime.finalizer import _invocation_failure
from modules.network.infra.runtime.redis_store import RedisNetworkExecutionStore
from shared.infra.in_memory_execution_state import InMemoryExecutionStateStore


@pytest.mark.asyncio
async def test_network_store_keeps_invocations_context_cancel_and_terminal_state_outside_sql() -> None:
    state = InMemoryExecutionStateStore()
    store = RedisNetworkExecutionStore(state)
    execution_id = uuid4()
    network_session_id = uuid4()
    node_id = uuid4()
    agent_id = uuid4()
    existing_agent_session_id = uuid4()
    trace_id = uuid4()
    execution = NetworkExecutionSnapshot(
        id=execution_id,
        network_id=uuid4(),
        network_version_id=None,
        network_session_id=network_session_id,
        project_id=uuid4(),
        input_message="network input",
        draft_revision=3,
        definition_snapshot={"nodes": [], "edges": []},
        resolved_bindings_snapshot={
            str(node_id): {"release_id": None, "session_mode": "stateful"}
        },
        status="queued",
    )

    await store.initialize(
        execution,
        ttl_seconds=3600,
        agent_contexts={str(node_id): str(existing_agent_session_id)},
    )
    invocation = await store.start_invocation(
        execution=execution,
        node_id=node_id,
        agent_id=agent_id,
        depth=0,
        message="agent input",
        parent_invocation_id=None,
        persist_context=True,
    )

    assert invocation.agent_session_id == existing_agent_session_id

    new_agent_session_id = uuid4()
    invocation_result = AgentInvocationResult(
        answer="agent output",
        session_id=new_agent_session_id,
        trace_id=trace_id,
        provider="openai",
        model="test-model",
        usage={
            "input_tokens": 2,
            "output_tokens": 3,
            "total_tokens": 5,
            "cost_usd": 0.001,
        },
        tool_calls=[{"tool_name": "lookup", "success": True}],
        sources=[{"chunk_id": str(uuid4())}],
    )
    object.__setattr__(
        invocation_result,
        "diagnostics",
        {
            "schema_version": 5,
            "llm_work_latency_ms": 12,
            "usage_complete": True,
            "cost_status": "known",
            "cost_usd": 0.001,
        },
    )
    object.__setattr__(
        invocation_result,
        "llm_calls",
        [{"call_id": "llm-1", "latency_ms": 12, "cost_status": "known"}],
    )
    object.__setattr__(
        invocation_result,
        "started_at",
        "2026-08-25T12:00:00+00:00",
    )
    object.__setattr__(
        invocation_result,
        "completed_at",
        "2026-08-25T12:00:01+00:00",
    )
    await store.complete_invocation(
        invocation.id,
        result=invocation_result,
        persist_context=True,
    )

    invocations = await store.invocations(execution_id)
    assert len(invocations) == 1
    persisted = invocations[0]
    assert persisted["id"] == str(invocation.id)
    assert persisted["agent_run_id"] == str(invocation.id)
    assert persisted["status"] == "completed"
    assert persisted["output_message"] == "agent output"
    assert persisted["agent_session_id"] == str(new_agent_session_id)
    assert persisted["trace_id"] == str(trace_id)
    assert persisted["usage"]["total_tokens"] == 5
    assert persisted["tool_calls"][0]["tool_name"] == "lookup"
    assert persisted["diagnostics"]["schema_version"] == 5
    assert persisted["diagnostics"]["llm_work_latency_ms"] == 12
    assert persisted["llm_calls"][0]["call_id"] == "llm-1"
    assert persisted["started_at"] == "2026-08-25T12:00:00+00:00"
    assert persisted["completed_at"] == "2026-08-25T12:00:01+00:00"

    snapshot = await store.snapshot(execution_id)
    assert snapshot[f"agent_session:{node_id}"] == str(new_agent_session_id)
    assert snapshot["invocation_count"] == 1

    await store.request_cancel(execution_id)
    assert await store.is_cancel_requested(execution_id) is True

    await store.mark_terminal_pending(
        execution_id,
        status="completed",
        result={"output": "network output", "trace_id": str(trace_id)},
    )
    terminal = await store.snapshot(execution_id)
    assert terminal["status"] == "terminal_pending_persist"
    assert terminal["terminal_status"] == "completed"
    assert terminal["terminal_result"]["output"] == "network output"

    await store.mark_persisted(execution_id, status="completed")
    final_state = await store.snapshot(execution_id)
    assert final_state["status"] == "completed"
    assert final_state["phase"] == "persisted"


@pytest.mark.asyncio
async def test_network_store_uses_cached_invocation_identity_for_hot_events(monkeypatch) -> None:
    state = InMemoryExecutionStateStore()
    store = RedisNetworkExecutionStore(state)
    execution = NetworkExecutionSnapshot(
        id=uuid4(),
        network_id=uuid4(),
        network_version_id=None,
        network_session_id=uuid4(),
        project_id=uuid4(),
        input_message="network input",
        draft_revision=1,
        definition_snapshot={"nodes": [], "edges": []},
        resolved_bindings_snapshot={},
        status="queued",
    )
    node_id = uuid4()
    agent_id = uuid4()

    await store.initialize(execution, ttl_seconds=3600)
    invocation = await store.start_invocation(
        execution=execution,
        node_id=node_id,
        agent_id=agent_id,
        depth=0,
        message="agent input",
        parent_invocation_id=None,
        persist_context=False,
    )

    get_calls = 0
    original_get = state.get

    async def counting_get(run_id):
        nonlocal get_calls
        get_calls += 1
        return await original_get(run_id)

    published = []

    async def capture_publish(run_id, run_kind, event_type, payload, **kwargs):
        published.append((run_id, run_kind, event_type, dict(payload), kwargs))
        return "cursor"

    monkeypatch.setattr(state, "get", counting_get)
    monkeypatch.setattr(store._events, "publish", capture_publish)

    await store.emit(
        execution.id,
        "token",
        {
            "content": "A",
            "visibility": "assistant",
            "channel": "final",
            "phase": "response_generation",
        },
        invocation_id=invocation.id,
    )

    assert get_calls == 0
    payload = published[-1][3]
    assert payload["invocation_id"] == str(invocation.id)
    assert payload["node_id"] == str(node_id)
    assert payload["agent_id"] == str(agent_id)
    assert payload["depth"] == 0

    store._invocation_event_context.clear()
    await store.emit(
        execution.id,
        "agent_activity",
        {"status": "generating_answer"},
        invocation_id=invocation.id,
    )
    assert get_calls == 1

    await store.emit(
        execution.id,
        "agent_invocation_completed",
        {},
        invocation_id=invocation.id,
    )
    assert invocation.id not in store._invocation_event_context
    assert invocation.id not in store._invocation_to_execution


@pytest.mark.asyncio
async def test_network_store_captures_structured_failure_from_runtime_event() -> None:
    state = InMemoryExecutionStateStore()
    store = RedisNetworkExecutionStore(state)
    execution = NetworkExecutionSnapshot(
        id=uuid4(),
        network_id=uuid4(),
        network_version_id=None,
        network_session_id=uuid4(),
        project_id=uuid4(),
        input_message="network input",
        draft_revision=1,
        definition_snapshot={"nodes": [], "edges": []},
        resolved_bindings_snapshot={},
        status="queued",
    )
    node_id = uuid4()
    agent_id = uuid4()

    await store.initialize(execution, ttl_seconds=3600)
    invocation = await store.start_invocation(
        execution=execution,
        node_id=node_id,
        agent_id=agent_id,
        depth=0,
        message="agent input",
        parent_invocation_id=None,
        persist_context=False,
    )
    await store.fail_invocation(
        invocation.id,
        "ReadTimeout: provider exceeded request deadline",
    )
    await store.emit(
        execution.id,
        "agent_invocation_failed",
        {
            "code": "provider_timeout",
            "stage": "provider_request",
            "message": "The model provider did not answer before the timeout.",
            "retryable": True,
            "phase": "response_generation",
            "call_index": 1,
            "upstream_status": None,
            "upstream_error_code": None,
            "partial_result_available": False,
        },
        invocation_id=invocation.id,
    )

    persisted = (await store.invocations(execution.id))[0]
    assert persisted["failure"]["code"] == "provider_timeout"
    assert persisted["failure"]["stage"] == "provider_request"
    assert persisted["failure"]["retryable"] is True
    assert persisted["failure"]["phase"] == "response_generation"
    assert persisted["failure"]["call_index"] == 1
    assert persisted["failure"]["internal_detail"].startswith("ReadTimeout")
    assert persisted["failure"]["cause_invocation_id"] == str(invocation.id)
    assert persisted["failure"]["cause_node_id"] == str(node_id)
    assert persisted["failure"]["cause_agent_id"] == str(agent_id)


def test_finalizer_prefers_structured_failure_and_uses_network_failure_as_fallback() -> None:
    structured = _invocation_failure(
        {
            "failure": {
                "code": "provider_timeout",
                "stage": "provider_request",
                "message": "Provider timed out",
                "retryable": True,
                "internal_detail": "ReadTimeout: 30 seconds",
            }
        },
        terminal_failure_code="budget_exceeded",
        terminal_failure_detail="Network execution timeout exceeded",
    )
    assert structured["code"] == "provider_timeout"
    assert structured["internal_detail"] == "ReadTimeout: 30 seconds"

    fallback = _invocation_failure(
        {"error": None},
        terminal_failure_code="budget_exceeded",
        terminal_failure_detail="Network execution timeout exceeded",
    )
    assert fallback["code"] == "budget_exceeded"
    assert fallback["message"] == "Network execution timeout exceeded"
    assert fallback["internal_detail"] == "Network execution timeout exceeded"
