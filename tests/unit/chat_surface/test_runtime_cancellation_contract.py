from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.chat_surface.control_plane_service import ControlPlaneChatSurfaceService
from modules.chat_surface.presentation import reattach_routes
from shared.infra.errors import AuthorizationError, NotFoundError


class _ClaimsCodec:
    def __init__(self, claims) -> None:
        self.claims = claims

    def decode(self, _token: str):
        return self.claims


def _never_session_factory():
    raise AssertionError("authorization should fail before touching the database")


@pytest.mark.asyncio
async def test_chat_cancel_scope_is_required_before_database_access() -> None:
    session_id = uuid4()
    claims = SimpleNamespace(
        session_id=session_id,
        permissions=frozenset({"chat:history", "chat:send", "chat:stream"}),
    )
    service = ControlPlaneChatSurfaceService(
        _never_session_factory,
        _ClaimsCodec(claims),
    )

    with pytest.raises(AuthorizationError):
        await service.authorize_session_token(
            "token",
            expected_session_id=session_id,
            host_origin="https://app.example.com",
            permission="chat:cancel",
        )


@pytest.mark.asyncio
async def test_chat_cancel_token_cannot_target_another_session() -> None:
    expected_session_id = uuid4()
    claims = SimpleNamespace(
        session_id=uuid4(),
        permissions=frozenset({"chat:history", "chat:send", "chat:stream", "chat:cancel"}),
    )
    service = ControlPlaneChatSurfaceService(
        _never_session_factory,
        _ClaimsCodec(claims),
    )

    with pytest.raises(NotFoundError):
        await service.authorize_session_token(
            "token",
            expected_session_id=expected_session_id,
            host_origin="https://app.example.com",
            permission="chat:cancel",
        )


class _Session:
    def __init__(self, run) -> None:
        self.run = run

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, _model, _run_id):
        return self.run


class _SessionFactory:
    def __init__(self, run) -> None:
        self.run = run

    def __call__(self):
        return _Session(self.run)


class _StateStore:
    def __init__(self) -> None:
        self.requested = []

    async def get(self, _run_id):
        return {"status": "running"}

    async def request_cancel(self, run_id) -> None:
        self.requested.append(run_id)


@pytest.mark.asyncio
async def test_chat_cancel_endpoint_requests_agent_runtime_cancellation(monkeypatch) -> None:
    project_id = uuid4()
    agent_id = uuid4()
    release_id = uuid4()
    session_id = uuid4()
    run_id = uuid4()
    binding = SimpleNamespace(
        project_id=project_id,
        target_type="agent",
        target_id=agent_id,
        session_id=session_id,
        target_release_id=release_id,
    )
    authorized = SimpleNamespace(binding=binding)
    message_request = SimpleNamespace(id=uuid4())
    run = SimpleNamespace(
        id=run_id,
        project_id=project_id,
        agent_id=agent_id,
        session_id=session_id,
        agent_release_id=release_id,
        network_execution_id=None,
        status="running",
    )
    permission_calls = []

    async def authorize(_request, actual_session_id, _origin, **kwargs):
        permission_calls.append((actual_session_id, kwargs))
        return authorized, message_request, run_id, "running"

    store = _StateStore()
    monkeypatch.setattr(reattach_routes, "_authorized_active_request", authorize)
    monkeypatch.setattr(reattach_routes, "EXECUTION_STATE_STORE", store)
    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(session_factory=_SessionFactory(run))
        )
    )

    response = await reattach_routes.cancel_chat_active_run(
        session_id,
        request,
        host_origin="https://app.example.com",
    )

    assert permission_calls == [
        (
            session_id,
            {"permission": "chat:cancel", "require_stream": False},
        )
    ]
    assert store.requested == [run_id]
    assert response == {
        "success": True,
        "data": {
            "run_id": str(run_id),
            "status": "cancel_requested",
            "target_type": "agent",
        },
    }


@pytest.mark.asyncio
async def test_chat_cancel_endpoint_is_idempotent_for_terminal_run(monkeypatch) -> None:
    session_id = uuid4()
    run_id = uuid4()
    authorized = SimpleNamespace(
        binding=SimpleNamespace(target_type="agent")
    )
    message_request = SimpleNamespace(id=uuid4())
    permission_calls = []

    async def authorize(_request, actual_session_id, _origin, **kwargs):
        permission_calls.append((actual_session_id, kwargs))
        return authorized, message_request, run_id, "cancelled"

    monkeypatch.setattr(reattach_routes, "_authorized_active_request", authorize)

    response = await reattach_routes.cancel_chat_active_run(
        session_id,
        SimpleNamespace(),
        host_origin="https://app.example.com",
    )

    assert permission_calls == [
        (
            session_id,
            {"permission": "chat:cancel", "require_stream": False},
        )
    ]
    assert response == {
        "success": True,
        "data": {
            "run_id": str(run_id),
            "status": "cancelled",
            "target_type": "agent",
        },
    }
