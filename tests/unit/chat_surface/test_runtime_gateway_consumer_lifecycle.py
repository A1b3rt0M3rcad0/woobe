from __future__ import annotations

from uuid import uuid4

import pytest

from modules.chat_surface.application.runtime_gateway import (
    ChatRuntimeChunk,
    PreparedChatRuntime,
)
from modules.chat_surface.presentation.routes import _consume_runtime_stream


class _Service:
    def __init__(self) -> None:
        self.marked: list[tuple[object, dict]] = []

    async def mark_message(self, message_id, **kwargs) -> None:
        self.marked.append((message_id, kwargs))


@pytest.mark.asyncio
async def test_observer_end_without_terminal_does_not_terminalize_message() -> None:
    message_id = uuid4()
    run_id = uuid4()
    service = _Service()

    async def chunks():
        yield ChatRuntimeChunk(
            sse="event: token\ndata: {}\n\n",
            run_id=run_id,
        )

    prepared = PreparedChatRuntime(stream=chunks(), run_id=run_id)
    observed = [
        chunk
        async for chunk in _consume_runtime_stream(
            service,
            message_request_id=message_id,
            prepared=prepared,
        )
    ]

    assert observed == ["event: token\ndata: {}\n\n"]
    assert service.marked == [
        (
            message_id,
            {
                "status": "streaming",
                "target_run_id": run_id,
                "error_code": None,
            },
        )
    ]


@pytest.mark.asyncio
async def test_terminal_runtime_fact_terminalizes_message() -> None:
    message_id = uuid4()
    run_id = uuid4()
    service = _Service()

    async def chunks():
        yield ChatRuntimeChunk(
            sse="event: done\ndata: {}\n\n",
            run_id=run_id,
            terminal_status="completed",
        )

    prepared = PreparedChatRuntime(stream=chunks(), run_id=run_id)
    _ = [
        chunk
        async for chunk in _consume_runtime_stream(
            service,
            message_request_id=message_id,
            prepared=prepared,
        )
    ]

    assert service.marked == [
        (
            message_id,
            {
                "status": "streaming",
                "target_run_id": run_id,
                "error_code": None,
            },
        ),
        (
            message_id,
            {
                "status": "completed",
                "target_run_id": run_id,
                "error_code": None,
            },
        ),
    ]
