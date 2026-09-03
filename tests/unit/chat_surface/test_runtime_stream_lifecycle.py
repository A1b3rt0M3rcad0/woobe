from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.chat_surface.application.runtime_gateway import (
    ChatRuntimeChunk,
    PreparedChatRuntime,
)
from modules.chat_surface.presentation import reattach_routes


class _SurfaceService:
    def __init__(self) -> None:
        self.marked: list[tuple[object, dict]] = []

    async def mark_message(self, message_id, **kwargs) -> None:
        self.marked.append((message_id, kwargs))


class _Gateway:
    def __init__(self, prepared: PreparedChatRuntime) -> None:
        self.prepared = prepared
        self.observed = []

    async def observe(self, target, run_id, disconnect_check):
        self.observed.append((target, run_id, disconnect_check))
        return self.prepared


class _Request:
    def __init__(self, gateway: _Gateway, *, disconnected: bool = False) -> None:
        self.disconnected = disconnected
        self.app = SimpleNamespace(
            state=SimpleNamespace(chat_surface_runtime_gateway=gateway)
        )

    async def is_disconnected(self) -> bool:
        return self.disconnected


def _authorized(*, project_id, agent_id, session_id, release_id):
    return SimpleNamespace(
        binding=SimpleNamespace(
            target_type="agent",
            project_id=project_id,
            target_id=agent_id,
            session_id=session_id,
            target_release_id=release_id,
        )
    )


@pytest.mark.asyncio
async def test_chat_surface_observer_marks_message_cancelled_only_after_terminal_run_state(monkeypatch) -> None:
    run_id = uuid4()
    project_id = uuid4()
    agent_id = uuid4()
    session_id = uuid4()
    release_id = uuid4()
    message_request = SimpleNamespace(id=uuid4())
    authorized = _authorized(
        project_id=project_id,
        agent_id=agent_id,
        session_id=session_id,
        release_id=release_id,
    )

    async def active_request(*_args, **_kwargs):
        return authorized, message_request, run_id, "cancel_requested"

    async def chunks():
        yield ChatRuntimeChunk(
            sse=(
                "event: run.state\n"
                f'data: {{"type":"run.state","run_id":"{run_id}","status":"cancelled"}}\n\n'
            ),
            run_id=run_id,
            terminal_status="cancelled",
        )

    prepared = PreparedChatRuntime(stream=chunks(), run_id=run_id)
    gateway = _Gateway(prepared)
    service = _SurfaceService()
    monkeypatch.setattr(reattach_routes, "_authorized_active_request", active_request)
    monkeypatch.setattr(reattach_routes, "_service", lambda _request: service)

    request = _Request(gateway)
    response = await reattach_routes.stream_chat_active_run(session_id, request)
    observed = []
    async for chunk in response.body_iterator:
        observed.append(chunk.decode() if isinstance(chunk, bytes) else str(chunk))

    assert response.headers["cache-control"] == "no-cache, no-transform"
    assert response.headers["x-accel-buffering"] == "no"
    assert any('"status":"cancelled"' in chunk for chunk in observed)
    assert len(gateway.observed) == 1
    assert service.marked == [
        (
            message_request.id,
            {
                "status": "streaming",
                "target_run_id": run_id,
                "error_code": None,
            },
        ),
        (
            message_request.id,
            {
                "status": "cancelled",
                "target_run_id": run_id,
                "error_code": None,
            },
        ),
    ]


@pytest.mark.asyncio
async def test_chat_surface_transport_disconnect_does_not_terminalize_message_request(monkeypatch) -> None:
    run_id = uuid4()
    project_id = uuid4()
    agent_id = uuid4()
    session_id = uuid4()
    release_id = uuid4()
    message_request = SimpleNamespace(id=uuid4())
    authorized = _authorized(
        project_id=project_id,
        agent_id=agent_id,
        session_id=session_id,
        release_id=release_id,
    )

    async def active_request(*_args, **_kwargs):
        return authorized, message_request, run_id, "running"

    async def chunks():
        yield ChatRuntimeChunk(
            sse="event: token\ndata: {\"type\":\"token\",\"content\":\"partial\"}\n\n",
            run_id=run_id,
        )

    prepared = PreparedChatRuntime(stream=chunks(), run_id=run_id)
    gateway = _Gateway(prepared)
    service = _SurfaceService()
    monkeypatch.setattr(reattach_routes, "_authorized_active_request", active_request)
    monkeypatch.setattr(reattach_routes, "_service", lambda _request: service)

    response = await reattach_routes.stream_chat_active_run(
        session_id,
        _Request(gateway, disconnected=True),
    )
    async for _ in response.body_iterator:
        pass

    assert service.marked == [
        (
            message_request.id,
            {
                "status": "streaming",
                "target_run_id": run_id,
                "error_code": None,
            },
        )
    ]
