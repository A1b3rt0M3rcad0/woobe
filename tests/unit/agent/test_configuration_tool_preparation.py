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
@pytest.mark.parametrize('legacy', [False, True])
@pytest.mark.parametrize('failure', [None, 'missing', 'concurrent', 'revoked'])
async def test_mcp_preparation_authorizes_each_send_and_saves_only_matching_revision(monkeypatch, failure, legacy):
    project, identifier = uuid4(), uuid4()
    auth = {'type': 'bearer', 'fields': {'token': {'source': 'project_environment', 'key': 'MCP_TOKEN'}}}
    original = SimpleNamespace(id=identifier, project_id=project, type='mcp', timeout_ms=1000,
        updated_at=datetime.now(UTC), config={'server': {'url': 'https://approved.example/mcp'}, 'authentication': auth})
    if legacy:
        from modules.agent.domain.legacy_tool_configuration import bind_legacy_tool_headers
        from modules.agent.infra.database import configuration_secret_projection
        original.config.pop('authentication')
        original.config['server']['headers'] = [{'key':'Authorization', 'value':'{{secret:stored}}'}]
        reference = {'source':'legacy_configuration', 'key':'LEGACY_KEY', 'alias_id':str(uuid4())}
        async def project_headers(session, *, project_id, tools):
            return [bind_legacy_tool_headers(tool, {'stored':reference}) for tool in tools]
        monkeypatch.setattr(configuration_secret_projection, 'project_secret_headers', project_headers)
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
    store = SimpleNamespace(lock_project=AsyncMock(), acquire=AsyncMock(), record_validation=AsyncMock())
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
        assert request.headers['authorization'] == ('mcp-private-canary' if legacy else 'Bearer mcp-private-canary')
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
            if legacy:
                assert 'authentication' not in persisted.config
                assert persisted.config['server']['headers'] == original.config['server']['headers']
            assert authorizer.require_active_control.await_count == 4
    assert not active and port.current_tool_configuration.get() is None
