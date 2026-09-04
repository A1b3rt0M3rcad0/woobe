from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.chat_surface.application.runtime_gateway import ChatRunIdentity
from woobe_api.http.chat_surface import reattach_routes


class _Service:
    def __init__(self) -> None:
        self.marked = []

    async def mark_message(self, message_id, **kwargs) -> None:
        self.marked.append((message_id, kwargs))


class _Gateway:
    def __init__(self, run_id) -> None:
        self.run_id = run_id
        self.resolve_calls = 0

    async def resolve_run(
        self,
        _target,
        *,
        preferred_run_id=None,
        created_after=None,
    ):
        del preferred_run_id, created_after
        self.resolve_calls += 1
        if self.resolve_calls < 3:
            return None
        return ChatRunIdentity(run_id=self.run_id, status="running")


@pytest.mark.asyncio
async def test_chat_surface_recovers_run_identity_lag_after_message_acceptance(monkeypatch) -> None:
    binding_id = uuid4()
    session_id = uuid4()
    run_id = uuid4()
    message_request = SimpleNamespace(
        id=uuid4(),
        status="accepted",
        target_run_id=None,
        created_at=datetime.now(UTC),
    )
    authorized = SimpleNamespace(
        binding=SimpleNamespace(
            id=binding_id,
            project_id=uuid4(),
            target_type="agent",
            target_id=uuid4(),
            target_release_id=uuid4(),
            session_id=session_id,
        ),
        claims=SimpleNamespace(permissions=frozenset({"chat:history", "chat:stream"})),
    )

    async def authorize_session(*_args, **_kwargs):
        return authorized

    async def latest_message_request(*_args, **_kwargs):
        return message_request

    async def no_wait(_seconds):
        return None

    service = _Service()
    gateway = _Gateway(run_id)
    monkeypatch.setattr(reattach_routes, "_authorized_session", authorize_session)
    monkeypatch.setattr(reattach_routes, "_latest_message_request", latest_message_request)
    monkeypatch.setattr(reattach_routes, "_runtime_gateway", lambda _request: gateway)
    monkeypatch.setattr(reattach_routes.asyncio, "sleep", no_wait)
    monkeypatch.setattr(reattach_routes, "_service", lambda _request: service)

    resolved_authorized, resolved_request, resolved_run_id, resolved_status = (
        await reattach_routes._authorized_active_request(
            SimpleNamespace(),
            session_id,
            "https://app.example.com",
        )
    )

    assert resolved_authorized is authorized
    assert resolved_request is message_request
    assert resolved_run_id == run_id
    assert resolved_status == "running"
    assert gateway.resolve_calls == 3
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

