import asyncio
from types import SimpleNamespace
from uuid import uuid4

from modules.network.infra.runtime.store import SQLNetworkExecutionStore


class _Session:
    def __init__(self, release=None) -> None:
        self.release = release
        self.get_calls = 0

    async def get(self, _model, _release_id):
        self.get_calls += 1
        return self.release


def test_pinned_release_session_mode_wins_over_compatibility_snapshot() -> None:
    project_id = uuid4()
    agent_id = uuid4()
    release_id = uuid4()
    session = _Session(
        SimpleNamespace(
            project_id=project_id,
            agent_id=agent_id,
            session_mode="stateful",
        )
    )

    async def run() -> str:
        return await SQLNetworkExecutionStore._resolve_agent_session_mode(
            session,
            project_id=project_id,
            agent_id=agent_id,
            release_id=release_id,
            snapshot_override={
                "provider": "custom",
                "model": "deepseek-v4-flash",
                "pinned_release_id": str(release_id),
            },
        )

    assert asyncio.run(run()) == "stateful"
    assert session.get_calls == 1


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
