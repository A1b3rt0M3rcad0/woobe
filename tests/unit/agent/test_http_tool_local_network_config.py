import ipaddress

import httpx
import pytest

from modules.agent.infra.adapters import tool_executor
from modules.agent.infra.adapters.tool_executor import HttpToolExecutor, _blocked_address
from shared.infra.config import Settings


@pytest.mark.parametrize(
    "raw_address",
    [
        "127.0.0.1",
        "::1",
        "10.0.0.10",
        "172.16.0.10",
        "192.168.1.10",
        "fc00::1",
    ],
)
def test_local_network_flag_allows_loopback_and_private_addresses(raw_address: str):
    address = ipaddress.ip_address(raw_address)
    assert _blocked_address(address, allow_local_networks=True) is False


@pytest.mark.parametrize(
    "raw_address",
    [
        "169.254.169.254",
        "fe80::1",
        "0.0.0.0",
        "224.0.0.1",
    ],
)
def test_local_network_flag_keeps_special_addresses_blocked(raw_address: str):
    address = ipaddress.ip_address(raw_address)
    assert _blocked_address(address, allow_local_networks=True) is True


def test_local_network_flag_is_disabled_by_default():
    address = ipaddress.ip_address("127.0.0.1")
    assert _blocked_address(address) is True


@pytest.mark.asyncio
async def test_executor_blocks_localhost_by_default():
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"ok": True}))
    )
    executor = HttpToolExecutor(client=client)
    try:
        result = await executor.execute("GET", "http://localhost:3001/health")
    finally:
        await client.aclose()

    assert result.success is False
    assert "target URL is not public" in str(result.error)


@pytest.mark.asyncio
async def test_executor_allows_localhost_when_enabled():
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"ok": True}))
    )
    executor = HttpToolExecutor(client=client, allow_local_networks=True)
    try:
        result = await executor.execute("GET", "http://localhost:3001/health")
    finally:
        await client.aclose()

    assert result.success is True
    assert result.status_code == 200


@pytest.mark.asyncio
async def test_local_mode_still_blocks_dns_resolution_change(monkeypatch):
    resolutions = iter(
        [
            frozenset({"127.0.0.1"}),
            frozenset({"127.0.0.2"}),
        ]
    )
    monkeypatch.setattr(
        tool_executor,
        "_validated_local_addresses",
        lambda _url: next(resolutions),
    )
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"ok": True}))
    )
    executor = HttpToolExecutor(client=client, allow_local_networks=True)
    try:
        result = await executor.execute("GET", "http://localhost:3001/health")
    finally:
        await client.aclose()

    assert result.success is False
    assert "DNS resolution changed" in str(result.error)


def test_settings_reads_local_network_flag_from_environment(monkeypatch):
    monkeypatch.setenv("WOOBE_HTTP_TOOL_ALLOW_LOCAL_NETWORKS", "true")
    monkeypatch.setenv("WOOBE_DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    monkeypatch.setenv("WOOBE_ENCRYPTION_KEY", "local-test-encryption-key-123456789")
    monkeypatch.setenv("WOOBE_RABBITMQ_URL", "amqp://user:pass@localhost:5672/")

    settings = Settings(service_role="worker", _env_file=None)

    assert settings.http_tool_allow_local_networks is True
