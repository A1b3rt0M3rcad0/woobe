from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.chat_surface.control_plane_service import ControlPlaneChatSurfaceService
from modules.chat_surface.presentation import reattach_routes


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
        return self.message_request


class _SessionFactory:
    def __init__(self, *, run, message_request=None) -> None:
        self.run = run
        self.message_request = message_request

    def __call__(self):
        return _Session(run=self.run, message_request=self.message_request)


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

    monkeypatch.setattr(reattach_routes, "_authorized_session", authorize)
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
