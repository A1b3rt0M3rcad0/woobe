from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage

from modules.agent.application.use_cases.instrumented_fallback_mixin import (
    InstrumentedFallbackMixin,
)
from modules.agent.application.use_cases.runtime_streaming import (
    RuntimeStreamChannel,
    current_runtime_stream,
)


class ParentFallback:
    async def _try_fallback(self, agent, messages, json_enabled, primary_error):
        result = AIMessage(content="fallback answer")
        result.usage_metadata = {
            "input_tokens": 3,
            "output_tokens": 2,
            "total_tokens": 5,
        }
        return result, "compatible-provider", 12, {"used": True}


class FallbackRuntime(InstrumentedFallbackMixin, ParentFallback):
    pass


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
    assert latency == 12
    assert info == {"used": True}
