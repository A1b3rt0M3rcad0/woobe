from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.chat_surface.application.runtime_gateway import ChatRunIdentity
from modules.chat_surface.presentation import reattach_routes


class _Gateway:
    def __init__(self, identity: ChatRunIdentity | None) -> None:
        self.identity = identity

    async def resolve_run(
        self,
        _target,
        *,
        preferred_run_id=None,
        created_after=None,
    ):
        del preferred_run_id, created_after
        return self.identity


class _Lifecycle:
    def __init__(self) -> None:
        self.marked: list[tuple[object, dict]] = []

    async def mark_message(self, message_id, **kwargs) -> None:
        self.marked.append((message_id, kwargs))


def _binding(target_type: str):
    return SimpleNamespace(
        id=uuid4(),
        project_id=uuid4(),
        target_type=target_type,
        target_id=uuid4(),
        target_release_id=uuid4(),
        session_id=uuid4(),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("target_type", ["agent", "network"])
async def test_terminal_bookkeeping_does_not_resurrect_last_run_as_active(
    monkeypatch,
    target_type: str,
) -> None:
    binding = _binding(target_type)
    run_id = uuid4()
    message_request = SimpleNamespace(
        id=uuid4(),
        status="completed",
        target_run_id=run_id,
        created_at=SimpleNamespace(),
    )
    authorized = SimpleNamespace(
        binding=binding,
        claims=SimpleNamespace(permissions=frozenset({"chat:history", "chat:stream"})),
    )
    lifecycle = _Lifecycle()
    gateway = _Gateway(ChatRunIdentity(run_id=run_id, status="completed"))

    async def authorize(*_args, **_kwargs):
        return authorized

    async def latest(*_args, **_kwargs):
        return message_request

    async def no_wait(_seconds):
        return None

    monkeypatch.setattr(reattach_routes, "_authorized_session", authorize)
    monkeypatch.setattr(reattach_routes, "_latest_message_request", latest)
    monkeypatch.setattr(reattach_routes, "_service", lambda _request: lifecycle)
    monkeypatch.setattr(reattach_routes, "_runtime_gateway", lambda _request: gateway)
    monkeypatch.setattr(reattach_routes.asyncio, "sleep", no_wait)

    response = await reattach_routes.get_chat_active_run(
        binding.session_id,
        SimpleNamespace(),
        host_origin="https://app.example.com",
    )

    assert response == {"success": True, "data": None}
    assert lifecycle.marked == []


@pytest.mark.asyncio
@pytest.mark.parametrize("target_type", ["agent", "network"])
async def test_terminal_run_remains_visible_while_message_bookkeeping_is_active(
    monkeypatch,
    target_type: str,
) -> None:
    binding = _binding(target_type)
    run_id = uuid4()
    message_request = SimpleNamespace(
        id=uuid4(),
        status="streaming",
        target_run_id=run_id,
        created_at=SimpleNamespace(),
    )
    authorized = SimpleNamespace(
        binding=binding,
        claims=SimpleNamespace(permissions=frozenset({"chat:history", "chat:stream"})),
    )
    lifecycle = _Lifecycle()
    gateway = _Gateway(ChatRunIdentity(run_id=run_id, status="completed"))

    async def authorize(*_args, **_kwargs):
        return authorized

    async def latest(*_args, **_kwargs):
        return message_request

    monkeypatch.setattr(reattach_routes, "_authorized_session", authorize)
    monkeypatch.setattr(reattach_routes, "_latest_message_request", latest)
    monkeypatch.setattr(reattach_routes, "_service", lambda _request: lifecycle)
    monkeypatch.setattr(reattach_routes, "_runtime_gateway", lambda _request: gateway)

    response = await reattach_routes.get_chat_active_run(
        binding.session_id,
        SimpleNamespace(),
        host_origin="https://app.example.com",
    )

    assert response == {
        "success": True,
        "data": {
            "message_request_id": str(message_request.id),
            "run_id": str(run_id),
            "status": "completed",
            "target_type": target_type,
        },
    }
    assert lifecycle.marked == []
