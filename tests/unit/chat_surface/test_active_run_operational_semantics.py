from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.chat_surface.application.runtime_gateway import ChatRunIdentity
from modules.chat_surface.presentation import reattach_routes


class _Gateway:
    def __init__(
        self,
        *,
        preferred_identity: ChatRunIdentity | None,
        active_identity: ChatRunIdentity | None,
    ) -> None:
        self.preferred_identity = preferred_identity
        self.active_identity = active_identity
        self.calls: list[tuple[object | None, object | None]] = []

    async def resolve_run(
        self,
        _target,
        *,
        preferred_run_id=None,
        created_after=None,
    ):
        self.calls.append((preferred_run_id, created_after))
        if preferred_run_id is not None or created_after is not None:
            return self.preferred_identity
        return self.active_identity


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


def _authorized(binding):
    return SimpleNamespace(
        binding=binding,
        claims=SimpleNamespace(permissions=frozenset({"chat:history", "chat:stream"})),
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
    lifecycle = _Lifecycle()
    gateway = _Gateway(
        preferred_identity=ChatRunIdentity(run_id=run_id, status="completed"),
        active_identity=None,
    )

    async def authorize(*_args, **_kwargs):
        return _authorized(binding)

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

    assert response == {"success": True, "data": None}
    assert lifecycle.marked == []
    assert gateway.calls == [(run_id, None), (None, None)]


@pytest.mark.asyncio
@pytest.mark.parametrize("target_type", ["agent", "network"])
async def test_terminal_bookkeeping_can_recover_a_different_canonical_active_run(
    monkeypatch,
    target_type: str,
) -> None:
    binding = _binding(target_type)
    historical_run_id = uuid4()
    active_run_id = uuid4()
    message_request = SimpleNamespace(
        id=uuid4(),
        status="completed",
        target_run_id=historical_run_id,
        created_at=SimpleNamespace(),
    )
    lifecycle = _Lifecycle()
    gateway = _Gateway(
        preferred_identity=ChatRunIdentity(
            run_id=historical_run_id,
            status="completed",
        ),
        active_identity=ChatRunIdentity(run_id=active_run_id, status="running"),
    )

    async def authorize(*_args, **_kwargs):
        return _authorized(binding)

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
            "run_id": str(active_run_id),
            "status": "running",
            "target_type": target_type,
        },
    }
    assert lifecycle.marked == [
        (
            message_request.id,
            {
                "status": "streaming",
                "target_run_id": active_run_id,
                "error_code": None,
            },
        )
    ]
    assert gateway.calls == [(historical_run_id, None), (None, None)]


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
    lifecycle = _Lifecycle()
    gateway = _Gateway(
        preferred_identity=ChatRunIdentity(run_id=run_id, status="completed"),
        active_identity=None,
    )

    async def authorize(*_args, **_kwargs):
        return _authorized(binding)

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
    assert gateway.calls == [(run_id, None)]
