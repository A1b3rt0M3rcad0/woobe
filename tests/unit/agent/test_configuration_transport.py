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
