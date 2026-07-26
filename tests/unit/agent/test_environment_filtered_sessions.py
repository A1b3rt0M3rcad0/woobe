from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.agent.application.use_cases.environment_filtered_sessions import (
    EnvironmentFilteredListAgentSessionsUseCase,
)


def _session(*, project_id, agent_id, environment=None, minutes=0):
    data = {} if environment is None else {"runtime_environment": environment}
    return SimpleNamespace(
        id=uuid4(),
        project_id=project_id,
        agent_id=agent_id,
        status="active",
        mode="chat",
        data=data,
        last_message_at=datetime.now(timezone.utc) + timedelta(minutes=minutes),
        created_at=datetime.now(timezone.utc),
    )


@pytest.mark.asyncio
async def test_sessions_are_filtered_before_environment_pagination() -> None:
    project_id = uuid4()
    agent_id = uuid4()
    draft = _session(project_id=project_id, agent_id=agent_id, environment="draft", minutes=5)
    staging_new = _session(project_id=project_id, agent_id=agent_id, environment="staging", minutes=4)
    production = _session(project_id=project_id, agent_id=agent_id, environment="production", minutes=3)
    staging_old = _session(project_id=project_id, agent_id=agent_id, environment="staging", minutes=2)

    session_repo = SimpleNamespace(list_by_agent=AsyncMock(return_value=[draft, staging_new, production, staging_old]))
    message_repo = SimpleNamespace(count_by_session=AsyncMock(return_value=0))
    use_case = EnvironmentFilteredListAgentSessionsUseCase(session_repo, message_repo)

    first_page = await use_case.execute(SimpleNamespace(
        project_id=project_id,
        agent_id=agent_id,
        environment="staging",
        cursor=None,
        limit=1,
    ))

    assert [item.id for item in first_page.items] == [staging_new.id]
    assert first_page.has_next is True
    assert first_page.next_cursor == str(staging_new.id)

    second_page = await use_case.execute(SimpleNamespace(
        project_id=project_id,
        agent_id=agent_id,
        environment="staging",
        cursor=first_page.next_cursor,
        limit=1,
    ))

    assert [item.id for item in second_page.items] == [staging_old.id]
    assert second_page.has_next is False


@pytest.mark.asyncio
async def test_legacy_sessions_without_environment_are_draft() -> None:
    project_id = uuid4()
    agent_id = uuid4()
    legacy = _session(project_id=project_id, agent_id=agent_id, environment=None)
    staging = _session(project_id=project_id, agent_id=agent_id, environment="staging")

    use_case = EnvironmentFilteredListAgentSessionsUseCase(
        SimpleNamespace(list_by_agent=AsyncMock(return_value=[legacy, staging])),
        SimpleNamespace(count_by_session=AsyncMock(return_value=0)),
    )

    result = await use_case.execute(SimpleNamespace(
        project_id=project_id,
        agent_id=agent_id,
        environment="draft",
        cursor=None,
        limit=20,
    ))

    assert [item.id for item in result.items] == [legacy.id]
