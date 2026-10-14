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
        bare = expected.get('authorization', 'unchanged').split(' ', 1)[-1]
        return httpx.Response(200, json={"innocent": list(expected.values()), "proof": bare, "password_echo": "canary-password"}, request=request)
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
            if 'authorization' in expected:
                assert expected['authorization'].split(' ', 1)[1] not in str(result.output)
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


@pytest.mark.parametrize('url,expected', [
    ('https://approved.example/api/search?q={{query}}', 'https://approved.example/api/search'),
    ('https://approved.example/api/items/{{id}}', 'https://approved.example/api/items/'),
    ('https://approved.example/api/items/{{id}}/events/{{event}}', 'https://approved.example/api/items/'),
])
def test_parameterized_tool_urls_retain_a_static_credential_boundary(url, expected):
    from modules.core.infra.database.configuration_resolution import destination_matches
    target = tool(binding('bearer', token='TOKEN'))
    target.config['url'] = url
    dependency = tool_dependencies(target)[0]
    assert dependency.destination == expected
    assert destination_matches(dependency.destination, expected.rstrip('/') + '/123?public=true')
    assert not destination_matches(dependency.destination, 'https://unapproved.example/api/items/123')
    assert not destination_matches(dependency.destination, 'https://approved.example/outside')
    for path in ('../outside', '%2e%2e/outside', '%252e%252e/outside'):
        with pytest.raises(ConfigurationError):
            destination_matches(dependency.destination, expected.rstrip('/') + '/' + path)
    revision = dependency.definition_revision
    target.config['url'] = url + '&changed=true'
    assert tool_dependencies(target)[0].definition_revision != revision


@pytest.mark.parametrize('url', [
    'https://{{host}}/api', '{{scheme}}://approved.example/api',
    'https://user:password@approved.example/api', 'https://approved.example/{{invalid',
    'https://approved.example/api#fragment', 'https://approved.example\\unapproved.example/api',
])
def test_dynamic_or_ambiguous_authority_never_qualifies_a_tool_binding(url):
    target = tool(binding('bearer', token='TOKEN'))
    target.config['url'] = url
    with pytest.raises(ConfigurationError):
        tool_dependencies(target)


@pytest.mark.asyncio
async def test_route_credentials_resolve_only_for_selected_scope_and_none_suppresses_parent(monkeypatch):
    from modules.agent.infra.adapters.tool_runtime import HttpToolRuntime
    parent = binding('headers', **{'X-Parent': 'PARENT'})
    scoped = binding('bearer', token='ROUTE')
    target = SimpleNamespace(id=uuid4(), project_id=uuid4(), timeout_ms=1000,
        input_schema=None, config={'mode': 'group', 'base_url': 'https://approved.example',
            'authentication': parent, 'permission': {'mode': 'allow'}, 'routes': [
                {'id': 'protected/one', 'name': 'Protected', 'description': 'Protected read', 'path': '/protected',
                 'method': 'GET', 'authentication': scoped, 'default_permission': 'allow'},
                {'id': 'public', 'name': 'Public', 'description': 'Public read', 'path': '/public',
                 'method': 'GET', 'authentication': {'type': 'none'}, 'default_permission': 'allow'}]})
    validate_tool_authentication(target.config)
    dependencies = tool_dependencies(target)
    assert {dep.field_path for dep in dependencies} == {
        '/config/authentication/fields/X-Parent', '/config/routes/protected~1one/authentication/fields/token'}
    assert {dep.destination for dep in dependencies} == {'https://approved.example/', 'https://approved.example/protected'}
    calls, sent = [], []
    async def resolve(**identity):
        calls.append(identity)
        assert identity['destination'] == 'https://approved.example/protected'
        return 'parent-canary' if identity['field_path'].startswith('/config/authentication') else 'route-canary'
    monkeypatch.setattr(port, '_runtime_resolver', resolve)
    monkeypatch.setattr('modules.agent.infra.adapters.tool_executor._validated_local_addresses', lambda url: frozenset({'8.8.8.8'}))
    monkeypatch.setattr('modules.agent.infra.adapters.tool_executor._validated_public_addresses', lambda url: frozenset({'8.8.8.8'}))
    def send(request):
        sent.append(str(request.url))
        if request.url.path == '/protected':
            assert request.headers['authorization'] == 'Bearer route-canary'
            assert request.headers['x-parent'] == 'parent-canary'
        else:
            assert 'authorization' not in request.headers and 'x-parent' not in request.headers
            assert 'cookie' not in request.headers
        return httpx.Response(200, headers={'Set-Cookie': 'session=private-peer-cookie; Path=/'},
                              json={'echo': dict(request.headers)}, request=request)
    context = new_execution_context(); context.project_id, context.run_id = target.project_id, uuid4()
    token = current_execution.set(context)
    try:
        async with httpx.AsyncClient(transport=httpx.MockTransport(send)) as client:
            runtime = HttpToolRuntime(HttpToolExecutor(client=client))
            first = await runtime.execute(target, {'__mcp_tool_name': 'protected/one'})
            assert first.success and 'route-canary' not in str(first.output) and 'parent-canary' not in str(first.output)
            before = len(calls)
            second = await runtime.execute(target, {'__mcp_tool_name': 'public'})
            assert second.success and len(calls) == before
            assert sent == ['https://approved.example/protected', 'https://approved.example/public']
    finally:
        current_execution.reset(token)
    assert current_tool_configuration.get() is None


def test_route_reference_cannot_authorize_absolute_url_or_model_visible_copy():
    config = {'base_url': 'https://approved.example', 'routes': [{'id': 'one', 'path': '//foreign.example',
        'authentication': binding('bearer', token='TOKEN')} ]}
    with pytest.raises(ConfigurationError):
        tool_dependencies(SimpleNamespace(project_id=uuid4(), id=uuid4(), config=config))
    config['routes'][0]['path'] = '/one'
    config['routes'][0]['body'] = {'source': 'project_environment', 'key': 'TOKEN'}
    with pytest.raises(ConfigurationError):
        validate_tool_authentication(config)
