from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.chat_surface.presentation import reattach_routes
from shared.infra.in_memory_execution_state import InMemoryExecutionStateStore


class _SurfaceService:
    def __init__(self) -> None:
        self.marked: list[tuple[object, dict]] = []

    async def mark_message(self, message_id, **kwargs) -> None:
        self.marked.append((message_id, kwargs))


class _Request:
    def __init__(self, *, disconnected: bool = False) -> None:
        self.disconnected = disconnected
        self.app = SimpleNamespace(
            state=SimpleNamespace(
                settings=SimpleNamespace(network_stream_heartbeat_seconds=10),
                session_factory=None,
            )
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

    store = InMemoryExecutionStateStore()
    await store.create(
        run_id,
        {
            "status": "running",
            "project_id": str(project_id),
            "agent_id": str(agent_id),
            "session_id": str(session_id),
        },
        ttl_seconds=3600,
    )
    await store.append_event(
        run_id,
        "cancelled",
        {
            "run_id": str(run_id),
            "output": "partial",
            "partial": True,
            "persisted": True,
        },
    )

    service = _SurfaceService()
    monkeypatch.setattr(reattach_routes, "_authorized_active_request", active_request)
    monkeypatch.setattr(reattach_routes, "EXECUTION_STATE_STORE", store)
    monkeypatch.setattr(reattach_routes, "_service", lambda _request: service)

    response = await reattach_routes.stream_chat_active_run(session_id, _Request())
    chunks = []
    async for chunk in response.body_iterator:
        chunks.append(chunk.decode() if isinstance(chunk, bytes) else str(chunk))

    assert response.headers["cache-control"] == "no-cache, no-transform"
    assert response.headers["x-accel-buffering"] == "no"
    assert any('"status": "cancelled"' in chunk for chunk in chunks)
    assert service.marked == [
        (
            message_request.id,
            {
                "status": "cancelled",
                "target_run_id": run_id,
                "error_code": None,
            },
        )
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

    store = InMemoryExecutionStateStore()
    await store.create(
        run_id,
        {
            "status": "running",
            "project_id": str(project_id),
            "agent_id": str(agent_id),
            "session_id": str(session_id),
        },
        ttl_seconds=3600,
    )
    await store.append_event(run_id, "token", {"content": "partial", "visibility": "assistant", "channel": "final"})

    service = _SurfaceService()
    monkeypatch.setattr(reattach_routes, "_authorized_active_request", active_request)
    monkeypatch.setattr(reattach_routes, "EXECUTION_STATE_STORE", store)
    monkeypatch.setattr(reattach_routes, "_service", lambda _request: service)

    response = await reattach_routes.stream_chat_active_run(
        session_id,
        _Request(disconnected=True),
    )
    async for _ in response.body_iterator:
        pass

    assert service.marked == []
