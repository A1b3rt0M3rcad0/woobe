import httpx
import pytest

from modules.agent.infra.adapters.configuration_transport import BoundConfigurationCredential, ConfigurationTransport
from shared.contracts.project_configuration import ConfigurationError

CANARY = "private-outbound-canary"


@pytest.mark.asyncio
async def test_material_is_only_in_authenticated_hop_not_retained_request_or_errors():
    resolved, sent = [], []
    async def resolve(url):
        resolved.append(url)
        return CANARY
    async def send(request):
        sent.append(request)
        assert request.headers["Authorization"] == "Bearer " + CANARY
        assert CANARY.encode() not in request.content
        return httpx.Response(401, text=CANARY, request=request)
    credential = BoundConfigurationCredential(resolve)
    transport = ConfigurationTransport(credential, transport=httpx.MockTransport(send))
    async with httpx.AsyncClient(transport=transport) as client:
        response = await client.post("https://provider.example/v1/chat", json={"model": "test"})
    assert response.status_code == 401
    assert CANARY not in response.text
    assert "authorization" not in sent[0].headers
    assert CANARY not in repr(credential)
    assert resolved == ["https://provider.example/v1/chat"]


@pytest.mark.asyncio
async def test_redirect_rechecks_actual_destination_before_sending_any_header():
    checks, sent = [], []
    async def resolve(url):
        checks.append(url)
        if not url.startswith("https://provider.example/v1/"):
            raise ConfigurationError("CONFIG_DESTINATION_CHANGED")
        return CANARY
    async def send(request):
        sent.append(str(request.url))
        return httpx.Response(307, headers={"Location": "https://other.example/stolen"})
    transport = ConfigurationTransport(BoundConfigurationCredential(resolve), transport=httpx.MockTransport(send))
    async with httpx.AsyncClient(transport=transport, follow_redirects=True) as client:
        with pytest.raises(ConfigurationError) as error:
            await client.post("https://provider.example/v1/chat", json={"input": "hello"})
    assert error.value.code == "CONFIG_DESTINATION_CHANGED"
    assert sent == ["https://provider.example/v1/chat"]
    assert len(checks) == 2


@pytest.mark.asyncio
async def test_revocation_between_requests_blocks_reused_client():
    calls = 0
    async def resolve(url):
        nonlocal calls
        calls += 1
        if calls > 1:
            raise ConfigurationError("CONFIG_VALUE_REVOKED")
        return CANARY
    sent = []
    async def send(request):
        sent.append(str(request.url))
        return httpx.Response(200, json={"ok": True})
    transport = ConfigurationTransport(BoundConfigurationCredential(resolve), transport=httpx.MockTransport(send))
    async with httpx.AsyncClient(transport=transport) as client:
        await client.post("https://provider.example/v1/chat")
        with pytest.raises(ConfigurationError) as error:
            await client.post("https://provider.example/v1/chat")
    assert error.value.code == "CONFIG_VALUE_REVOKED"
    assert len(sent) == 1


@pytest.mark.asyncio
async def test_compatibility_fallback_keeps_resolver_until_transport():
    from types import SimpleNamespace as N
    from unittest.mock import AsyncMock, Mock
    from modules.agent.application.interfaces.execution_context import current_execution, new_execution_context
    from modules.agent.infra.execution.explicit_runtime_persistence import ExplicitRuntimePersistenceMixin
    resolve = AsyncMock()
    credential = BoundConfigurationCredential(resolve)
    factory = N(create_chat_model=Mock(return_value=N(ainvoke=AsyncMock(return_value="answer"))))
    context = new_execution_context()
    context.prepared_fallback = {"api_key": credential, "base_url": "https://fallback.test/v1"}
    token = current_execution.set(context)
    try:
        result = await ExplicitRuntimePersistenceMixin._try_fallback(N(_llm_factory=factory),
            N(provider="openai", model="main", fallback_provider="openai", fallback_model="fallback",
                fallback_credential_id="credential", temperature=0.2, max_output_tokens=50),
            [], False, "unavailable")
    finally:
        current_execution.reset(token)
    assert result[0] == "answer"
    assert factory.create_chat_model.call_args.kwargs["api_key"] is credential
    resolve.assert_not_awaited()
