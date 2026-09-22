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


@dataclass
class ToolSelectingChunk:
    content: str
    tool_calls: list[dict]

    def __add__(self, other: "ToolSelectingChunk") -> "ToolSelectingChunk":
        return ToolSelectingChunk(
            self.content + other.content,
            [*self.tool_calls, *other.tool_calls],
        )


class ToolSelectingStreamingModel:
    async def astream(self, _messages):
        yield ToolSelectingChunk("Vou procurar.", [])
        yield ToolSelectingChunk(
            "",
            [
                {
                    "id": "call-1",
                    "name": "lookup",
                    "args": {"query": "repo"},
                    "type": "tool_call",
                }
            ],
        )


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
    assert [event_type for event_type, _ in recorder.events] == [
        "output.delta.batch"
    ]
    payload = recorder.events[0][1]
    assert payload["content"] == "hello world"
    assert payload["channel"] == "final"
    assert payload["visibility"] == "assistant"
    assert payload["output_mode"] == "final"
    assert payload["phase"] == "response_generation"
    assert payload["message_id"] == str(context.output_message_id)


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
async def test_visible_pre_tool_text_is_promoted_to_intermediate_message() -> None:
    recorder = FakeRecorder()
    context = new_execution_context()
    context.run_event_recorder = recorder
    context_token = current_execution.set(context)
    channel = RuntimeStreamChannel()
    stream_token = current_runtime_stream.set(channel)
    try:
        result = await invoke_model_with_optional_streaming(
            model=ToolSelectingStreamingModel(),
            messages=[],
            phase="capability_response_generation",
            provider="openai",
            model_name="gpt-test",
        )
    finally:
        current_runtime_stream.reset(stream_token)
        current_execution.reset(context_token)

    events = []
    while not channel.queue.empty():
        events.append(channel.queue.get_nowait())

    assert [event.event_type for event in events] == [
        "agent_activity",
        "token",
        "assistant_message_completed",
        "token_retract",
    ]
    candidate = events[1]
    promoted = events[2]
    retracted = events[3]
    assert candidate.payload["content"] == "Vou procurar."
    assert candidate.payload["output_mode"] == "final"
    assert promoted.payload["content"] == "Vou procurar."
    assert promoted.payload["output_mode"] == "intermediate"
    assert promoted.payload["message_id"] != candidate.payload["message_id"]
    assert retracted.payload["message_id"] == candidate.payload["message_id"]
    assert retracted.payload["reason"] == "tool_call_selected"
    assert context.output_message_id is not None
    assert promoted.payload["message_id"] != str(context.output_message_id)
    assert channel.public_output == ""
    assert context.intermediate_messages == [
        {
            "message_id": promoted.payload["message_id"],
            "content": "Vou procurar.",
            "phase": "capability_response_generation",
            "output_mode": "intermediate",
            "provider": "openai",
            "model": "gpt-test",
            "partial": False,
            "completed_at": promoted.payload["completed_at"],
        }
    ]
    assert [event_type for event_type, _ in recorder.events] == [
        "output.delta.batch",
        "assistant.message.completed",
        "output.retracted",
    ]
    assert result.tool_calls[0]["name"] == "lookup"


@pytest.mark.asyncio
async def test_multiple_promotions_keep_distinct_messages_and_one_terminal_id() -> None:
    recorder = FakeRecorder()
    context = new_execution_context()
    context.run_event_recorder = recorder
    context_token = current_execution.set(context)
    channel = RuntimeStreamChannel()
    stream_token = current_runtime_stream.set(channel)
    try:
        await invoke_model_with_optional_streaming(
            model=ToolSelectingStreamingModel(),
            messages=[],
            phase="capability_response_generation",
            provider="openai",
            model_name="gpt-test",
        )
        await invoke_model_with_optional_streaming(
            model=ToolSelectingStreamingModel(),
            messages=[],
            phase="tool_followup_1",
            provider="openai",
            model_name="gpt-test",
        )
        await invoke_model_with_optional_streaming(
            model=StreamingModel(),
            messages=[],
            phase="tool_followup_2",
            provider="openai",
            model_name="gpt-test",
        )
    finally:
        current_runtime_stream.reset(stream_token)
        current_execution.reset(context_token)

    assert context.output_message_id is not None
    assert context.intermediate_messages is not None
    assert len(context.intermediate_messages) == 2
    intermediate_ids = {
        item["message_id"] for item in context.intermediate_messages
    }
    assert len(intermediate_ids) == 2
    assert str(context.output_message_id) not in intermediate_ids

    events = []
    while not channel.queue.empty():
        events.append(channel.queue.get_nowait())
    completed = [
        event for event in events
        if event.event_type == "assistant_message_completed"
    ]
    final_tokens = [
        event for event in events
        if event.event_type == "token"
        and event.payload.get("phase") == "tool_followup_2"
    ]
    assert len(completed) == 2
    assert {event.payload["message_id"] for event in completed} == intermediate_ids
    assert final_tokens
    assert {
        event.payload["message_id"] for event in final_tokens
    } == {str(context.output_message_id)}
    assert channel.public_output == "hello world"


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


@pytest.mark.asyncio
async def test_strategy_specific_phase_can_explicitly_own_public_output() -> None:
    channel = RuntimeStreamChannel()
    token = current_runtime_stream.set(channel)
    try:
        result = await invoke_model_with_optional_streaming(
            model=StreamingModel(),
            messages=[],
            phase="conclusion",
            provider="openai",
            model_name="gpt-test",
            output_mode="final",
        )
    finally:
        current_runtime_stream.reset(token)

    activity = channel.queue.get_nowait()
    first = channel.queue.get_nowait()
    second = channel.queue.get_nowait()
    assert activity.event_type == "agent_activity"
    assert activity.payload["status"] == "generating_answer"
    assert activity.payload["phase"] == "conclusion"
    assert activity.payload["message"] == "Generating conclusion..."
    assert [first.event_type, second.event_type] == ["token", "token"]
    assert first.payload["message_id"] == second.payload["message_id"]
    assert first.payload["output_mode"] == "final"
    assert result.content == "hello world"


@pytest.mark.asyncio
async def test_intermediate_output_is_a_distinct_message_and_does_not_become_run_output() -> None:
    context = new_execution_context()
    context_token = current_execution.set(context)
    channel = RuntimeStreamChannel()
    stream_token = current_runtime_stream.set(channel)
    try:
        result = await invoke_model_with_optional_streaming(
            model=StreamingModel(),
            messages=[],
            phase="progress_update",
            provider="openai",
            model_name="gpt-test",
            output_mode="intermediate",
        )
    finally:
        current_runtime_stream.reset(stream_token)
        current_execution.reset(context_token)

    events = []
    while not channel.queue.empty():
        events.append(channel.queue.get_nowait())
    assert [event.event_type for event in events] == [
        "agent_activity",
        "assistant_message_delta",
        "assistant_message_delta",
        "assistant_message_completed",
    ]
    first_delta = events[1]
    second_delta = events[2]
    completed = events[3]
    assert first_delta.payload["message_id"] == second_delta.payload["message_id"]
    assert completed.payload["message_id"] == first_delta.payload["message_id"]
    assert completed.payload["content"] == "hello world"
    assert completed.payload["output_mode"] == "intermediate"
    assert channel.public_output == ""
    assert context.intermediate_messages == [
        {
            "message_id": completed.payload["message_id"],
            "content": "hello world",
            "phase": "progress_update",
            "output_mode": "intermediate",
            "provider": "openai",
            "model": "gpt-test",
            "partial": False,
            "completed_at": completed.payload["completed_at"],
        }
    ]
    assert result.content == "hello world"


@pytest.mark.asyncio
async def test_strategy_specific_internal_phase_exposes_phase_activity_without_output() -> None:
    channel = RuntimeStreamChannel()
    token = current_runtime_stream.set(channel)
    try:
        result = await invoke_model_with_optional_streaming(
            model=StreamingModel(),
            messages=[],
            phase="hypothesis_formulation",
            provider="openai",
            model_name="gpt-test",
            output_mode="internal",
        )
    finally:
        current_runtime_stream.reset(token)

    activity = channel.queue.get_nowait()
    assert activity.event_type == "agent_activity"
    assert activity.payload["status"] == "thinking"
    assert activity.payload["phase"] == "hypothesis_formulation"
    assert activity.payload["message"] == "Hypothesis formulation..."
    assert result.content == "hello world"
    assert channel.queue.empty()
