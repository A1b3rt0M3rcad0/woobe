from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.network.application.session_mode_binding_service import (
    NetworkApplicationService,
    _session_mode_value,
)
from shared.infra.errors import ConflictError


def test_session_mode_value_accepts_only_runtime_contract_values() -> None:
    assert _session_mode_value("stateful") == "stateful"
    assert _session_mode_value("stateless") == "stateless"
    assert _session_mode_value("invalid") is None
    assert _session_mode_value(None) is None


@pytest.mark.asyncio
async def test_freeze_bindings_uses_pinned_agent_release_session_mode() -> None:
    project_id = uuid4()
    agent_id = uuid4()
    release_id = uuid4()
    node_id = uuid4()
    session = AsyncMock()
    session.get.return_value = SimpleNamespace(
        project_id=project_id,
        agent_id=agent_id,
        session_mode="stateful",
    )
    bindings = {
        str(node_id): {
            "node_id": str(node_id),
            "agent_id": str(agent_id),
            "release_id": str(release_id),
        }
    }

    await NetworkApplicationService._freeze_bindings(
        session,
        project_id=project_id,
        bindings=bindings,
    )

    assert bindings[str(node_id)]["session_mode"] == "stateful"
    session.get.assert_awaited_once()


@pytest.mark.asyncio
async def test_freeze_bindings_rejects_release_from_another_agent() -> None:
    project_id = uuid4()
    agent_id = uuid4()
    node_id = uuid4()
    session = AsyncMock()
    session.get.return_value = SimpleNamespace(
        project_id=project_id,
        agent_id=uuid4(),
        session_mode="stateless",
    )
    bindings = {
        str(node_id): {
            "node_id": str(node_id),
            "agent_id": str(agent_id),
            "release_id": str(uuid4()),
        }
    }

    with pytest.raises(ConflictError, match="does not belong"):
        await NetworkApplicationService._freeze_bindings(
            session,
            project_id=project_id,
            bindings=bindings,
        )
