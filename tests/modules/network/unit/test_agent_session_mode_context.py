from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.network.infra.runtime.store import (
    SQLNetworkExecutionStore,
    should_persist_agent_context,
)


def test_stateless_agent_never_persists_context() -> None:
    assert not should_persist_agent_context(
        network_persists_context=True,
        agent_session_mode="stateless",
    )


def test_stateful_agent_persists_only_in_stateful_network() -> None:
    assert should_persist_agent_context(
        network_persists_context=True,
        agent_session_mode="stateful",
    )
    assert not should_persist_agent_context(
        network_persists_context=False,
        agent_session_mode="stateful",
    )


@pytest.mark.asyncio
async def test_binding_snapshot_defines_agent_session_mode_without_release_lookup() -> None:
    session = AsyncMock()
    project_id = uuid4()
    agent_id = uuid4()

    mode = await SQLNetworkExecutionStore._resolve_agent_session_mode(
        session,
        project_id=project_id,
        agent_id=agent_id,
        release_id=uuid4(),
        snapshot_override=None,
        binding_session_mode="stateless",
    )

    assert mode == "stateless"
    session.get.assert_not_awaited()


@pytest.mark.asyncio
async def test_draft_snapshot_defines_agent_session_mode() -> None:
    session = AsyncMock()

    mode = await SQLNetworkExecutionStore._resolve_agent_session_mode(
        session,
        project_id=uuid4(),
        agent_id=uuid4(),
        release_id=None,
        snapshot_override={"session_mode": "stateless"},
    )

    assert mode == "stateless"
    session.get.assert_not_awaited()


@pytest.mark.asyncio
async def test_pinned_release_defines_agent_session_mode_for_legacy_binding() -> None:
    session = AsyncMock()
    project_id = uuid4()
    agent_id = uuid4()
    session.get.return_value = SimpleNamespace(
        project_id=project_id,
        agent_id=agent_id,
        session_mode="stateful",
    )

    mode = await SQLNetworkExecutionStore._resolve_agent_session_mode(
        session,
        project_id=project_id,
        agent_id=agent_id,
        release_id=uuid4(),
        snapshot_override=None,
    )

    assert mode == "stateful"


@pytest.mark.asyncio
async def test_pinned_release_from_another_agent_is_rejected() -> None:
    session = AsyncMock()
    project_id = uuid4()
    session.get.return_value = SimpleNamespace(
        project_id=project_id,
        agent_id=uuid4(),
        session_mode="stateful",
    )

    with pytest.raises(RuntimeError, match="does not belong"):
        await SQLNetworkExecutionStore._resolve_agent_session_mode(
            session,
            project_id=project_id,
            agent_id=uuid4(),
            release_id=uuid4(),
            snapshot_override=None,
        )


@pytest.mark.asyncio
async def test_missing_session_mode_is_rejected() -> None:
    session = AsyncMock()

    with pytest.raises(RuntimeError, match="valid session_mode"):
        await SQLNetworkExecutionStore._resolve_agent_session_mode(
            session,
            project_id=uuid4(),
            agent_id=uuid4(),
            release_id=None,
            snapshot_override={},
        )
