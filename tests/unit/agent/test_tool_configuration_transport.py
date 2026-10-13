from types import SimpleNamespace
from uuid import uuid4
from base64 import b64encode
import httpx
import pytest
from modules.agent.application.interfaces.execution_context import current_execution, new_execution_context
from modules.agent.application.interfaces import project_configuration as port
from modules.agent.domain.tool_configuration import tool_dependencies, validate_tool_authentication
from modules.agent.infra.adapters.tool_configuration_transport import configuration_bound_tool, current_tool_configuration
from modules.agent.infra.adapters.tool_executor import HttpToolExecutor
from shared.contracts.project_configuration import ConfigurationError


def tool(auth):
    return SimpleNamespace(id=uuid4(), project_id=uuid4(), config={"url": "https://approved.example/api", "authentication": auth})


def binding(kind, **fields):
    return {"type": kind, "fields": {name: {"source": "project_environment", "key": key} for name, key in fields.items()}}


@pytest.mark.asyncio
@pytest.mark.parametrize("auth,expected", [
    (binding("bearer", token="TOKEN"), {"authorization": "Bearer canary-token"}),
    (binding("api_key", api_key="TOKEN"), {"x-api-key": "canary-token"}),
    (binding("basic", username="USER", password="PASSWORD"), {"authorization": "Basic " + b64encode(b"canary-user:canary-password").decode()}),
    (binding("headers", **{"X-Client": "USER", "X-Token": "TOKEN"}), {"x-client": "canary-user", "x-token": "canary-token"}),
])
async def test_tool_injects_at_send_redacts_echo_and_rechecks_each_call(monkeypatch, auth, expected):
    target = tool(auth)
    context = new_execution_context()
    context.project_id, context.run_id = target.project_id, uuid4()
    calls, sent = [], []
    revoked = False
    async def resolve(**identity):
        assert identity["project_id"] == target.project_id
        assert identity["run_id"] == context.run_id
        assert identity["consumer_id"] == target.id
        assert identity["destination"] == target.config["url"]
        calls.append(identity)
        if revoked:
            raise ConfigurationError("CONFIG_VALUE_REVOKED")
        field = identity["field_path"].rsplit("/", 1)[-1]
        return {"token": "canary-token", "api_key": "canary-token", "username": "canary-user", "password": "canary-password", "X-Client": "canary-user", "X-Token": "canary-token"}[field]
    monkeypatch.setattr(port, "_runtime_resolver", resolve)
    monkeypatch.setattr("modules.agent.infra.adapters.tool_executor._validated_local_addresses", lambda url: frozenset({"8.8.8.8"}))
    def send(request):
        for name, value in expected.items():
            assert request.headers[name] == value
        sent.append(request)
        return httpx.Response(200, json={"innocent": list(expected.values()), "password_echo": "canary-password"}, request=request)
    class Runtime:
        @configuration_bound_tool
        async def execute(self, target):
            return await executor.execute("GET", target.config["url"])
    token = current_execution.set(context)
    try:
        async with httpx.AsyncClient(transport=httpx.MockTransport(send)) as client:
            executor = HttpToolExecutor(client=client)
            result = await Runtime().execute(target)
            assert result.success
            for secret in expected.values():
                assert secret not in str(result.output)
            assert all(name not in sent[0].headers for name in expected)
            assert current_tool_configuration.get() is None
            revoked = True
            with pytest.raises(ConfigurationError, match="revoked"):
                await Runtime().execute(target)
            assert len(sent) == 1
            assert current_tool_configuration.get() is None
    finally:
        current_execution.reset(token)


def test_tool_reference_change_has_distinct_revision_and_no_value():
    target = tool(binding("basic", username="USER", password="PASSWORD"))
    dependencies = tool_dependencies(target)
    assert len(dependencies) == 2
    original = dependencies[0].definition_revision
    target.config["url"] = "https://other.example/api"
    assert tool_dependencies(target)[0].definition_revision != original
    target.config["body"] = {"source": "project_environment", "key": "PASSWORD"}
    with pytest.raises(ConfigurationError):
        validate_tool_authentication(target.config)


@pytest.mark.asyncio
async def test_no_unauthenticated_fallback_outside_accepted_run():
    class Runtime:
        @configuration_bound_tool
        async def execute(self, target):
            pytest.fail("must not send")
    token = current_execution.set(None)
    try:
        with pytest.raises(ConfigurationError):
            await Runtime().execute(tool(binding("bearer", token="TOKEN")))
    finally:
        current_execution.reset(token)


@pytest.mark.asyncio
async def test_anonymous_configuration_does_not_grant_private_network_access(monkeypatch):
    target = tool(binding('none'))
    context = new_execution_context()
    context.project_id, context.run_id = target.project_id, uuid4()
    monkeypatch.setattr('modules.agent.infra.adapters.tool_executor._validated_public_addresses', lambda _: None)
    monkeypatch.setattr('modules.agent.infra.adapters.tool_executor._validated_local_addresses', lambda _: pytest.fail('Anonymous binding is not a destination grant'))
    class Runtime:
        @configuration_bound_tool
        async def execute(self, target):
            return await executor.execute('GET', 'http://127.0.0.1/private')
    token = current_execution.set(context)
    try:
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: pytest.fail('Must not send'))) as client:
            executor = HttpToolExecutor(client=client)
            result = await Runtime().execute(target)
            assert not result.success and 'SSRF blocked' in result.error
    finally:
        current_execution.reset(token)
