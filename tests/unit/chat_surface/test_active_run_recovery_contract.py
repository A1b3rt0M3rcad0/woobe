from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.chat_surface.application.runtime_gateway import ChatRunIdentity
from modules.chat_surface.infra.services import (
    control_plane_service as control_plane_service_module,
)
from modules.chat_surface.infra.services.control_plane_service import (
    ControlPlaneChatSurfaceService,
)
from modules.chat_surface.infra.services.chat_surface_service import ChatSurfaceService
from shared.infra.errors import ConflictError
from woobe_api.http.chat_surface import reattach_routes
from woobe_api.http.shared.errors import conflict_handler


class _AdmissionSession:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def scalar(self, _statement):
        return None


class _AdmissionSessionFactory:
    def __call__(self):
        return _AdmissionSession()


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


class _MessageBindingSession:
    def __init__(self, *, message_request, binding) -> None:
        self.message_request = message_request
        self.binding = binding

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, _model, identifier):
        if identifier == self.message_request.id:
            return self.message_request
        if identifier == self.binding.id:
            return self.binding
        return None


class _MessageBindingSessionFactory:
    def __init__(self, *, message_request, binding) -> None:
        self.message_request = message_request
        self.binding = binding

    def __call__(self):
        return _MessageBindingSession(
            message_request=self.message_request,
            binding=self.binding,
        )


class _LifecycleService:
    def __init__(self) -> None:
        self.marked: list[tuple[object, dict]] = []

    async def mark_message(self, message_id, **kwargs) -> None:
        self.marked.append((message_id, kwargs))


class _Gateway:
    def __init__(self, identity: ChatRunIdentity | None) -> None:
        self.identity = identity
        self.calls = []

    async def resolve_run(
        self,
        target,
        *,
        preferred_run_id=None,
        created_after=None,
    ):
        self.calls.append((target, preferred_run_id, created_after))
        return self.identity


def _binding(*, target_type: str):
    return SimpleNamespace(
        id=uuid4(),
        project_id=uuid4(),
        target_type=target_type,
        target_id=uuid4(),
        session_id=uuid4(),
        target_release_id=uuid4(),
    )


def _authorized(binding):
    return SimpleNamespace(
        surface=SimpleNamespace(id=uuid4()),
        binding=binding,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("target_type", ["agent", "network"])
async def test_active_run_endpoint_uses_runtime_gateway_as_canonical_resolver(
    monkeypatch,
    target_type: str,
) -> None:
    binding = _binding(target_type=target_type)
    run_id = uuid4()
    message_request = SimpleNamespace(
        id=uuid4(),
        status="failed",
        target_run_id=run_id,
        created_at=SimpleNamespace(),
    )
    authorized = SimpleNamespace(
        binding=binding,
        claims=SimpleNamespace(permissions=frozenset({"chat:history", "chat:stream"})),
    )
    gateway = _Gateway(ChatRunIdentity(run_id=run_id, status="running"))
    lifecycle = _LifecycleService()

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
            "status": "running",
            "target_type": target_type,
        },
    }
    assert len(gateway.calls) == 1
    target, preferred_run_id, created_after = gateway.calls[0]
    assert target.target_type == target_type
    assert preferred_run_id == run_id
    assert created_after is None
    assert lifecycle.marked == [
        (
            message_request.id,
            {
                "status": "streaming",
                "target_run_id": run_id,
                "error_code": None,
            },
        )
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("target_type", ["agent", "network"])
async def test_active_run_endpoint_recovers_canonical_run_without_message_request(
    monkeypatch,
    target_type: str,
) -> None:
    binding = _binding(target_type=target_type)
    run_id = uuid4()
    authorized = SimpleNamespace(
        binding=binding,
        claims=SimpleNamespace(permissions=frozenset({"chat:history", "chat:stream"})),
    )
    gateway = _Gateway(ChatRunIdentity(run_id=run_id, status="running"))
    lifecycle = _LifecycleService()

    async def authorize(*_args, **_kwargs):
        return authorized

    async def no_message(*_args, **_kwargs):
        return None

    monkeypatch.setattr(reattach_routes, "_authorized_session", authorize)
    monkeypatch.setattr(reattach_routes, "_latest_message_request", no_message)
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
            "message_request_id": None,
            "run_id": str(run_id),
            "status": "running",
            "target_type": target_type,
        },
    }
    assert lifecycle.marked == []
    assert len(gateway.calls) == 1
    _, preferred_run_id, created_after = gateway.calls[0]
    assert preferred_run_id is None
    assert created_after is None


@pytest.mark.asyncio
@pytest.mark.parametrize("target_type", ["agent", "network"])
async def test_begin_message_active_run_conflict_carries_canonical_run_identity(
    target_type: str,
) -> None:
    binding = _binding(target_type=target_type)
    run_id = uuid4()
    service = ControlPlaneChatSurfaceService(_AdmissionSessionFactory(), SimpleNamespace())
    authorized = _authorized(binding)

    async def reconcile_surface(_surface_id):
        return None

    async def active_run(_binding):
        return run_id, "running"

    service._reconcile_surface_active_messages = reconcile_surface
    service._active_run_for_binding = active_run

    with pytest.raises(ConflictError) as raised:
        await service.begin_message(
            authorized,
            "new-message-idempotency-key",
        )

    error = raised.value
    assert str(error) == "ChatSurface Session already has an active Run"
    assert getattr(error, "code", None) == "active_run_conflict"
    assert getattr(error, "run_id", None) == run_id
    assert getattr(error, "status", None) == "running"
    assert getattr(error, "target_type", None) == target_type


@pytest.mark.asyncio
@pytest.mark.parametrize("target_type", ["agent", "network"])
@pytest.mark.parametrize(
    ("run_status", "expected_status", "expected_error_code"),
    [
        ("completed", "completed", None),
        ("cancelled", "cancelled", None),
        ("failed", "failed", "runtime_failed"),
    ],
)
async def test_active_message_request_reconciles_terminal_run_and_releases_gate(
    monkeypatch,
    target_type: str,
    run_status: str,
    expected_status: str,
    expected_error_code: str | None,
) -> None:
    binding = _binding(target_type=target_type)
    run_id = uuid4()
    message_request = SimpleNamespace(
        id=uuid4(),
        status="streaming",
        target_run_id=run_id,
    )
    service = ControlPlaneChatSurfaceService(
        _ActiveRequestSessionFactory(message_request),
        SimpleNamespace(),
    )
    authorized = SimpleNamespace(binding=binding)
    marked: list[tuple[object, dict]] = []

    async def resolve_request_run(_request, _binding):
        return run_id, run_status

    async def base_mark_message(_self, request_id, **kwargs):
        marked.append((request_id, kwargs))

    service._resolve_request_run = resolve_request_run
    monkeypatch.setattr(ChatSurfaceService, "mark_message", base_mark_message)

    active = await service.active_message_request(authorized)

    assert active is None
    assert marked == [
        (
            message_request.id,
            {
                "status": expected_status,
                "target_run_id": run_id,
                "error_code": expected_error_code,
            },
        )
    ]


@pytest.mark.asyncio
async def test_begin_message_reconciles_active_message_before_creation(monkeypatch) -> None:
    binding = _binding(target_type="agent")
    service = ControlPlaneChatSurfaceService(_AdmissionSessionFactory(), SimpleNamespace())
    authorized = _authorized(binding)
    created = SimpleNamespace(id=uuid4())
    events: list[str] = []

    async def reconcile_surface(surface_id):
        assert surface_id == authorized.surface.id
        events.append("surface-reconcile")

    async def no_active_run(_binding):
        return None, None

    async def reconcile(_authorized):
        events.append("reconcile")
        return None

    async def base_begin_message(_self, _authorized, _idempotency_key, *, metadata=None):
        events.append("create")
        return created, True

    service._reconcile_surface_active_messages = reconcile_surface
    service._active_run_for_binding = no_active_run
    service.active_message_request = reconcile
    monkeypatch.setattr(ChatSurfaceService, "begin_message", base_begin_message)

    result = await service.begin_message(authorized, "next-message")

    assert result == (created, True)
    assert events == ["surface-reconcile", "reconcile", "create"]


@pytest.mark.asyncio
async def test_mark_message_waits_for_canonical_terminal_before_releasing_gate(
    monkeypatch,
) -> None:
    binding = _binding(target_type="agent")
    run_id = uuid4()
    message_request = SimpleNamespace(
        id=uuid4(),
        session_binding_id=binding.id,
        status="streaming",
        target_run_id=run_id,
    )
    service = ControlPlaneChatSurfaceService(
        _MessageBindingSessionFactory(
            message_request=message_request,
            binding=binding,
        ),
        SimpleNamespace(),
    )
    states = iter(
        [
            (run_id, "running"),
            (run_id, "running"),
            (run_id, "completed"),
        ]
    )
    resolve_calls = 0
    marked: list[tuple[object, dict]] = []

    async def resolve_request_run(_request, _binding):
        nonlocal resolve_calls
        resolve_calls += 1
        return next(states)

    async def no_wait(_seconds):
        return None

    async def base_mark_message(_self, request_id, **kwargs):
        marked.append((request_id, kwargs))

    service._resolve_request_run = resolve_request_run
    monkeypatch.setattr(control_plane_service_module.asyncio, "sleep", no_wait)
    monkeypatch.setattr(ChatSurfaceService, "mark_message", base_mark_message)

    await service.mark_message(message_request.id, status="completed")

    assert resolve_calls == 3
    assert marked == [
        (
            message_request.id,
            {
                "status": "completed",
                "target_run_id": run_id,
                "error_code": None,
            },
        )
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("target_type", ["agent", "network"])
async def test_conflict_handler_serializes_active_run_identity(target_type: str) -> None:
    run_id = uuid4()
    error = ConflictError("ChatSurface Session already has an active Run")
    error.code = "active_run_conflict"
    error.run_id = run_id
    error.status = "running"
    error.target_type = target_type

    response = await conflict_handler(SimpleNamespace(), error)

    assert response.status_code == 409
    assert json.loads(response.body) == {
        "success": False,
        "message": "ChatSurface Session already has an active Run",
        "data": {
            "code": "active_run_conflict",
            "run_id": str(run_id),
            "status": "running",
            "target_type": target_type,
        },
    }
