from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.chat_surface.application.dtos import UpdateChatSurfaceRequest
from modules.chat_surface.infra.services.chat_surface_service import ChatSurfaceService
from shared.infra.errors import ConflictError


class Context:
    def __init__(self, value=None):
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, *args):
        return False


@pytest.mark.asyncio
@pytest.mark.parametrize("stale", [False, True])
async def test_surface_revision_is_checked_under_native_row_lock(stale):
    revision = datetime.now(UTC)
    surface = SimpleNamespace(id=uuid4(), status="draft", updated_at=revision, description="before")
    session = SimpleNamespace(get=AsyncMock(return_value=surface), flush=AsyncMock(), begin=lambda: Context())
    service = ChatSurfaceService.__new__(ChatSurfaceService)
    service._session_factory = lambda: Context(session)
    payload = UpdateChatSurfaceRequest(description="after")
    if stale:
        with pytest.raises(ConflictError, match="changed remotely"):
            await service.update_surface(surface.id, payload, expected_updated_at=revision-timedelta(seconds=1))
        assert surface.description == "before"
        session.flush.assert_not_awaited()
    else:
        assert await service.update_surface(surface.id, payload, expected_updated_at=revision) is surface
        assert surface.description == "after"
        session.flush.assert_awaited_once()
    assert session.get.await_args.kwargs["with_for_update"] is True
