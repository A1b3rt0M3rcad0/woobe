import asyncio
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.agent.infra.handlers import detached_mcp_oauth as boundary
from modules.agent.infra.adapters.oauth_protocol_executor import OAuthProtocolExecutor
from modules.agent.application.interfaces.ports import ExecutionResult
from modules.agent.application.interfaces.oauth_protocol import current_oauth_operation_authorizer
from shared.contracts.errors import AuthorizationError
from shared.contracts.project_configuration import ConfigurationError


@pytest.mark.asyncio
@pytest.mark.parametrize('concurrent', ['none', 'config', 'metadata', 'authority', 'cancel'])
async def test_outbound_flow_releases_sql_and_fences_commit(monkeypatch, concurrent):
    target = SimpleNamespace(id=uuid4(), project_id=uuid4(), type='mcp', name='Original',
        updated_at='original', config={'server': {'url': 'https://approved.example/mcp'}})
    state = {'active': 0, 'authorized': True}
    writes = []
    began, finish = asyncio.Event(), asyncio.Event()

    class Uow:
        session = object()
        async def __aenter__(self):
            state['active'] += 1
            return self
        async def __aexit__(self, *args):
            state['active'] -= 1

    async def authorize(*args):
        assert state['active'] == 1
        if not state['authorized']:
            raise AuthorizationError('Grant revoked')

    async def write(tool):
        assert state['active'] == 1
        writes.append(deepcopy(tool))

    repo = SimpleNamespace(get_by_id=AsyncMock(side_effect=lambda _: deepcopy(target)),
        lock_by_id=AsyncMock(side_effect=lambda _: deepcopy(target)), update=write)
    monkeypatch.setattr(boundary, 'SQLAlchemyAgentToolRepository', lambda _: repo)
    monkeypatch.setattr(boundary, 'configuration_for_session', lambda _: SimpleNamespace(lock_project=AsyncMock()))
    monkeypatch.setattr(boundary.DetachedMcpOAuthOperation, 'authorize', staticmethod(authorize))

    def controller(workset):
        async def handle(request):
            assert state['active'] == 0
            began.set()
            await finish.wait()
            assert state['active'] == 0
            async def outbound(*args, **kwargs):
                assert state['active'] == 0
                return ExecutionResult(success=True, output={'body': {}})
            await OAuthProtocolExecutor(SimpleNamespace(execute=outbound)).execute('GET', 'https://approved.example/metadata')
            detached = await workset.get_by_id(target.id)
            detached.config['oauth'] = {'status': 'pending'}
            await workset.update(detached)
            return SimpleNamespace(body={'data': {'status': 'pending'}})
        return SimpleNamespace(handle=handle)

    operation = boundary.DetachedMcpOAuthOperation(Uow, controller)
    task = asyncio.create_task(operation(SimpleNamespace(body={'tool_id': str(target.id)}, principal=object())))
    await asyncio.wait_for(began.wait(), 1)
    assert state['active'] == 0 and not writes
    if concurrent == 'config':
        target.config['server']['url'] = 'https://different.example/mcp'
    elif concurrent == 'metadata':
        target.name = 'Concurrent rename'
        target.updated_at = 'newer'
    elif concurrent == 'authority':
        state['authorized'] = False
    elif concurrent == 'cancel':
        task.cancel()
    finish.set()
    if concurrent in {'config', 'metadata'}:
        with pytest.raises(ConfigurationError) as rejected:
            await task
        assert rejected.value.code == 'CONFIG_REVISION_CONFLICT'
    elif concurrent == 'authority':
        with pytest.raises(AuthorizationError):
            await task
    elif concurrent == 'cancel':
        with pytest.raises(asyncio.CancelledError):
            await task
    else:
        assert (await task).body['data']['status'] == 'pending'
        assert len(writes) == 1 and writes[0].config['oauth']['status'] == 'pending'
    assert state['active'] == 0
    assert current_oauth_operation_authorizer.get() is None
    if concurrent != 'none':
        assert not writes
