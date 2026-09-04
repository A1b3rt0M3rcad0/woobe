from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.chat_surface.application.runtime_gateway import ChatRunIdentity
from modules.chat_surface.infra.services.control_plane_service import ControlPlaneChatSurfaceService
from woobe_api.http.chat_surface import reattach_routes
from shared.infra.errors import AuthorizationError, ConflictError, NotFoundError


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


class _Gateway:
    def __init__(self, *, status: str = "cancel_requested", error: Exception | None = None) -> None:
        self.status = status
        self.error = error
        self.calls: list[tuple[object, object]] = []

    async def cancel(self, target, run_id):
        self.calls.append((target, run_id))
        if self.error is not None:
            raise self.error
        return ChatRunIdentity(run_id=run_id, status=self.status)


def _request(gateway: _Gateway):
    return SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(chat_surface_runtime_gateway=gateway)
        )
    )


def _authorized_binding(*, target_type: str):
    return SimpleNamespace(
        binding=SimpleNamespace(
            project_id=uuid4(),
            target_type=target_type,
            target_id=uuid4(),
            session_id=uuid4(),
            target_release_id=uuid4(),
        )
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("target_type", ["agent", "network"])
async def test_chat_cancel_endpoint_delegates_to_canonical_runtime_gateway(
    monkeypatch,
    target_type: str,
) -> None:
    authorized = _authorized_binding(target_type=target_type)
    session_id = authorized.binding.session_id
    run_id = uuid4()
    permission_calls = []

    async def authorize(_request, actual_session_id, _origin, **kwargs):
        permission_calls.append((actual_session_id, kwargs))
        return authorized, SimpleNamespace(id=uuid4()), run_id, "running"

    gateway = _Gateway()
    monkeypatch.setattr(reattach_routes, "_authorized_active_request", authorize)

    response = await reattach_routes.cancel_chat_active_run(
        session_id,
        _request(gateway),
        host_origin="https://app.example.com",
    )

    assert permission_calls == [
        (session_id, {"permission": "chat:cancel", "require_stream": False})
    ]
    assert len(gateway.calls) == 1
    target, actual_run_id = gateway.calls[0]
    assert target.target_type == target_type
    assert target.project_id == authorized.binding.project_id
    assert target.target_id == authorized.binding.target_id
    assert target.target_release_id == authorized.binding.target_release_id
    assert target.session_id == session_id
    assert actual_run_id == run_id
    assert response == {
        "success": True,
        "data": {
            "run_id": str(run_id),
            "status": "cancel_requested",
            "target_type": target_type,
        },
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [
        ConflictError("Agent Run has no active runtime state"),
        ConflictError("Agent Run runtime control state is temporarily unavailable"),
        ConflictError("Agent Run cancellation request could not be recorded safely"),
        NotFoundError("Run not found"),
    ],
)
async def test_chat_cancel_endpoint_preserves_runtime_gateway_failures(
    monkeypatch,
    error: Exception,
) -> None:
    authorized = _authorized_binding(target_type="agent")
    run_id = uuid4()

    async def authorize(*_args, **_kwargs):
        return authorized, SimpleNamespace(id=uuid4()), run_id, "running"

    gateway = _Gateway(error=error)
    monkeypatch.setattr(reattach_routes, "_authorized_active_request", authorize)

    with pytest.raises(type(error), match=str(error)):
        await reattach_routes.cancel_chat_active_run(
            authorized.binding.session_id,
            _request(gateway),
        )

    assert len(gateway.calls) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("target_type", ["agent", "network"])
async def test_chat_cancel_endpoint_is_idempotent_for_terminal_run(
    monkeypatch,
    target_type: str,
) -> None:
    authorized = _authorized_binding(target_type=target_type)
    run_id = uuid4()
    permission_calls = []

    async def authorize(_request, actual_session_id, _origin, **kwargs):
        permission_calls.append((actual_session_id, kwargs))
        return authorized, SimpleNamespace(id=uuid4()), run_id, "cancelled"

    gateway = _Gateway()
    monkeypatch.setattr(reattach_routes, "_authorized_active_request", authorize)

    response = await reattach_routes.cancel_chat_active_run(
        authorized.binding.session_id,
        _request(gateway),
        host_origin="https://app.example.com",
    )

    assert permission_calls == [
        (
            authorized.binding.session_id,
            {"permission": "chat:cancel", "require_stream": False},
        )
    ]
    assert gateway.calls == []
    assert response == {
        "success": True,
        "data": {
            "run_id": str(run_id),
            "status": "cancelled",
            "target_type": target_type,
        },
    }

