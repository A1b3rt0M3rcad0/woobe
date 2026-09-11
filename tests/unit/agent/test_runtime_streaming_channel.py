from dataclasses import dataclass

import pytest

from modules.agent.application.interfaces.execution_context import (
    current_execution,
    new_execution_context,
)
from modules.agent.infra.execution.runtime_streaming import (
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


class FakeRecorder:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    async def emit(self, event_type: str, payload: dict | None = None, **_kwargs):
        self.events.append((event_type, dict(payload or {})))
        return None


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
async def test_runtime_stream_journals_visible_output_as_bounded_batch() -> None:
    recorder = FakeRecorder()
    context = new_execution_context()
    context.run_event_recorder = recorder
    context_token = current_execution.set(context)
    channel = RuntimeStreamChannel()
    stream_token = current_runtime_stream.set(channel)
    try:
        result = await invoke_model_with_optional_streaming(
            model=StreamingModel(),
            messages=[],
            phase="response_generation",
            provider="openai",
            model_name="gpt-test",
        )
    finally:
        current_runtime_stream.reset(stream_token)
        current_execution.reset(context_token)

    assert result.content == "hello world"
    assert recorder.events == [
        (
            "output.delta.batch",
            {
                "content": "hello world",
                "channel": "final",
                "visibility": "assistant",
            },
        )
    ]


@pytest.mark.asyncio
async def test_runtime_stream_journals_retraction_after_visible_output() -> None:
    recorder = FakeRecorder()
    context = new_execution_context()
    context.run_event_recorder = recorder
    context_token = current_execution.set(context)
    channel = RuntimeStreamChannel()
    try:
        await channel.append_durable_output("candidate")
        await channel.retract_durable_output(
            content_length=len("candidate"),
            token_count=1,
            phase="capability_response_generation",
            reason="tool_call_selected",
            provider="openai",
            model_name="gpt-test",
        )
    finally:
        current_execution.reset(context_token)

    assert [event_type for event_type, _ in recorder.events] == [
        "output.delta.batch",
        "output.retracted",
    ]
    assert recorder.events[0][1]["content"] == "candidate"
    assert recorder.events[1][1]["content_length"] == len("candidate")
    assert recorder.events[1][1]["reason"] == "tool_call_selected"


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
