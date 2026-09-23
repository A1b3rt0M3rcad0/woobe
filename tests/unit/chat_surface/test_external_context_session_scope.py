from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.agent.infra.database.models import AgentReleaseModel, SessionModel
from modules.chat_surface.infra.services.control_plane_service import (
    ControlPlaneChatSurfaceService,
)
from modules.network.infra.database.models import NetworkSessionModel, NetworkVersionModel


class _Session:
    def __init__(self, values):
        self._values = values

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, model, _identity):
        return self._values.get(model)


class _SessionFactory:
    def __init__(self, values):
        self._values = values

    def __call__(self):
        return _Session(self._values)


def _authorized(target_type: str):
    return SimpleNamespace(
        surface=SimpleNamespace(
            public_id="support",
            name="Support",
            appearance_config={},
        ),
        binding=SimpleNamespace(
            target_type=target_type,
            session_id=uuid4(),
            target_release_id=uuid4(),
        ),
    )


@pytest.mark.asyncio
async def test_agent_chat_surface_reports_fixed_session_external_context_fields() -> None:
    target_session = SimpleNamespace(
        external_context_snapshot={"client_id": "client-123"}
    )
    release = SimpleNamespace(
        external_context_contract={
            "client_id": {
                "schema": {"type": "string"},
                "required": True,
                "scope": "session",
                "model": {"expose": False},
            },
            "current_page": {
                "schema": {"type": "string"},
                "required": False,
                "scope": "run",
                "model": {"expose": False},
            },
        }
    )
    service = ControlPlaneChatSurfaceService(
        _SessionFactory(
            {
                SessionModel: target_session,
                AgentReleaseModel: release,
            }
        ),
        SimpleNamespace(),
    )

    configuration = await service.embed_configuration(_authorized("agent"))

    assert configuration["external_context_session_fields"] == ["client_id"]
    assert configuration["external_context_locked_fields"] == ["client_id"]


@pytest.mark.asyncio
async def test_network_chat_surface_reports_fixed_session_external_context_fields() -> None:
    target_session = SimpleNamespace(
        external_context_snapshot={"client_id": "client-123"}
    )
    version = SimpleNamespace(
        effective_external_context_contract={
            "client_id": {
                "schema": {"type": "string"},
                "scope": "session",
                "consumers": {"support": {"required": True}},
            },
            "current_page": {
                "schema": {"type": "string"},
                "scope": "run",
                "consumers": {"support": {"required": False}},
            },
        }
    )
    service = ControlPlaneChatSurfaceService(
        _SessionFactory(
            {
                NetworkSessionModel: target_session,
                NetworkVersionModel: version,
            }
        ),
        SimpleNamespace(),
    )

    configuration = await service.embed_configuration(_authorized("network"))

    assert configuration["external_context_session_fields"] == ["client_id"]
    assert configuration["external_context_locked_fields"] == ["client_id"]
