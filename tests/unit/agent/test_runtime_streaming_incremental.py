from __future__ import annotations

import asyncio

import pytest

from modules.agent.infra.execution.runtime_streaming import (
    RuntimeStreamChannel,
    current_runtime_stream,
    invoke_model_with_optional_streaming,
)


class _Chunk:
    def __init__(
        self,
        content: str = "",
        *,
        tool_calls: list[dict] | None = None,
        tool_call_chunks: list[dict] | None = None,
    ) -> None:
        self.content = content
        self.tool_calls = list(tool_calls or [])
        self.tool_call_chunks = list(tool_call_chunks or [])

    def __add__(self, other: "_Chunk") -> "_Chunk":
        return _Chunk(
            self.content + other.content,
            tool_calls=[*self.tool_calls, *other.tool_calls],
            tool_call_chunks=[*self.tool_call_chunks, *other.tool_call_chunks],
        )


class _ControlledModel:
    def __init__(self, *, first: str, second: _Chunk) -> None:
        self.first = first
        self.second = second
        self.release = asyncio.Event()
        self.waiting = asyncio.Event()

    async def astream(self, _messages):
        yield _Chunk(self.first)
        self.waiting.set()
        await self.release.wait()
        yield self.second


async def _next_event(channel: RuntimeStreamChannel, event_type: str):
    while True:
        event = await asyncio.wait_for(channel.queue.get(), timeout=1)
        if event.event_type == event_type:
            return event


@pytest.mark.asyncio
async def test_tool_followup_streams_before_provider_completion() -> None:
    channel = RuntimeStreamChannel()
    model = _ControlledModel(first="Hello", second=_Chunk(" world"))
    context_token = current_runtime_stream.set(channel)

    try:
        task = asyncio.create_task(
            invoke_model_with_optional_streaming(
                model=model,
                messages=[],
                phase="tool_followup_1",
                provider="test-provider",
                model_name="test-model",
            )
        )

        await asyncio.wait_for(model.waiting.wait(), timeout=1)
        event = await _next_event(channel, "token")

        assert event.payload["content"] == "Hello"
        assert event.payload["phase"] == "tool_followup_1"
        assert task.done() is False
        assert channel.public_output == "Hello"

        model.release.set()
        result = await asyncio.wait_for(task, timeout=1)
        assert result.content == "Hello world"

        trailing = await _next_event(channel, "token")
        assert trailing.payload["content"] == " world"
        assert channel.public_output == "Hello world"
    finally:
        model.release.set()
        current_runtime_stream.reset(context_token)


@pytest.mark.asyncio
async def test_capability_response_is_buffered_until_provider_decides_no_tool_call() -> None:
    channel = RuntimeStreamChannel()
    model = _ControlledModel(first="Hello", second=_Chunk(" world"))
    context_token = current_runtime_stream.set(channel)

    try:
        task = asyncio.create_task(
            invoke_model_with_optional_streaming(
                model=model,
                messages=[],
                phase="capability_response_generation",
                provider="test-provider",
                model_name="test-model",
            )
        )

        await asyncio.wait_for(model.waiting.wait(), timeout=1)
        activity = await asyncio.wait_for(channel.queue.get(), timeout=1)
        assert activity.event_type == "agent_activity"
        assert task.done() is False
        assert channel.public_output == ""
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(channel.queue.get(), timeout=0.05)

        model.release.set()
        result = await asyncio.wait_for(task, timeout=1)
        assert result.content == "Hello world"

        first = await _next_event(channel, "token")
        second = await _next_event(channel, "token")
        assert first.payload["content"] == "Hello"
        assert second.payload["content"] == " world"
        assert channel.public_output == "Hello world"
    finally:
        model.release.set()
        current_runtime_stream.reset(context_token)


@pytest.mark.asyncio
async def test_capability_text_is_never_published_when_tool_call_is_selected() -> None:
    channel = RuntimeStreamChannel()
    model = _ControlledModel(
        first="I will check that.",
        second=_Chunk(
            "",
            tool_calls=[{"name": "lookup_order", "args": {"id": "123"}}],
        ),
    )
    context_token = current_runtime_stream.set(channel)

    try:
        task = asyncio.create_task(
            invoke_model_with_optional_streaming(
                model=model,
                messages=[],
                phase="capability_response_generation",
                provider="test-provider",
                model_name="test-model",
            )
        )

        await asyncio.wait_for(model.waiting.wait(), timeout=1)
        activity = await asyncio.wait_for(channel.queue.get(), timeout=1)
        assert activity.event_type == "agent_activity"
        assert channel.public_output == ""

        model.release.set()
        result = await asyncio.wait_for(task, timeout=1)
        assert result.tool_calls
        assert channel.public_output == ""

        remaining = []
        while not channel.queue.empty():
            remaining.append(channel.queue.get_nowait().event_type)
        assert "token" not in remaining
        assert "token_retract" not in remaining
    finally:
        model.release.set()
        current_runtime_stream.reset(context_token)
