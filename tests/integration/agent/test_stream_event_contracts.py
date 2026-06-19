import pytest

from modules.agent.application.use_cases.runtime_streaming import RuntimeStreamChannel


@pytest.mark.asyncio
async def test_runtime_stream_terminal_contract() -> None:
    channel = RuntimeStreamChannel()
    await channel.emit("done", answer="ok")
    await channel.emit("error", message="ignored")
    event = channel.queue.get_nowait()
    assert event.event_type == "done"
    assert channel.queue.empty()
