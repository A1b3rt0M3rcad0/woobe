from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.chat_surface import control_plane_service as control_plane_service_module
from modules.chat_surface.control_plane_service import ControlPlaneChatSurfaceService
from modules.chat_surface.presentation import routes
from modules.chat_surface.service import ChatSurfaceService


class _ActiveRequestSession:
    def __init__(self, message_request) -> None:
        self.message_request = message_request

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def scalar(self, _statement):
        return self.message_request


class _ActiveRequestSessionFactory:
    def __init__(self, message_request) -> None:
        self.message_request = message_request

    def __call__(self):
        return _ActiveRequestSession(self.message_request)


class _SurfaceLifecycle:
    def __init__(self) -> None:
        self.marked: list[tuple[object, dict]] = []

    async def mark_message(self, message_id, **kwargs) -> None:
        self.marked.append((message_id, kwargs))


@pytest.mark.asyncio
async def test_active_message_request_without_canonical_run_releases_orphaned_gate(
    monkeypatch,
) -> None:
    message_request = SimpleNamespace(
        id=uuid4(),
        status="streaming",
        target_run_id=None,
    )
    binding = SimpleNamespace(
        id=uuid4(),
        target_type="agent",
    )
    authorized = SimpleNamespace(binding=binding)
    service = ControlPlaneChatSurfaceService(
        _ActiveRequestSessionFactory(message_request),
        SimpleNamespace(),
    )
    marked: list[tuple[object, dict]] = []

    async def no_run(_request, _binding):
        return None, None

    async def no_wait(_seconds):
        return None

    async def base_mark_message(_self, request_id, **kwargs):
        marked.append((request_id, kwargs))

    service._resolve_request_run = no_run
    monkeypatch.setattr(control_plane_service_module.asyncio, "sleep", no_wait)
    monkeypatch.setattr(ChatSurfaceService, "mark_message", base_mark_message)

    active = await service.active_message_request(authorized)

    assert active is None
    assert marked == [
        (
            message_request.id,
            {
                "status": "failed",
                "target_run_id": None,
                "error_code": "run_acceptance_missing",
            },
        )
    ]


@pytest.mark.asyncio
async def test_agent_stream_setup_failure_terminalizes_message_request(
    monkeypatch,
) -> None:
    message_request_id = uuid4()
    project_id = uuid4()
    agent_id = uuid4()
    surface_id = uuid4()
    session_id = uuid4()
    release_id = uuid4()
    lifecycle = _SurfaceLifecycle()
    authorized = SimpleNamespace(
        surface=SimpleNamespace(
            id=surface_id,
            project_id=project_id,
            target_id=agent_id,
        ),
        binding=SimpleNamespace(
            metadata_={"source": "control_plane_test"},
            session_id=session_id,
            target_release_id=release_id,
        ),
    )
    payload = SimpleNamespace(message="hello", metadata=None)

    def fail_runtime_composition():
        raise RuntimeError("runtime composition failed")

    monkeypatch.setattr(routes, "_service", lambda _request: lifecycle)
    monkeypatch.setattr(routes, "build_agent_stream_service", fail_runtime_composition)

    stream = routes._agent_stream(
        SimpleNamespace(),
        message_request_id=message_request_id,
        authorized=authorized,
        payload=payload,
    )

    with pytest.raises(RuntimeError, match="runtime composition failed"):
        async for _ in stream:
            pass

    assert lifecycle.marked == [
        (message_request_id, {"status": "streaming"}),
        (
            message_request_id,
            {
                "status": "failed",
                "error_code": "runtime_failed",
            },
        ),
    ]
