from dataclasses import dataclass

import pytest

from modules.agent.runtime.runtime_streaming import (
    RuntimeStreamChannel,
    current_runtime_stream,
    invoke_model_with_optional_streaming,
)


@dataclass
class Chunk:
    content: str

    def __add__(self, other: "Chunk") -> "Chunk":
        return Chunk(self.content + other.content)


class StreamingModel:
    async def astream(self, _messages):
        yield Chunk("hello ")
        yield Chunk("world")


class ToolFollowupStreamingModel:
    async def astream(self, _messages):
        yield Chunk("16<｜end")
        yield Chunk("▁of▁sentence｜>")


class NonStreamingModel:
    async def ainvoke(self, _messages):
        return Chunk("ok<|endoftext|>")


@pytest.mark.asyncio
async def test_runtime_stream_emits_progressive_tokens_and_ttft() -> None:
    channel = RuntimeStreamChannel()
    token = current_runtime_stream.set(channel)
    try:
        result = await invoke_model_with_optional_streaming(
            model=StreamingModel(),
            messages=[],
            phase="response_generation",
            provider="openai",
            model_name="gpt-test",
        )
    finally:
        current_runtime_stream.reset(token)

    activity = channel.queue.get_nowait()
    first = channel.queue.get_nowait()
    second = channel.queue.get_nowait()
    assert activity.event_type == "agent_activity"
    assert [first.event_type, second.event_type] == ["token", "token"]
    assert [first.payload["content"], second.payload["content"]] == [
        "hello ",
        "world",
    ]
    assert result.content == "hello world"
    assert channel.ttft_ms is not None


@pytest.mark.asyncio
async def test_tool_followup_is_emitted_as_final_without_provider_control_token() -> None:
    channel = RuntimeStreamChannel()
    token = current_runtime_stream.set(channel)
    try:
        result = await invoke_model_with_optional_streaming(
            model=ToolFollowupStreamingModel(),
            messages=[],
            phase="tool_followup_1",
            provider="openrouter",
            model_name="deepseek/deepseek-v4-flash",
        )
    finally:
        current_runtime_stream.reset(token)

    activity = channel.queue.get_nowait()
    visible = channel.queue.get_nowait()
    assert activity.event_type == "agent_activity"
    assert visible.event_type == "token"
    assert visible.payload["content"] == "16"
    assert visible.payload["phase"] == "tool_followup_1"
    assert result.content == "16"
    assert channel.queue.empty()


@pytest.mark.asyncio
async def test_non_streaming_response_removes_provider_control_token() -> None:
    result = await invoke_model_with_optional_streaming(
        model=NonStreamingModel(),
        messages=[],
        phase="response_generation",
        provider="openrouter",
        model_name="test-model",
    )

    assert result.content == "ok"


@pytest.mark.asyncio
async def test_runtime_stream_allows_exactly_one_terminal_event() -> None:
    channel = RuntimeStreamChannel()

    await channel.emit("done", answer="ok")
    await channel.emit("error", message="must be ignored")
    await channel.emit("token", content="must be ignored")

    terminal = channel.queue.get_nowait()
    assert terminal.event_type == "done"
    assert channel.queue.empty()
