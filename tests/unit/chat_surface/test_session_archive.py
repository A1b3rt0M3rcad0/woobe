from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from modules.agent.domain.enums import SessionStatus
from modules.agent.infra.database.models import SessionModel
from modules.chat_surface.infra.services.chat_surface_service import ChatSurfaceService, SurfaceCredential
from modules.network.infra.database.models import NetworkSessionModel


class _AsyncContext:
    def __init__(self, value=None):
        self._value = value

    async def __aenter__(self):
        return self._value if self._value is not None else self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _FakeSession:
    def __init__(self, binding, target_session, expected_model):
        self._binding = binding
        self._target_session = target_session
        self._expected_model = expected_model

    def begin(self):
        return _AsyncContext()

    async def scalar(self, _statement):
        return self._binding

    async def get(self, model, key, **_kwargs):
        assert model is self._expected_model
        assert key == self._binding.session_id
        return self._target_session


class _SessionFactory:
    def __init__(self, session):
        self._session = session

    def __call__(self):
        return _AsyncContext(self._session)


def _surface_and_credential(target_type: str):
    project_id = uuid4()
    surface_id = uuid4()
    target_id = uuid4()
    surface = SimpleNamespace(
        id=surface_id,
        project_id=project_id,
        target_type=target_type,
        target_id=target_id,
    )
    credential = SurfaceCredential(
        api_key_id=uuid4(),
        project_id=project_id,
        chat_surface_id=surface_id,
        scopes=frozenset({"surface:sessions:archive"}),
    )
    return surface, credential


def _binding(surface, *, target_type: str):
    return SimpleNamespace(
        chat_surface_id=surface.id,
        project_id=surface.project_id,
        target_type=target_type,
        target_id=surface.target_id,
        target_release_id=uuid4(),
        session_id=uuid4(),
        status="active",
    )


@pytest.mark.asyncio
async def test_archive_agent_chat_surface_session_closes_underlying_agent_session():
    surface, credential = _surface_and_credential("agent")
    binding = _binding(surface, target_type="agent")
    target_session = SimpleNamespace(status=SessionStatus.ACTIVE.value)
    session = _FakeSession(binding, target_session, SessionModel)
    service = ChatSurfaceService(_SessionFactory(session), MagicMock())

    result = await service.archive_session(
        surface=surface,
        credential=credential,
        session_id=binding.session_id,
    )

    assert result is binding
    assert binding.status == "archived"
    assert target_session.status == SessionStatus.CLOSED.value


@pytest.mark.asyncio
async def test_archive_network_chat_surface_session_keeps_network_archive_status():
    surface, credential = _surface_and_credential("network")
    binding = _binding(surface, target_type="network")
    target_session = SimpleNamespace(status="active")
    session = _FakeSession(binding, target_session, NetworkSessionModel)
    service = ChatSurfaceService(_SessionFactory(session), MagicMock())

    result = await service.archive_session(
        surface=surface,
        credential=credential,
        session_id=binding.session_id,
    )

    assert result is binding
    assert binding.status == "archived"
    assert target_session.status == "archived"

