from dataclasses import dataclass

import pytest

from modules.agent.application.use_cases.runtime_streaming import (
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

    first = channel.queue.get_nowait()
    second = channel.queue.get_nowait()
    assert [first.event_type, second.event_type] == ["token", "token"]
    assert [first.payload["content"], second.payload["content"]] == [
        "hello ",
        "world",
    ]
    assert result.content == "hello world"
    assert channel.ttft_ms is not None


@pytest.mark.asyncio
async def test_runtime_stream_allows_exactly_one_terminal_event() -> None:
    channel = RuntimeStreamChannel()

    await channel.emit("done", answer="ok")
    await channel.emit("error", message="must be ignored")
    await channel.emit("token", content="must be ignored")

    terminal = channel.queue.get_nowait()
    assert terminal.event_type == "done"
    assert channel.queue.empty()
