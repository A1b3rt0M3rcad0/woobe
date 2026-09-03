import asyncio
from uuid import uuid4

import pytest

from modules.network.infra.runtime.store import SQLNetworkExecutionStore


class _Session:
    def __init__(self) -> None:
        self.get_calls = 0

    async def get(self, _model, _release_id):
        self.get_calls += 1
        raise AssertionError("Network runtime must not query Agent releases")


def test_pinned_release_without_frozen_session_mode_is_rejected() -> None:
    session = _Session()

    async def run() -> str:
        return await SQLNetworkExecutionStore._resolve_agent_session_mode(
            session,
            project_id=uuid4(),
            agent_id=uuid4(),
            release_id=uuid4(),
            snapshot_override={"session_mode": "stateless"},
        )

    with pytest.raises(RuntimeError, match="frozen session_mode"):
        asyncio.run(run())
    assert session.get_calls == 0


def test_draft_snapshot_session_mode_is_used_without_release_binding() -> None:
    session = _Session()

    async def run() -> str:
        return await SQLNetworkExecutionStore._resolve_agent_session_mode(
            session,
            project_id=uuid4(),
            agent_id=uuid4(),
            release_id=None,
            snapshot_override={"session_mode": "stateless"},
        )

    assert asyncio.run(run()) == "stateless"
    assert session.get_calls == 0


def test_frozen_binding_session_mode_has_precedence_without_database_lookup() -> None:
    session = _Session()

    async def run() -> str:
        return await SQLNetworkExecutionStore._resolve_agent_session_mode(
            session,
            project_id=uuid4(),
            agent_id=uuid4(),
            release_id=uuid4(),
            snapshot_override={"session_mode": "stateless"},
            binding_session_mode="stateful",
        )

    assert asyncio.run(run()) == "stateful"
    assert session.get_calls == 0
