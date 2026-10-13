from copy import deepcopy
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import AsyncMock

import httpx
import pytest
from modules.agent.application.interfaces import project_configuration as port
from modules.agent.application.mcp_tool_bootstrap import McpToolBootstrapper
from modules.agent.infra.adapters import configuration_tool_preparation as module
from modules.agent.infra.adapters.tool_executor import HttpToolExecutor
from shared.contracts.errors import AuthorizationError
from shared.contracts.project_configuration import ConfigurationError
from shared.presentation.contracts import OperationRequest
from shared.security.principal import ControlPlanePrincipal


@pytest.mark.asyncio
@pytest.mark.parametrize('failure', [None, 'missing', 'concurrent', 'revoked'])
async def test_mcp_preparation_authorizes_each_send_and_saves_only_matching_revision(monkeypatch, failure):
    project, identifier = uuid4(), uuid4()
    auth = {'type': 'bearer', 'fields': {'token': {'source': 'project_environment', 'key': 'MCP_TOKEN'}}}
    original = SimpleNamespace(id=identifier, project_id=project, type='mcp', timeout_ms=1000,
        updated_at=datetime.now(UTC), config={'server': {'url': 'https://approved.example/mcp'}, 'authentication': auth})
    persisted = deepcopy(original)
    active, outbound = [], []
    class Scope:
        def __init__(self): self.session = object()
        async def __aenter__(self): active.append(self.session); return self
        async def __aexit__(self, *_): active.remove(self.session)
    repository = SimpleNamespace(get_by_id=AsyncMock(return_value=original), lock_by_id=AsyncMock(return_value=persisted), update=AsyncMock())
    monkeypatch.setattr(module, 'SQLAlchemyAgentToolRepository', lambda session: repository)
    authorizer = SimpleNamespace(require_active_control=AsyncMock(), authorize_control_key=AsyncMock())
    monkeypatch.setattr(module, 'TenantAuthorizer', lambda session: authorizer)
    store = SimpleNamespace(acquire=AsyncMock(), record_validation=AsyncMock())
    if failure == 'missing': store.acquire.side_effect = ConfigurationError('CONFIG_VALUE_MISSING')
    monkeypatch.setattr(port, '_factory', lambda session: store)
    async def resolve(**identity):
        assert not active
        assert identity['project_id'] == project and identity['consumer_id'] == identifier
        assert identity['destination'] == 'https://approved.example/mcp'
        return 'mcp-private-canary'
    monkeypatch.setattr(port, '_runtime_resolver', resolve)
    monkeypatch.setattr('modules.agent.infra.adapters.tool_executor._validated_local_addresses', lambda url: frozenset({'8.8.8.8'}))
    def send(request):
        import json
        assert not active, 'SQL must be closed before external I/O'
        assert request.headers['authorization'] == 'Bearer mcp-private-canary'
        payload = json.loads(request.content)
        outbound.append(payload['method'])
        if failure == 'concurrent': persisted.config = {**persisted.config, 'concurrent': True}
        if failure == 'revoked': authorizer.require_active_control.side_effect = AuthorizationError('revoked')
        if payload['method'] == 'notifications/initialized': return httpx.Response(202, request=request)
        result = {'tools': [{'name': 'lookup', 'description': 'Read metadata', 'inputSchema': {'type': 'object'}}]} if payload['method'] == 'tools/list' else {'protocolVersion': '2025-06-18', 'capabilities': {'tools': {}}, 'serverInfo': {'name': 'fixture', 'version': '1'}}
        return httpx.Response(200, json={'jsonrpc': '2.0', 'id': payload['id'], 'result': result}, request=request)
    principal = ControlPlanePrincipal(api_key_id=uuid4(), credential_id=uuid4(), workspace_id=uuid4(), key_prefix='test', authenticated_at=datetime.now(UTC))
    request = OperationRequest(principal=principal, path_params={'project_id': project, 'target_id': identifier}, body={'environment': 'staging'})
    async with httpx.AsyncClient(transport=httpx.MockTransport(send)) as client:
        handler = module.ConfigurationToolPreparation(Scope, McpToolBootstrapper(HttpToolExecutor(client=client)))
        if failure:
            with pytest.raises((ConfigurationError, AuthorizationError)):
                await handler(request)
            repository.update.assert_not_awaited()
            store.record_validation.assert_not_awaited()
            if failure == 'missing': assert not outbound
        else:
            result = await handler(request)
            assert result.body['data']['state'] == 'ready'
            assert result.body['data']['discovered_count'] == 1
            assert 'mcp-private-canary' not in str(result.body) + str(persisted.config)
            assert store.record_validation.await_args.kwargs['state'] == 'valid'
            assert store.acquire.await_args.kwargs['environment'] == 'staging'
            assert outbound == ['initialize', 'notifications/initialized', 'tools/list']
            assert authorizer.require_active_control.await_count == 4
    assert not active and port.current_tool_configuration.get() is None
