from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.agent.application.interfaces.project_configuration import current_tool_configuration
from modules.agent.domain.enums import ToolStatus
from modules.agent.infra.handlers import configured_tool_operation as module
from shared.contracts.errors import AuthorizationError
from shared.contracts.project_configuration import ConfigurationError
from shared.presentation.contracts import OperationRequest


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', [None, 'permission', 'configuration'])
async def test_persisted_tool_invocation_acquires_before_detached_send_and_never_falls_back(monkeypatch, failure):
    project_id, tool_id = uuid4(), uuid4()
    auth = {'type': 'bearer', 'fields': {'token': {'source': 'project_environment', 'key': 'TOKEN'}}}
    tool = SimpleNamespace(id=tool_id, project_id=project_id, status=ToolStatus.ACTIVE,
                           config={'url': 'https://approved.example/tool', 'authentication': auth})
    active = []
    class Scope:
        session = object()
        async def __aenter__(self): active.append(self.session); return self
        async def __aexit__(self, *_): active.remove(self.session)

    repo = SimpleNamespace(get_by_id=AsyncMock(return_value=tool), lock_by_id=AsyncMock(return_value=tool))
    monkeypatch.setattr(module, 'SQLAlchemyAgentToolRepository', lambda session: repo)
    store = SimpleNamespace(lock_project=AsyncMock(), acquire=AsyncMock())
    monkeypatch.setattr(module, 'configuration_for_session', lambda session: store)
    monkeypatch.setattr(module, 'project_secret_headers', AsyncMock(return_value=[tool]))
    authorization = AsyncMock()
    monkeypatch.setattr(module.ConfiguredToolOperation, 'authorize', authorization)
    fallback = AsyncMock(side_effect=AssertionError('central operations cannot fallback'))
    if failure == 'permission': authorization.side_effect = AuthorizationError('denied')
    if failure == 'configuration': store.acquire.side_effect = ConfigurationError('CONFIG_USAGE_NOT_AUTHORIZED')

    async def execute(actual, input_data):
        assert not active
        store.acquire.assert_awaited_once()
        assert actual is tool and input_data == {'id': 'order'}
        identity = current_tool_configuration.get()
        assert identity[0] == project_id and identity[2:] == (tool_id, auth)
        assert identity[1] == store.acquire.await_args.kwargs['run_id']
        return SimpleNamespace(success=True, output={'ok': True}, duration_ms=1, error=None)

    registry = SimpleNamespace(execute=AsyncMock(side_effect=execute))
    handler = module.ConfiguredToolOperation(Scope, fallback, registry=registry)
    request = OperationRequest(body={'tool_id': tool_id, 'input_data': {'id': 'order'}})
    if failure:
        with pytest.raises((ConfigurationError, AuthorizationError)):
            await handler(request)
        registry.execute.assert_not_awaited()
    else:
        response = await handler(request)
        assert response.body['data']['success']
        assert store.acquire.await_args.kwargs['environment'] == 'draft'
    assert not active and current_tool_configuration.get() is None
    fallback.assert_not_awaited()
    if failure == 'permission':
        repo.get_by_id.assert_not_awaited()
        store.acquire.assert_not_awaited()


@pytest.mark.asyncio
async def test_enclosing_operation_cannot_authorize_a_different_tool_or_binding():
    from modules.agent.infra.adapters.tool_configuration_transport import configuration_bound_tool

    project, identifier = uuid4(), uuid4()
    auth = {'type': 'bearer', 'fields': {'token': {'source': 'project_environment', 'key': 'TOKEN'}}}
    called = AsyncMock()
    wrapped = configuration_bound_tool(called)
    token = current_tool_configuration.set((project, uuid4(), identifier, auth))
    try:
        foreign = SimpleNamespace(id=uuid4(), project_id=project, config={'authentication': auth})
        with pytest.raises(ConfigurationError) as denied:
            await wrapped(None, foreign)
        assert denied.value.code == 'CONFIG_USAGE_NOT_AUTHORIZED'
        changed = SimpleNamespace(id=identifier, project_id=project, config={'authentication': {
            'type': 'bearer', 'fields': {'token': {'source': 'project_environment', 'key': 'OTHER'}},
        }})
        with pytest.raises(ConfigurationError) as denied:
            await wrapped(None, changed)
        assert denied.value.code == 'CONFIG_USAGE_NOT_AUTHORIZED'
        called.assert_not_awaited()
    finally:
        current_tool_configuration.reset(token)


@pytest.mark.asyncio
async def test_unconfigured_nested_tool_never_inherits_parent_private_headers():
    from modules.agent.infra.adapters.tool_configuration_transport import configuration_bound_tool

    async def execute(_self, _tool):
        assert current_tool_configuration.get() is None
        return 'ok'

    parent = (uuid4(), uuid4(), uuid4(), {'type': 'headers', 'fields': {
        'X-Private': {'source': 'project_environment', 'key': 'PRIVATE'},
    }})
    token = current_tool_configuration.set(parent)
    try:
        tool = SimpleNamespace(id=uuid4(), project_id=parent[0], config={})
        assert await configuration_bound_tool(execute)(None, tool) == 'ok'
        assert current_tool_configuration.get() == parent
    finally:
        current_tool_configuration.reset(token)
