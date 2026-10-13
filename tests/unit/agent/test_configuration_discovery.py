from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import AsyncMock

import pytest
from modules.agent.application.dtos.model_discovery_dtos import AvailableProviderModelOutput
from modules.agent.application.interfaces import project_configuration as port
from modules.agent.application.use_cases.list_available_provider_models import ListAvailableProviderModelsUseCase
from modules.agent.infra.adapters import provider_discovery_handler as module
from modules.agent.infra.adapters.configuration_transport import BoundConfigurationCredential
from shared.presentation.contracts import OperationRequest
from shared.security.principal import ControlPlanePrincipal
from shared.contracts.project_configuration import ConfigurationError


@pytest.mark.asyncio
@pytest.mark.parametrize('ready', [True, False])
async def test_discovery_authorizes_pins_and_releases_sql_before_provider_io(monkeypatch, ready):
    project, identifier = uuid4(), uuid4()
    credential = SimpleNamespace(id=identifier, project_id=project, provider='openai', status='active',
        encrypted_secret=None, metadata={}, binding_revision=1,
        authentication={'type':'api_key','fields':{'api_key':{'source':'project_environment','key':'TOKEN'}}})
    active = []
    class Scope:
        def __init__(self): self.session = object()
        def mark_read_only(self): return self
        async def __aenter__(self): active.append(self.session); return self
        async def __aexit__(self, *_): active.remove(self.session)
    repository = SimpleNamespace(get_by_id=AsyncMock(return_value=credential))
    monkeypatch.setattr(module, 'SQLAlchemyProviderCredentialRepository', lambda session: repository)
    authorizer = SimpleNamespace(require_active_control=AsyncMock(), authorize_control_key=AsyncMock())
    monkeypatch.setattr(module, 'TenantAuthorizer', lambda session: authorizer)
    store = SimpleNamespace(acquire=AsyncMock(), resolve=AsyncMock(return_value='runtime-canary'), record_validation=AsyncMock())
    if not ready: store.acquire.side_effect = ConfigurationError('CONFIG_VALUE_MISSING')
    monkeypatch.setattr(port, '_factory', lambda session: store)
    external = []
    async def discover(provider, key, metadata):
        assert not active, 'A SQL scope was held while starting provider I/O'
        assert isinstance(key, BoundConfigurationCredential)
        assert await key.resolve('https://api.openai.com/v1/models') == 'runtime-canary'
        assert not active, 'Resolver did not close its SQL scope before the send'
        external.append(True)
        return [AvailableProviderModelOutput(id='example', label='Example', provider='openai', source='provider')]
    principal = ControlPlanePrincipal(api_key_id=uuid4(), credential_id=uuid4(), workspace_id=uuid4(),
        key_prefix='test', authenticated_at=datetime.now(UTC))
    handler = module.ProviderDiscoveryHandler(Scope, discovery=discover, embedding_discovery=discover,
        secret_resolver=lambda _: pytest.fail('Typed credentials must not decrypt an old field'), use_case_factory=ListAvailableProviderModelsUseCase)
    request = OperationRequest(principal=principal, query_params={'available_for_credential_id':str(identifier), 'environment':'staging'})
    if not ready:
        with pytest.raises(ConfigurationError): await handler(request)
        assert not external
        store.record_validation.assert_not_awaited()
    else:
        result = await handler(request)
        assert result.body['data'][0]['id'] == 'example'
        assert 'runtime-canary' not in str(result.body)
        assert store.record_validation.await_args.kwargs['state'] == 'valid'
        assert store.acquire.await_args.kwargs['environment'] == 'staging'
    permissions = [call.kwargs['required_permission'] for call in authorizer.authorize_control_key.await_args_list]
    assert permissions == ['model:read', 'project:environment:validate']
    assert not active
