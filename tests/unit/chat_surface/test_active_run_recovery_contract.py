from __future__ import annotations

import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.chat_surface import control_plane_service as control_plane_service_module
from modules.chat_surface.control_plane_service import ControlPlaneChatSurfaceService
from modules.chat_surface.presentation import reattach_routes
from modules.chat_surface.service import ChatSurfaceService
from shared.infra.errors import ConflictError
from shared.presentation.errors import conflict_handler


class _Session:
    def __init__(self, *, run, message_request=None) -> None:
        self.run = run
        self.message_request = message_request

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, _model, identifier):
        if getattr(self.run, "id", None) == identifier:
            return self.run
        return None

    async def scalar(self, _statement):
        # The admission tests only query a Run; reattach tests first query the
        # MessageRequest and then resolve the Run by its durable target_run_id.
        return self.message_request if self.message_request is not None else self.run


class _SessionFactory:
    def __init__(self, *, run, message_request=None) -> None:
        self.run = run
        self.message_request = message_request

    def __call__(self):
        return _Session(run=self.run, message_request=self.message_request)


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


class _MessageLifecycleService:
    def __init__(self, *, run=None) -> None:
        self.run = run
        self.marked: list[tuple[object, dict]] = []

    async def mark_message(self, message_id, **kwargs) -> None:
        self.marked.append((message_id, kwargs))

    async def _active_run_for_binding(self, _binding):
        if self.run is None:
            return None, None
        return self.run.id, str(self.run.status)


def _binding(*, target_type: str):
    project_id = uuid4()
    target_id = uuid4()
    session_id = uuid4()
    release_id = uuid4()
    return SimpleNamespace(
        id=uuid4(),
        project_id=project_id,
        target_type=target_type,
        target_id=target_id,
        session_id=session_id,
        target_release_id=release_id,
    )


def _agent_run(binding):
    return SimpleNamespace(
        id=uuid4(),
        project_id=binding.project_id,
        agent_id=binding.target_id,
        session_id=binding.session_id,
        agent_release_id=binding.target_release_id,
        network_execution_id=None,
        status="running",
    )


def _network_run(binding):
    return SimpleNamespace(
        id=uuid4(),
        project_id=binding.project_id,
        network_id=binding.target_id,
        network_session_id=binding.session_id,
        network_version_id=binding.target_release_id,
        status="running",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("target_type", ["agent", "network"])
async def test_active_run_admission_and_reattach_resolve_the_same_run(target_type: str) -> None:
    binding = _binding(target_type=target_type)
    run = _agent_run(binding) if target_type == "agent" else _network_run(binding)
    factory = _SessionFactory(run=run)
    service = ControlPlaneChatSurfaceService(factory, SimpleNamespace())

    admitted_run_id, admitted_status = await service._active_run_for_binding(binding)

    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(session_factory=factory))
    )
    authorized = SimpleNamespace(binding=binding)
    message_request = SimpleNamespace(
        id=uuid4(),
        status="failed",
        target_run_id=run.id,
    )
    recovered_run_id, recovered_status = await reattach_routes._resolve_run_identity(
        request,
        authorized,
        message_request,
    )

    assert admitted_run_id == run.id
    assert admitted_status == "running"
    assert recovered_run_id == run.id
    assert recovered_status == "running"


@pytest.mark.asyncio
@pytest.mark.parametrize("target_type", ["agent", "network"])
async def test_active_run_endpoint_recovers_run_even_if_previous_observer_marked_message_failed(
    monkeypatch,
    target_type: str,
) -> None:
    binding = _binding(target_type=target_type)
    run = _agent_run(binding) if target_type == "agent" else _network_run(binding)
    message_request = SimpleNamespace(
        id=uuid4(),
        status="failed",
        target_run_id=run.id,
    )
    factory = _SessionFactory(run=run, message_request=message_request)
    authorized = SimpleNamespace(
        binding=binding,
        claims=SimpleNamespace(permissions=frozenset({"chat:history", "chat:stream"})),
    )

    async def authorize(*_args, **_kwargs):
        return authorized

    lifecycle = _MessageLifecycleService()
    monkeypatch.setattr(reattach_routes, "_authorized_session", authorize)
    monkeypatch.setattr(reattach_routes, "_service", lambda _request: lifecycle)
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(session_factory=factory))
    )

    response = await reattach_routes.get_chat_active_run(
        binding.session_id,
        request,
        host_origin="https://app.example.com",
    )

    assert response == {
        "success": True,
        "data": {
            "message_request_id": str(message_request.id),
            "run_id": str(run.id),
            "status": "running",
            "target_type": target_type,
        },
    }
    assert lifecycle.marked == [
        (
            message_request.id,
            {
                "status": "streaming",
                "target_run_id": run.id,
                "error_code": None,
            },
        )
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("target_type", ["agent", "network"])
async def test_active_run_endpoint_uses_canonical_run_when_message_request_is_missing(
    monkeypatch,
    target_type: str,
) -> None:
    """A canonical active Run must remain observable without MessageRequest correlation."""
    binding = _binding(target_type=target_type)
    run = _agent_run(binding) if target_type == "agent" else _network_run(binding)
    factory = _SessionFactory(run=run)
    authorized = SimpleNamespace(
        binding=binding,
        claims=SimpleNamespace(permissions=frozenset({"chat:history", "chat:stream"})),
    )

    async def authorize(*_args, **_kwargs):
        return authorized

    async def no_message_request(*_args, **_kwargs):
        return None

    lifecycle = _MessageLifecycleService(run=run)
    monkeypatch.setattr(reattach_routes, "_authorized_session", authorize)
    monkeypatch.setattr(reattach_routes, "_latest_message_request", no_message_request)
    monkeypatch.setattr(reattach_routes, "_service", lambda _request: lifecycle)
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(session_factory=factory))
    )

    response = await reattach_routes.get_chat_active_run(
        binding.session_id,
        request,
        host_origin="https://app.example.com",
    )

    assert response == {
        "success": True,
        "data": {
            "message_request_id": None,
            "run_id": str(run.id),
            "status": "running",
            "target_type": target_type,
        },
    }
    assert lifecycle.marked == []


@pytest.mark.asyncio
@pytest.mark.parametrize("target_type", ["agent", "network"])
async def test_begin_message_active_run_conflict_carries_canonical_run_identity(
    target_type: str,
) -> None:
    """Admission already knows the blocking Run, so the conflict must not discard it."""
    binding = _binding(target_type=target_type)
    run = _agent_run(binding) if target_type == "agent" else _network_run(binding)
    service = ControlPlaneChatSurfaceService(_AdmissionSessionFactory(), SimpleNamespace())
    authorized = SimpleNamespace(binding=binding)

    async def active_run(_binding):
        return run.id, "running"

    service._active_run_for_binding = active_run

    with pytest.raises(ConflictError) as raised:
        await service.begin_message(
            authorized,
            "new-message-idempotency-key",
        )

    error = raised.value
    assert str(error) == "ChatSurface Session already has an active Run"
    assert getattr(error, "code", None) == "active_run_conflict"
    assert getattr(error, "run_id", None) == run.id
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
    run = _agent_run(binding) if target_type == "agent" else _network_run(binding)
    run.status = run_status
    message_request = SimpleNamespace(
        id=uuid4(),
        status="streaming",
        target_run_id=run.id,
    )
    service = ControlPlaneChatSurfaceService(
        _SessionFactory(run=run, message_request=message_request),
        SimpleNamespace(),
    )
    authorized = SimpleNamespace(binding=binding)
    marked: list[tuple[object, dict]] = []

    async def resolve_request_run(_request, _binding):
        return run.id, run_status

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
                "target_run_id": run.id,
                "error_code": expected_error_code,
            },
        )
    ]


@pytest.mark.asyncio
async def test_begin_message_reconciles_active_message_request_before_creating_next_message(
    monkeypatch,
) -> None:
    binding = _binding(target_type="agent")
    service = ControlPlaneChatSurfaceService(_AdmissionSessionFactory(), SimpleNamespace())
    authorized = SimpleNamespace(binding=binding)
    created = SimpleNamespace(id=uuid4())
    events: list[str] = []

    async def no_active_run(_binding):
        return None, None

    async def reconcile(_authorized):
        events.append("reconcile")
        return None

    async def base_begin_message(_self, _authorized, _idempotency_key, *, metadata=None):
        events.append("create")
        return created, True

    service._active_run_for_binding = no_active_run
    service.active_message_request = reconcile
    monkeypatch.setattr(ChatSurfaceService, "begin_message", base_begin_message)

    result = await service.begin_message(authorized, "next-message")

    assert result == (created, True)
    assert events == ["reconcile", "create"]


@pytest.mark.asyncio
async def test_begin_message_retries_once_after_legacy_active_message_integrity_conflict(
    monkeypatch,
) -> None:
    binding = _binding(target_type="agent")
    service = ControlPlaneChatSurfaceService(_AdmissionSessionFactory(), SimpleNamespace())
    authorized = SimpleNamespace(binding=binding)
    created = SimpleNamespace(id=uuid4())
    begin_calls = 0
    reconcile_calls = 0

    async def no_active_run(_binding):
        return None, None

    async def reconcile(_authorized):
        nonlocal reconcile_calls
        reconcile_calls += 1
        return None

    async def base_begin_message(_self, _authorized, _idempotency_key, *, metadata=None):
        nonlocal begin_calls
        begin_calls += 1
        if begin_calls == 1:
            raise ConflictError("ChatSurface Session already has an active Run")
        return created, True

    service._active_run_for_binding = no_active_run
    service.active_message_request = reconcile
    monkeypatch.setattr(ChatSurfaceService, "begin_message", base_begin_message)

    result = await service.begin_message(authorized, "next-message")

    assert result == (created, True)
    assert begin_calls == 2
    assert reconcile_calls == 2


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
    """The iframe must receive the Run identity directly from the 409 response."""
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
