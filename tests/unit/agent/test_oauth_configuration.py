from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.agent.domain.oauth_configuration import oauth_dependencies, oauth_references, hydrate_oauth_workset
from shared.contracts.project_configuration import ConfigurationError


def source():
    return SimpleNamespace(id=uuid4(), project_id=uuid4(), config={
        'server': {'url': 'https://mcp.example/tenant/mcp'}, 'oauth': {
            'token_endpoint': 'https://auth.example/token', 'client_id': 'registered', 'scopes': ['read'],
            'configuration_refs': {field: {'source': 'legacy_configuration', 'key': field.upper(), 'alias_id': str(uuid4())}
                for field in ('access_token', 'refresh_token', 'client_secret', 'code_verifier', 'device_code')}}})


def test_each_field_keeps_its_exact_owner_and_destination_and_workset_has_no_material():
    tool = source()
    original = deepcopy(tool.config)
    dependencies = oauth_dependencies(tool)
    assert len(dependencies) == 5
    assert all(dep.consumer_kind == 'mcp_oauth' and dep.consumer_id == tool.id for dep in dependencies)
    assert next(dep.destination for dep in dependencies if dep.field_path.endswith('access_token')) == 'https://mcp.example/tenant/mcp'
    assert all(dep.destination == 'https://auth.example/token' for dep in dependencies if not dep.field_path.endswith('access_token'))
    workset = hydrate_oauth_workset(tool)
    assert tool.config == original
    assert 'configuration_refs' not in workset.config['oauth']
    assert all(workset.config['oauth'][field + '_encrypted'].startswith('woobe-oauth-ref:') for field in original['oauth']['configuration_refs'])


def test_flow_selection_does_not_acquire_access_or_refresh_authority_incidentally():
    tool = source()
    dependencies = oauth_dependencies(tool, fields={'code_verifier', 'client_secret'})
    assert {dep.field_path.rsplit('/', 1)[-1] for dep in dependencies} == {'code_verifier', 'client_secret'}
    first = dependencies[0].definition_revision
    tool.config['oauth']['scopes'] = ['write']
    assert oauth_dependencies(tool, fields={'code_verifier'})[0].definition_revision != first


@pytest.mark.parametrize('mutation', ['unknown', 'mixed', 'material', 'destination'])
def test_ambiguous_or_model_visible_authority_is_rejected(mutation):
    tool = source()
    if mutation == 'unknown':
        tool.config['oauth']['configuration_refs']['prompt'] = {'source': 'project_environment', 'key': 'TOKEN'}
    elif mutation == 'mixed':
        tool.config['oauth']['access_token_encrypted'] = 'old-ciphertext'
    elif mutation == 'material':
        tool.config['oauth']['configuration_refs']['access_token']['value'] = 'private-canary'
    else:
        tool.config['oauth']['token_endpoint'] = 'https://user:private-canary@auth.example/token'
    with pytest.raises(ConfigurationError) as rejected:
        hydrate_oauth_workset(tool) if mutation == 'mixed' else oauth_dependencies(tool)
    assert 'private-canary' not in str(rejected.value)
