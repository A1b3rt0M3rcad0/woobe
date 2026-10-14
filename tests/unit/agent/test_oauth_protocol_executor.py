import logging

import httpx
import pytest

from modules.agent.infra.adapters.oauth_protocol_executor import OAuthProtocolExecutor
from modules.agent.infra.adapters import tool_executor
from modules.agent.application.interfaces.oauth_protocol import private_oauth_protocol_response
from shared.security.redaction import SensitiveDataLoggingFilter


@pytest.mark.asyncio
@pytest.mark.parametrize('status', [200, 401])
async def test_private_protocol_response_is_owner_local_and_ordinary_tools_stay_redacted(monkeypatch, status):
    monkeypatch.setattr(tool_executor, '_validated_public_addresses', lambda *args, **kwargs: {'203.0.113.10'})
    body = {'access_token': 'access-canary', 'client_secret': 'client-canary', 'token_type': 'Bearer',
        'token_endpoint_auth_method': 'client_secret_post', 'nested': {'access_token': 'nested-canary'},
        'device_authorization_endpoint': 'https://approved.example/device',
        'authorization_servers': ['https://approved.example']}
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(status, json=body))) as client:
        executor = tool_executor.HttpToolExecutor(client=client)
        private = await OAuthProtocolExecutor(executor).execute('POST', 'https://approved.example/token')
        assert private_oauth_protocol_response.get() is False
        ordinary = await executor.execute('POST', 'https://approved.example/token')
    assert 'canary' not in str(ordinary.output)
    if status == 200:
        assert private.output['body']['nested']['access_token'] == '[REDACTED]'
        assert private.output['body']['access_token'] == 'access-canary'
        assert private.output['body']['client_secret'] == 'client-canary'
        assert private.output['body']['token_type'] == 'Bearer'
        assert private.output['body']['token_endpoint_auth_method'] == 'client_secret_post'
        assert private.output['body']['device_authorization_endpoint'] == 'https://approved.example/device'
        assert private.output['body']['authorization_servers'] == ['https://approved.example']
    else:
        assert 'canary' not in str(private.output)


def test_httpx_url_log_arguments_never_expose_oauth_query_values():
    record = logging.LogRecord('httpx', logging.INFO, 'client.py', 1, 'HTTP Request: %s %s',
        ('GET', httpx.URL('https://approved.example/authorize?state=state-canary&code=code-canary&page=1')), None)
    assert SensitiveDataLoggingFilter().filter(record)
    assert 'canary' not in record.getMessage()
    assert '/authorize' in record.getMessage() and 'page=1' in record.getMessage()


def test_malformed_url_log_cannot_break_logging_or_echo_credentials():
    record = logging.LogRecord('httpx', logging.INFO, 'client.py', 1,
        'Failed URL %s', ('https://approved.example:broken/?state=state-canary',), None)
    assert SensitiveDataLoggingFilter().filter(record)
    assert 'canary' not in record.getMessage()


@pytest.mark.asyncio
@pytest.mark.parametrize('code,expected', [('authorization_pending', 'authorization_pending'),
    ('slow_down', 'slow_down'), ('client-canary', 'oauth_protocol_error'), (['client-canary'], 'oauth_protocol_error')])
async def test_failed_protocol_preserves_machine_state_without_provider_echo(monkeypatch, code, expected):
    monkeypatch.setattr(tool_executor, '_validated_public_addresses', lambda *args, **kwargs: {'203.0.113.10'})
    body = {'error': code, 'error_description': 'client-canary refresh-canary device-canary',
        'device_code': 'device-canary', 'nested': {'text': 'client-canary'}}
    challenge = 'Bearer resource_metadata="https://approved.example/.well-known/oauth-protected-resource"'
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(400,
        json=body, headers={'WWW-Authenticate': challenge}))) as client:
        result = await OAuthProtocolExecutor(tool_executor.HttpToolExecutor(client=client)).execute(
            'POST', 'https://approved.example/token')
    assert not result.success and result.status_code == 400
    assert result.output['body'] == {'error': expected}
    assert result.output['headers']['www-authenticate'] == challenge
    assert 'canary' not in str(result)


@pytest.mark.asyncio
async def test_failed_protocol_transport_does_not_echo_request_query_or_material(monkeypatch):
    monkeypatch.setattr(tool_executor, '_validated_public_addresses', lambda *args, **kwargs: {'203.0.113.10'})
    def fail(request):
        raise httpx.RequestError('Connection failed for ' + str(request.url) + ' client-canary', request=request)
    async with httpx.AsyncClient(transport=httpx.MockTransport(fail)) as client:
        result = await OAuthProtocolExecutor(tool_executor.HttpToolExecutor(client=client)).execute(
            'GET', 'https://approved.example/authorize?state=state-canary&code=code-canary')
    assert not result.success and 'canary' not in str(result)
    assert private_oauth_protocol_response.get() is False


@pytest.mark.parametrize('header', ['Bearer token-canary',
    'Bearer resource_metadata="https://user:secret-canary@approved.example/metadata"',
    'Bearer resource_metadata="https://approved.example/metadata?token=token-canary"',
    'Bearer resource_metadata="https://approved.example:broken/metadata"',
    'Bearer resource_metadata="https://approved.example/metadata#token-canary"'])
def test_resource_challenge_exception_never_restores_credentials(header):
    assert tool_executor._oauth_resource_challenge(header) is None
