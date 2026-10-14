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
    assert private.output['body']['nested']['access_token'] == '[REDACTED]'
    if status == 200:
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
