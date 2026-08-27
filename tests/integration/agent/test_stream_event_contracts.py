from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage

from modules.agent.infra.execution.execution_instrumentation import (
    execute_tool_call,
)
from modules.agent.infra.execution.instrumented_fallback_mixin import (
    InstrumentedFallbackMixin,
)
from modules.agent.infra.execution.runtime_streaming import (
    RuntimeStreamChannel,
    current_runtime_stream,
)


class _FallbackModel:
    async def ainvoke(self, _messages):
        result = AIMessage(content="fallback answer")
        result.usage_metadata = {
            "input_tokens": 3,
            "output_tokens": 2,
            "total_tokens": 5,
        }
        return result


class _FallbackFactory:
    def create_chat_model(self, **_kwargs):
        return _FallbackModel()


class FallbackRuntime(InstrumentedFallbackMixin):
    def __init__(self) -> None:
        self._llm_factory = _FallbackFactory()


@pytest.mark.asyncio
async def test_runtime_stream_terminal_contract() -> None:
    channel = RuntimeStreamChannel()
    await channel.emit("done", answer="ok")
    await channel.emit("error", message="ignored")
    event = channel.queue.get_nowait()
    assert event.event_type == "done"
    assert channel.queue.empty()


@pytest.mark.asyncio
async def test_fallback_event_precedes_fallback_execution() -> None:
    channel = RuntimeStreamChannel()
    token = current_runtime_stream.set(channel)
    try:
        agent = SimpleNamespace(
            provider="primary-provider",
            model="primary-model",
            fallback_provider="compatible-provider",
            fallback_model="fallback-model",
            fallback_credential_id=None,
            fallback_provider_model_id=None,
            temperature=0.2,
            max_output_tokens=128,
            settings={},
        )
        result, provider, latency, info = await FallbackRuntime()._try_fallback(
            agent,
            [],
            False,
            RuntimeError("primary unavailable"),
        )
    finally:
        current_runtime_stream.reset(token)

    event = channel.queue.get_nowait()
    assert event.event_type == "fallback"
    assert event.payload["primary_model"] == "primary-model"
    assert event.payload["fallback_model"] == "fallback-model"
    assert event.payload["error"] == "primary unavailable"
    assert result.content == "fallback answer"
    assert provider == "compatible-provider"
    assert latency >= 0
    assert info["primary_model"] == "primary-model"
    assert info["fallback_model"] == "fallback-model"
    assert info["fallback_provider"] == "compatible-provider"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("result_payload", "expected_status", "expected_success"),
    [
        ({"success": True, "output": {"result": 3}}, "success", True),
        ({"success": False, "error": "execution failed"}, "error", False),
    ],
)
async def test_tool_events_are_ordered_and_truthful(
    result_payload,
    expected_status,
    expected_success,
) -> None:
    channel = RuntimeStreamChannel()
    token = current_runtime_stream.set(channel)

    async def execute(_call, _resolved_id):
        return result_payload

    try:
        info, message, payload = await execute_tool_call(
            execute=execute,
            tool_call={
                "id": "call-1",
                "name": "sum_numbers",
                "args": {"a": 1, "b": 2},
            },
            resolved_tool_id="tool-id",
        )
    finally:
        current_runtime_stream.reset(token)

    events = []
    while not channel.queue.empty():
        events.append(channel.queue.get_nowait())

    assert [event.event_type for event in events] == [
        "agent_activity",
        "tool_call_started",
        "tool_call_completed",
        "agent_activity",
    ]
    assert events[0].payload["status"] == "calling_tool"
    assert events[3].payload["status"] == "processing_tool_result"

    started = events[1]
    completed = events[2]
    assert started.payload["status"] == "running"
    assert completed.payload["status"] == expected_status
    assert completed.payload["success"] is expected_success
    assert info.success is expected_success
    assert payload["status"] == expected_status
    assert message.tool_call_id == "call-1"
