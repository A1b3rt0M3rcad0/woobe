from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.agent.application.dtos.runtime_dtos import CreateSessionInput, ListAgentSessionsInput
from modules.agent.application.use_cases.environment_session_use_cases import (
    EnvironmentAwareCreateSessionUseCase,
    EnvironmentAwareListAgentSessionsUseCase,
)
from modules.agent.domain.entities import AgentRelease
from modules.agent.domain.enums import ReleaseStatus


@pytest.mark.asyncio
async def test_session_list_delegates_environment_filtering_to_repository() -> None:
    project_id = uuid4()
    agent_id = uuid4()
    release_id = uuid4()
    session = SimpleNamespace(
        id=uuid4(),
        project_id=project_id,
        agent_id=agent_id,
        runtime_environment="staging",
        opened_release_id=release_id,
        status="active",
        mode="chat",
        data={"source": "playground", "loaded_release_id": str(uuid4())},
        last_message_at=None,
        created_at=None,
    )
    page = SimpleNamespace(
        items=[(session, 7)],
        next_cursor="next",
        has_next=True,
    )
    repo = SimpleNamespace(
        paginate_by_agent_environment=AsyncMock(return_value=page),
    )
    use_case = EnvironmentAwareListAgentSessionsUseCase(repo)

    result = await use_case.execute(ListAgentSessionsInput(
        project_id=project_id,
        agent_id=agent_id,
        environment="staging",
        cursor=None,
        limit=20,
    ))

    repo.paginate_by_agent_environment.assert_awaited_once_with(
        project_id,
        agent_id,
        "staging",
        limit=20,
        cursor=None,
    )
    assert result.items[0].runtime_environment == "staging"
    assert result.items[0].opened_release_id == release_id
    assert result.items[0].message_count == 7
    assert result.items[0].data == {"source": "playground"}
    assert result.next_cursor == "next"
    assert result.has_next is True


@pytest.mark.asyncio
async def test_stateless_agent_can_create_session() -> None:
    project_id = uuid4()
    agent_id = uuid4()
    agent = SimpleNamespace(
        id=agent_id,
        project_id=project_id,
        session_mode="stateless",
    )
    repo = SimpleNamespace(create=AsyncMock(side_effect=lambda session: session))
    use_case = EnvironmentAwareCreateSessionUseCase(
        repo,
        SimpleNamespace(get_by_id=AsyncMock(return_value=agent)),
        SimpleNamespace(),
        SimpleNamespace(write=AsyncMock()),
    )

    result = await use_case.execute(CreateSessionInput(
        project_id=project_id,
        agent_id=agent_id,
        runtime_environment="draft",
    ))

    assert result.runtime_environment == "draft"
    assert result.id is not None


@pytest.mark.asyncio
async def test_production_session_records_opening_release_without_client_pin() -> None:
    project_id = uuid4()
    agent_id = uuid4()
    release = AgentRelease(
        project_id=project_id,
        agent_id=agent_id,
        version="v2",
        status=ReleaseStatus.production,
    )
    agent = SimpleNamespace(
        id=agent_id,
        project_id=project_id,
        session_mode="stateful",
    )
    saved = []

    async def save_session(session):
        saved.append(session)
        return session

    use_case = EnvironmentAwareCreateSessionUseCase(
        SimpleNamespace(create=AsyncMock(side_effect=save_session)),
        SimpleNamespace(get_by_id=AsyncMock(return_value=agent)),
        SimpleNamespace(get_active_production=AsyncMock(return_value=release)),
        SimpleNamespace(write=AsyncMock()),
    )

    result = await use_case.execute(CreateSessionInput(
        project_id=project_id,
        agent_id=agent_id,
        runtime_environment="production",
        data={
            "source": "playground",
            "loaded_release_id": str(uuid4()),
            "release_version": "forged",
        },
    ))

    assert saved[0].runtime_environment == "production"
    assert saved[0].opened_release_id == release.id
    assert saved[0].data == {"source": "playground"}
    assert result.opened_release_id == release.id
    assert result.data == {"source": "playground"}


@pytest.mark.asyncio
async def test_draft_session_has_no_opening_release() -> None:
    project_id = uuid4()
    agent_id = uuid4()
    agent = SimpleNamespace(
        id=agent_id,
        project_id=project_id,
        session_mode="stateful",
    )
    repo = SimpleNamespace(create=AsyncMock(side_effect=lambda session: session))
    use_case = EnvironmentAwareCreateSessionUseCase(
        repo,
        SimpleNamespace(get_by_id=AsyncMock(return_value=agent)),
        SimpleNamespace(),
        SimpleNamespace(write=AsyncMock()),
    )

    result = await use_case.execute(CreateSessionInput(
        project_id=project_id,
        agent_id=agent_id,
        runtime_environment="draft",
    ))

    assert result.runtime_environment == "draft"
    assert result.opened_release_id is None
