from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.agent.application.dtos.runtime_dtos import AskInput
from modules.agent.domain.entities import Agent
from modules.agent.domain.run import AgentRun
from modules.agent.infra.execution.ask_use_case import AskAgentUseCase
from modules.agent.infra.execution.session_continuity_runtime_resolver import SessionContinuityReleaseRuntimeResolver


@pytest.mark.asyncio
@pytest.mark.parametrize('mode', ['stateful', 'stateless'])
async def test_each_request_without_session_creates_identity(mode):
    agent = Agent(project_id=uuid4(), name='test', session_mode=mode)
    repo = SimpleNamespace(create=AsyncMock(side_effect=lambda s: s), update=AsyncMock())
    request = AskInput(project_id=agent.project_id, agent_id=agent.id, message='hi')
    resolver = SessionContinuityReleaseRuntimeResolver.__new__(SessionContinuityReleaseRuntimeResolver)
    first = await resolver._resolve_session(repo, request, agent)
    second = await resolver._resolve_session(repo, request, agent)
    assert first.id != second.id
    assert first.agent_id == agent.id
    assert first.project_id == agent.project_id
    assert resolver._uses_session_history(agent) == (mode == 'stateful')


@pytest.mark.asyncio
async def test_stateless_can_reuse_session_without_enabling_history():
    agent = Agent(project_id=uuid4(), name='test', session_mode='stateless')
    session = SimpleNamespace(id=uuid4(), runtime_environment='draft', data={})
    repo = SimpleNamespace(get_by_id=AsyncMock(return_value=session), create=AsyncMock(), update=AsyncMock())
    request = AskInput(project_id=agent.project_id, agent_id=agent.id, message='hi', execution_context='draft', session_id=session.id)
    resolver = SessionContinuityReleaseRuntimeResolver.__new__(SessionContinuityReleaseRuntimeResolver)
    assert await resolver._resolve_session(repo, request, agent) is session
    assert not AskAgentUseCase._uses_session_history(agent)
    repo.create.assert_not_awaited()


def test_run_rejects_missing_session():
    with pytest.raises(ValueError, match='requires a Session'):
        AgentRun(project_id=uuid4(), agent_id=uuid4(), session_id=None,
                 trace_id=uuid4(), environment='draft', origin='test',
                 input_message='hi', execution_snapshot={})
