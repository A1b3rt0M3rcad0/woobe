from copy import deepcopy
from uuid import uuid4

import pytest

from modules.agent.domain.oauth_public_configuration import merge_public_oauth_edit, public_tool_configuration
from modules.agent.application.dtos.tools_dtos import CreateToolInput, CreateToolOutput
from modules.agent.presentation.schemas import ToolResponse
from modules.agent.presentation.schemas import ReleaseResponse
from modules.agent.application.dtos.ai_dtos import CreateReleaseOutput, ListReleasesOutput
from shared.contracts.project_configuration import ConfigurationError


def source():
    return {'server': {'url': 'https://mcp.example/mcp'}, 'oauth': {'status': 'connected',
        'access_token_encrypted': 'private-access-canary', 'refresh_token_encrypted': 'private-refresh-canary',
        'client_secret_encrypted': 'private-client-canary', 'device_code_encrypted': 'private-device-canary',
        'code_verifier_encrypted': 'private-verifier-canary', 'state': 'private-state-canary',
        'client_id': 'registered-client', 'token_endpoint': 'https://auth.example/token',
        'authorization_endpoint': 'https://auth.example/authorize', 'scopes': ['mcp:read']}}


@pytest.mark.parametrize('response_type', [CreateToolOutput, ToolResponse])
def test_actual_tool_response_schema_excludes_ciphertext_and_transients_without_mutating_source(response_type):
    config = source()
    original = deepcopy(config)
    response = response_type(id=uuid4(), project_id=uuid4(), name='Public Tool', description='',
        type='mcp', config=config, input_schema={}, output_schema={}, risk_level='low', timeout_ms=1000, status='active')
    public = response.model_dump()['config']
    assert 'canary' not in str(public)
    assert public['oauth']['client_id'] == 'registered-client' and public['oauth']['status'] == 'connected'
    assert config == original and response.config == original


def test_public_edit_preserves_private_authority_and_drops_readiness_projection():
    current = source()
    projected = public_tool_configuration(current)
    projected['mcp_readiness'] = {'state': 'ready'}
    result = merge_public_oauth_edit(current, projected)
    assert result == current
    # Omission is a metadata edit, not an implicit credential disconnect.
    assert merge_public_oauth_edit(current, {'server': current['server']}) == current
    assert 'canary' not in str(projected)


@pytest.mark.parametrize('mutation', ['destination', 'issuer', 'scopes', 'ciphertext', 'state', 'reference'])
def test_public_edit_cannot_inject_retarget_or_expand_opaque_protocol_authority(mutation):
    current = source()
    requested = public_tool_configuration(current)
    if mutation == 'destination': requested['server']['url'] = 'https://different.example/mcp'
    elif mutation == 'issuer': requested['oauth']['token_endpoint'] = 'https://different.example/token'
    elif mutation == 'scopes': requested['oauth']['scopes'] = ['write']
    elif mutation == 'ciphertext': requested['oauth']['client_secret_encrypted'] = 'injected-canary'
    elif mutation == 'state': requested['oauth']['state'] = 'injected-canary'
    elif mutation == 'reference': requested['oauth']['configuration_refs'] = {'access_token': {'source': 'project_environment', 'key': 'TOKEN'}}
    with pytest.raises(ConfigurationError) as denied:
        merge_public_oauth_edit(current, requested)
    assert 'canary' not in str(denied.value)


@pytest.mark.parametrize('private', ['access_token', 'refresh_token', 'client_secret_encrypted', 'device_code', 'code_verifier_encrypted', 'state'])
def test_public_create_cannot_persist_private_protocol_source(private):
    with pytest.raises(ConfigurationError) as denied:
        CreateToolInput(project_id=uuid4(), name='Injected OAuth', type='mcp',
            config={'server': {'url': 'https://mcp.example/mcp'}, 'oauth': {private: 'private-canary'}})
    assert 'private-canary' not in str(denied.value)


@pytest.mark.parametrize('response_type', [CreateReleaseOutput, ListReleasesOutput, ReleaseResponse])
def test_release_views_strip_private_oauth_without_rewriting_original_snapshot_identity(response_type):
    import hashlib
    import json
    original = {'tools': {'snapshots': [{'id': str(uuid4()), 'type': 'mcp', 'config': source()}]}}
    snapshot = original['tools']['snapshots'][0]
    snapshot['hash'] = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
    untouched = deepcopy(original)
    response = response_type(id=uuid4(), project_id=uuid4(), agent_id=uuid4(), version='draft',
        status='draft', runtime_config=original)
    public = response.model_dump()['runtime_config']['tools']['snapshots'][0]
    assert 'canary' not in str(public)
    assert public['hash'] == snapshot['hash']
    assert public['configuration_view'] == 'redacted_metadata'
    assert response.runtime_config == untouched and original == untouched


def test_protocol_input_errors_and_repr_do_not_echo_secret_state_or_code():
    from pydantic import ValidationError
    from modules.agent.application.dtos.mcp_oauth_dtos import McpOAuthStartInput, McpOAuthCompleteInput
    with pytest.raises(ValidationError) as invalid:
        McpOAuthStartInput(tool_id=uuid4(), client_secret='private-client-canary')
    assert 'private-client-canary' not in str(invalid.value)
    complete = McpOAuthCompleteInput(tool_id=uuid4(), code='private-code-canary', state='private-state-canary')
    assert 'canary' not in repr(complete)
