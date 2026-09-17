from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.chat_surface.infra.services import (
    control_plane_service as control_plane_service_module,
)
from modules.chat_surface.infra.services.control_plane_service import (
    ControlPlaneChatSurfaceService,
)
from modules.chat_surface.infra.services.chat_surface_service import ChatSurfaceService
from woobe_api.http.chat_surface import routes


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
    def __init__(self, message_request) -> None:
        self.message_request = message_request
        self.marked: list[tuple[object, dict]] = []

    async def begin_message(self, _authorized, _idempotency_key, *, metadata=None):
        return self.message_request, True

    async def mark_message(self, message_id, **kwargs) -> None:
        self.marked.append((message_id, kwargs))


class _FailingGateway:
    async def prepare(self, *_args, **_kwargs):
        raise RuntimeError("runtime composition failed")


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
async def test_runtime_gateway_setup_failure_terminalizes_new_message_request(
    monkeypatch,
) -> None:
    message_request = SimpleNamespace(id=uuid4(), target_run_id=None)
    project_id = uuid4()
    target_id = uuid4()
    surface_id = uuid4()
    session_id = uuid4()
    release_id = uuid4()
    lifecycle = _SurfaceLifecycle(message_request)
    authorized = SimpleNamespace(
        surface=SimpleNamespace(
            id=surface_id,
            project_id=project_id,
            target_type="agent",
            target_id=target_id,
        ),
        binding=SimpleNamespace(
            metadata_={"source": "control_plane_test"},
            session_id=session_id,
            target_release_id=release_id,
        ),
        claims=SimpleNamespace(
            permissions=frozenset({"chat:send", "chat:stream"})
        ),
    )
    payload = SimpleNamespace(message="hello", metadata=None, external_context=None)

    async def authorize(*_args, **_kwargs):
        return authorized

    monkeypatch.setattr(routes, "_authorized_session", authorize)
    monkeypatch.setattr(routes, "_service", lambda _request: lifecycle)
    monkeypatch.setattr(routes, "_runtime_gateway", lambda _request: _FailingGateway())

    with pytest.raises(RuntimeError, match="runtime composition failed"):
        await routes.stream_public_message(
            session_id,
            payload,
            SimpleNamespace(is_disconnected=lambda: None),
            idempotency_key="message-key",
            host_origin="https://app.example.com",
        )

    assert lifecycle.marked == [
        (
            message_request.id,
            {
                "status": "failed",
                "target_run_id": None,
                "error_code": "runtime_start_failed",
            },
        )
    ]
