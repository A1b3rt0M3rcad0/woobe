"""Real new CLI + API + Worker configuration lifecycle, including rotation fences.

Set WOOBE_TEST_CONFIGURATION_CLI=true alongside the exact WOOBE_TEST_CLI_SHA.
The legacy pinned CLI exercises the unchanged compatibility suite.
"""
import pytest
from uuid import uuid4
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tests.integration.cli.test_control_plane_workflow import cli
from tests.unit.package.test_configuration_package_v2 import package, network_package
import json
import os

pytestmark = pytest.mark.skipif(not (os.environ.get("WOOBE_CONFIGURATION_CLI_BINARY") or os.environ.get("WOOBE_TEST_CONFIGURATION_CLI") == "true"), reason="Requires the configuration-capable CLI; pinned legacy CLI is covered separately")


@pytest.fixture(autouse=True)
def configuration_binary(monkeypatch):
    # Keep the legacy binary for the rest of the suite; only these feature
    # contracts select the separately reviewed, exact paired executable.
    if os.environ.get("WOOBE_CONFIGURATION_CLI_BINARY"):
        monkeypatch.setenv("WOOBE_CLI_BINARY", os.environ["WOOBE_CONFIGURATION_CLI_BINARY"])
        monkeypatch.setenv("WOOBE_TEST_CLI_SHA", os.environ["WOOBE_CONFIGURATION_CLI_SHA"])


@pytest.mark.asyncio
async def test_project_summary_cursor_is_page_evidence_not_global_readiness(cli):
    project = await cli.data('project', 'create', body={
        'workspace_id': cli.workspace_id, 'name': 'Paged configuration', 'slug': str(uuid4())})
    cli.project_id = project['id']
    for i in range(3):
        await cli.data('project', 'network', 'create', body={'name': f'Unselected Network {i}'})
    cursor, counts = None, []
    while True:
        args = ['project', 'configuration', 'summary', '--env', 'staging', '--limit', '1']
        if cursor:
            args += ['--cursor', cursor]
        payload = await cli.run(*args, expected=9)
        page = payload['data']
        assert page['scope'] == 'current_selections_page' and not page['complete']
        assert page['page_state'] == 'ready' and page['unselected_target_count'] == 1
        counts.append(page['inspected_target_count'])
        if not page['has_next']:
            assert page['next_cursor'] is None
            break
        cursor = page['next_cursor']
        assert len(counts) < 4
    assert counts == [1, 1, 1]
    full = (await cli.run('project', 'configuration', 'summary', '--env', 'staging'))['data']
    assert full['scope'] == 'current_selections' and full['complete'] and full['inspected_target_count'] == 3

@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["agent", "network"])
async def test_remote_configuration_development_and_activation(cli, tmp_path, kind):
    project = await cli.data("project", "create", body={"workspace_id": cli.workspace_id, "name": "CLI structural smoke", "slug": str(uuid4())})
    cli.project_id = project["id"]
    source = tmp_path / "support"
    source.mkdir()
    files = package(source)
    provider_url = os.environ["WOOBE_TEST_FAKE_PROVIDER_URL"]
    files["woobe.yaml"]["spec"]["connections"]["primary"].update(provider="custom", metadata={
        "provider_family":"openai", "compatibility":"compatible", "base_url":provider_url})
    files["model.yaml"]["spec"].update(provider="custom", model="fake-success", base_url=provider_url)
    for name, document in files.items():
        (source / name).write_text(json.dumps(document))
    if kind == "network":
        network_package(files, "draft")
        for name, document in files.items():
            (source / name).write_text(json.dumps(document))
    approved = (await cli.run("package", "plan", str(source), "--structural", "--save-plan", str(tmp_path / "plan.json")))["data"]
    assert approved["installation_mode"] == "structural"
    applied = (await cli.run("package", "import", "--plan-file", str(tmp_path / "plan.json"), "--checkpoint", str(tmp_path / "checkpoint.json"), "--wait", "--wait-timeout", "60s"))["data"]
    assert applied["state"] == "succeeded", applied
    assert applied["installation_status"] == "installed"
    assert applied["execution_ready"] is False
    summary = await cli.data("request", "GET", f"/core/projects/{cli.project_id}/configuration/summary")
    assert summary["state"] == "blocked" and summary["missing_key_count"] == 1, summary
    cli_summary = await cli.run("project", "configuration", "summary", "--env", "draft", expected=6)
    assert cli_summary["data"]["blocked_key_count"] == 1
    if kind == "agent":
        _, restricted = await cli.issue("workspace", "control-key", "create", body={
            "name": "Configuration metadata only", "expires_at": (datetime.now(UTC) + timedelta(minutes=30)).isoformat(), "on_project_create_permissions": [],
            "project_grants": [{"project_id": cli.project_id, "permissions": ["project:read", "project:environment:read"]}]})
        denied = await cli.run("request", "GET", f"/core/projects/{cli.project_id}/configuration/summary", key=restricted, expected=4)
        assert "affected_target_count" not in str(denied)
    target = next(x["resource_id"] for x in applied["inventory"] if x["action"] == ("prepare_network" if kind == "network" else "prepare_inactive_agent"))
    exported = (await cli.run("package", "export", kind, target, "--package-schema", "2.0", "--destination", str(tmp_path / "exported")))["data"]
    assert exported["package_schema_version"] == "2.0"
    await cli.run("package", "validate", str(tmp_path / "exported"), "--locked")
    registry = tmp_path / "development"
    registry.mkdir()
    await cli.run("init", "--root", ".woobe", cwd=registry)
    pulled = (await cli.run(kind, target, "pull", "--alias", "support", cwd=registry))["data"]
    assert pulled["pulled"]
    await cli.run(kind, "@support", "validate", cwd=registry)
    pushed = (await cli.run(kind, "@support", "push", cwd=registry))["data"]
    assert pushed["pushed"] and pushed["environment"] == "draft"
    opened = (await cli.run(kind, "@support", "draft", "open", "configuration", cwd=registry))["data"]
    saved = (await cli.run(kind, "@support", "draft", "push", cwd=registry))["data"]
    checkpoint = (await cli.run(kind, "@support", "revision", "create", "--message", "Remote configuration", cwd=registry))["data"]
    assert checkpoint["definition_digest_scope"] == "woobe-portable-definition@2.0"
    registered = (await cli.run(kind, "@support", "draft", "checkpoint", checkpoint["revision_id"], cwd=registry))["data"]
    assert registered["record"] == checkpoint
    assert registered["author_artifact_status"] == "retained_custody"
    staged = (await cli.run(kind, "@support", "stage", "--revision", checkpoint["revision_id"], cwd=registry))["data"]
    assert staged["state"] in {"preparing", "prepared", "accepted"}, staged
    import asyncio
    operation = await cli.data("request", "GET", f"/projects/{cli.project_id}/packages/operations/{staged['preparation_operation_id']}")
    for _ in range(120):
        if operation["terminal"]:
            break
        await asyncio.sleep(.25)
        operation = await cli.data("request", "GET", f"/projects/{cli.project_id}/packages/operations/{staged['preparation_operation_id']}")
    assert operation["state"] == "succeeded", operation
    candidate = (await cli.run(kind, "@support", "candidate", staged["candidate_id"], cwd=registry))["data"]
    assert candidate["state"] == "ready" and candidate["runtime_digest"]
    assert candidate["record_digest"] == checkpoint["record_digest"]
    assert not candidate["published"] and not candidate["production_changed"]

    assert operation["configuration_ready"] is False
    assert operation["execution_ready"] is False
    assert operation["lifecycle_state"] == "candidate"
    config_base = f"/core/projects/{cli.project_id}/configuration"
    readiness = await cli.data("request", "GET", config_base + "/readiness/" + kind + "/" + target, "--query", "environment=staging", "--query", "version_id=" + candidate["snapshot_id"])
    assert readiness["state"] == "blocked" and readiness["required_key_count"] == 1
    keys = await cli.data("request", "GET", config_base + "/keys")
    assert len(keys["items"]) == 1
    key = keys["items"][0]
    credentials = await cli.data("project", "provider-credential", "list")
    credential = credentials[0]
    await cli.data("request", "POST", config_base + "/use-policies", body={"key_id":key["id"],
        "consumer_kind":"provider_credential", "consumer_scope":credential["id"], "destination":provider_url,
        "environments":["staging", "production"], "field_paths":["/authentication/fields/api_key"], "expected_revision":0})
    canary = "fake-api-key"
    cli.secret_values.add(canary)
    await cli.data("request", "PUT", config_base + "/keys/" + key["id"] + "/values/staging",
        body={"expected_revision":0, "value":canary})
    evaluation = (await cli.run(kind, "@support", "test", "--candidate", candidate["candidate_id"], "--yes", body={
        "schema_version":"1.0", "suite_id":"configuration-smoke", "suite_version":"1", "dataset_version":"1",
        "cases":[{"id":"greeting", "message":"Hello"}]}, cwd=registry))["data"]
    assert evaluation["state"] == "passed"
    publication = (await cli.run(kind, "@support", "publish", "--candidate", candidate["candidate_id"],
        "--evaluation", evaluation["evaluation_id"], "--notes", "Qualified configuration smoke", "--yes", cwd=registry))["data"]
    if not publication.get("published"):
        publication = (await cli.run(kind, "@support", "publication", publication["publication_id"], "reconcile", "--yes", cwd=registry))["data"]
    assert publication["published"] and not publication["production_changed"]
    selection = (await cli.run(kind, "@support", "current", "--env", "production", cwd=registry))["data"]
    plan_args = (kind, "@support", "deployment", "plan", "--release", publication["release_id"],
        "--expected-generation", str(selection["environment_generation"]), "--notes", "Configuration-qualified activation")
    missing = await cli.run(*plan_args, cwd=registry, expected=(2,6,9))
    assert missing["error"].get("domain_code") == "CONFIG_VALUE_MISSING", missing
    await cli.data("request", "PUT", config_base + "/keys/" + key["id"] + "/values/production",
        body={"expected_revision":0, "value":canary})
    plan = (await cli.run(*plan_args, cwd=registry))["data"]
    await cli.data("request", "PUT", config_base + "/keys/" + key["id"] + "/values/production",
        body={"expected_revision":1, "value":canary})
    await cli.run(kind, "@support", "lease", "acquire", "--scope", "production", cwd=registry)
    rejected = await cli.run(kind, "@support", "deployment", "apply", plan["plan_id"], "--yes", cwd=registry, expected=(2,6,9))
    assert "CONFIG_REVISION_CONFLICT" in str(rejected), rejected
    replanned = (await cli.run(*plan_args, cwd=registry))["data"]
    deployed = (await cli.run(kind, "@support", "deployment", "apply", replanned["plan_id"], "--yes", cwd=registry))["data"]
    assert deployed["state"] == "committed" and deployed["selection_changed"]
    assert deployed["release_id"] == publication["release_id"]
    summary = await cli.data("request", "GET", config_base + "/summary", "--query", "environment=production")
    assert summary["state"] in {"ready", "ready_with_notices"} and summary["blocked_key_count"] == 0, summary


@pytest.mark.asyncio
async def test_legacy_provider_can_be_edited_by_new_cli_and_web(cli, tmp_path):
    import asyncio
    import yaml
    project = await cli.data('project', 'create', body={'workspace_id':cli.workspace_id,
        'name':'Central legacy Provider authoring', 'slug':str(uuid4())})
    cli.project_id = project['id']
    credential = await cli.data('project','provider-credential','create',body={
        'project_id':cli.project_id,'provider':'custom','name':'Deterministic', 'secret':'fake-api-key',
        'metadata':{'base_url':os.environ['WOOBE_TEST_FAKE_PROVIDER_URL'],'model':'fake-success'}})
    cli.secret_values.add('fake-api-key')
    model = await cli.data('project','provider-model','create',body={'project_id':cli.project_id,
        'provider_credential_id':credential['id'],'name':'Deterministic','model':'fake-success'})
    agent = await cli.data('project','agent','create',body={'project_id':cli.project_id,'name':'Legacy authoring',
        'provider':'custom','provider_model_id':model['id'],'provider_credential_id':credential['id'],
        'model':'fake-success','system_prompt':'Original objective','session_mode':'stateless','max_output_tokens':64})
    target = agent['id']
    await cli.data('project','agent','release','create',target,body={'project_id':cli.project_id,'agent_id':target,'version':'draft'})
    registry = tmp_path / 'development'; registry.mkdir()
    await cli.run('init','--root','.woobe',cwd=registry)
    await cli.run('agent',target,'pull','--alias','support',cwd=registry)
    await cli.run('agent','@support','push',cwd=registry)
    await cli.run('agent','@support','draft','open','configuration',cwd=registry)
    await cli.run('agent','@support','draft','push',cwd=registry)
    record = (await cli.run('agent','@support','revision','create','--message','Explicit reused connection',cwd=registry))['data']
    assert record['definition_digest_scope'] == 'woobe-portable-definition@2.0'
    await cli.run('agent','@support','draft','checkpoint',record['revision_id'],cwd=registry)
    await cli.run('agent','@support','stage','--revision',record['revision_id'],cwd=registry)
    # Exercise the public Web authoring endpoints against a separate retained
    # capture, including bindings derived from that capture (not CLI input).
    exported = await cli.data('request','POST',f'/projects/{cli.project_id}/packages/export',body={
        'kind':'Agent','target_id':target,'source':'draft','knowledge':'portable','development':True,
        'package_schema_version':'2.0'})
    base = f'/projects/{cli.project_id}/agents/{target}/asac'
    draft = await cli.data('request','POST',base+'/drafts',body={'operation_id':str(uuid4()),
        'name':'web-configuration','resource_uid':exported['source']['resource_uid'],'source_export_id':exported['export_id']})
    route = base + '/drafts/' + draft['draft_id']
    editor = await cli.data('request','GET',route+'/editor')
    entry = next(item for item in editor['files'] if item['path']==editor['entrypoint_path'])
    document = yaml.safe_load(entry['content'])
    document['metadata']['description'] = 'Edited through the Web source API'
    edited = await cli.data('request','PUT',route+'/editor',body={'operation_id':str(uuid4()),
        'expected_generation':draft['generation'],'files':[{'path':entry['path'],'content':yaml.safe_dump(document)}]})
    checkpoint = await cli.data('request','POST',route+'/checkpoint',body={'operation_id':str(uuid4()),
        'expected_generation':edited['generation'],'revision_id':'rv_'+str(uuid4()),'message':'Web schema2 checkpoint','parents':[]})
    assert checkpoint['record']['definition_digest_scope']=='woobe-portable-definition@2.0'
    staged = await cli.data('request','POST',route+'/stage',body={'operation_id':str(uuid4()),
        'expected_generation':edited['generation'],'revision_id':checkpoint['record']['revision_id']})
    for _ in range(240):
        operation = await cli.data('request','GET',f"/projects/{cli.project_id}/packages/operations/{staged['preparation_operation_id']}")
        if operation['terminal']:
            break
        await asyncio.sleep(.25)
    assert operation['state']=='succeeded', operation
    assert operation['configuration_ready'] is True, operation


@pytest.mark.asyncio
async def test_fresh_secret_api_requires_authorized_tool_use_and_preserves_revocation(cli):
    project = await cli.data('project','create',body={'workspace_id':cli.workspace_id,'name':'Central Secret writer','slug':str(uuid4())})
    cli.project_id=project['id']
    canary='fresh-secret-fixture-canary'
    cli.secret_values.add(canary)
    await cli.data('request','POST','/tools/secrets',body={'project_id':cli.project_id,'name':'tool-key','type':'api_key','value':canary})
    base=f'/core/projects/{cli.project_id}/configuration'
    keys=await cli.data('request','GET',base+'/keys')
    assert len(keys['items'])==1
    aliases=await cli.data('request','GET',base+'/legacy-bindings')
    assert len(aliases['items'])==1 and aliases['items'][0]['source_kind']=='secret'
    _,restricted=await cli.issue('workspace','control-key','create',body={
        'name':'Legacy Tool author without secret use approval','expires_at':(datetime.now(UTC)+timedelta(minutes=30)).isoformat(),
        'on_project_create_permissions':[], 'project_grants':[{'project_id':cli.project_id,
            'permissions':['project:read','tool:read','tool:write','secret:read','project:environment:read']}]})
    body={'project_id':cli.project_id,'name':'Secret consumer','type':'http','config':{
        'url':os.environ['WOOBE_TEST_FAKE_PROVIDER_URL'],'method':'GET','headers':[{'key':'Authorization','value':'{{secret:tool-key}}'}]},
        'input_schema':{'type':'object','properties':{}}}
    await cli.run('request','POST','/tools/tools',body=body,key=restricted,expected=4)
    # The rejected write must not leave an unauthorized Tool or central grant.
    assert (await cli.data('request','GET','/tools/tools','--query','project_id='+cli.project_id))==[]
    tool=await cli.data('request','POST','/tools/tools',body=body)
    readiness=await cli.data('request','GET',base+'/readiness/tool/'+tool['id'],'--query','environment=production')
    assert readiness['state']=='ready_with_notices'
    policy=(await cli.data('request','GET',base+'/keys/'+keys['items'][0]['id']+'/use-policies'))['items'][0]
    await cli.data('request','DELETE',base+'/use-policies/'+policy['id'],'--query','expected_revision='+str(policy['revision']))
    await cli.data('request','PATCH','/tools/tools/'+tool['id'],body={'name':'Renamed after revocation'})
    readiness=await cli.data('request','GET',base+'/readiness/tool/'+tool['id'],'--query','environment=production')
    assert readiness['state']=='blocked'
    assert readiness['dependencies'][0]['code']=='CONFIG_USAGE_NOT_AUTHORIZED'


@pytest.mark.asyncio
@pytest.mark.parametrize('protocol', ['http', 'mcp'])
@pytest.mark.parametrize('source', ['secret', 'inline'])
async def test_existing_tool_operations_use_central_material_and_preserve_revocations(cli, protocol, source):
    project = await cli.data('project', 'create', body={
        'workspace_id': cli.workspace_id, 'name': 'Detached Tool operation', 'slug': str(uuid4()),
    })
    cli.project_id = project['id']
    for name, value in [('auth', 'Bearer ephemeral-native-environment-token'),
                        ('token', 'ephemeral-native-tool-token')]:
        cli.secret_values.add(value)
        if source == 'secret':
            await cli.data('request', 'POST', '/tools/secrets', body={
                'project_id': cli.project_id, 'name': name, 'type': 'api_key', 'value': value,
            })
    headers = [{'key': 'Authorization', 'value': '{{secret:auth}}'},
               {'key': 'X-Tool-Token', 'value': '{{secret:token}}'}]
    if source == 'inline':
        headers = [{'key': 'Authorization', 'value': 'Bearer ephemeral-native-environment-token'},
                   {'key': 'X-Tool-Token', 'value': 'ephemeral-native-tool-token', 'sensitive': True}]
    endpoint = os.environ['WOOBE_TEST_FAKE_MCP_URL']
    config = ({'method': 'GET', 'url': endpoint.removesuffix('/mcp') + '/http-protected', 'headers': headers}
              if protocol == 'http' else {'mode': 'server', 'exposure': 'all_discovered',
                  'server': {'url': endpoint, 'transport': 'streamable_http', 'headers': headers}})
    tool = await cli.data('request', 'POST', '/tools/tools', body={
        'project_id': cli.project_id, 'name': 'Configured Tool', 'type': protocol,
        'config': config, 'input_schema': {'type': 'object', 'properties': {}},
    })
    if source == 'inline':
        assert 'ephemeral-native' not in str(tool)
        saved = await cli.data('request', 'GET', '/tools/tools', '--query', 'project_id=' + cli.project_id)
        assert 'ephemeral-native' not in str(saved)
        await cli.data('request', 'PATCH', '/tools/tools/' + tool['id'], body={'name': 'Safe rename'})
    route = '/tools/tools/execute' if protocol == 'http' else '/tools/mcp/refresh'
    result = await cli.data('request', 'POST', route, body={'tool_id': tool['id']})
    if protocol == 'http':
        assert result['success'] and result['output']['body']['authenticated'], result
    else:
        assert tool['config']['mcp_status'] == 'configuration_required'
        assert result['initialized'] and result['discovered_count'] == 1 and result['status'] == 'ready', result
    base = f'/core/projects/{cli.project_id}/configuration'
    key = (await cli.data('request', 'GET', base + '/keys'))['items'][0]
    policy = (await cli.data('request', 'GET', base + '/keys/' + key['id'] + '/use-policies'))['items'][0]
    await cli.data('request', 'DELETE', base + '/use-policies/' + policy['id'],
        '--query', 'expected_revision=' + str(policy['revision']))
    denied = await cli.run('request', 'POST', route, body={'tool_id': tool['id']}, expected=4)
    assert 'CONFIG_USAGE_NOT_AUTHORIZED' in str(denied)


@pytest.mark.asyncio
async def test_pre_v1_mcp_author_can_refresh_without_granting_new_validation_authority(cli):
    from uuid import UUID
    from modules.core.infra.database.configuration_models import ConfigurationLegacyAuthorityModel
    from shared.infra.config import Settings
    from shared.infra.database.session import create_engine, create_session_factory
    project = await cli.data('project', 'create', body={
        'workspace_id': cli.workspace_id, 'name': 'Pre-v1 MCP authority', 'slug': str(uuid4()),
    })
    cli.project_id = project['id']
    for value in ('Bearer ephemeral-native-environment-token', 'ephemeral-native-tool-token'):
        cli.secret_values.add(value)
    tool = await cli.data('request', 'POST', '/tools/tools', body={
        'project_id': cli.project_id, 'name': 'Old MCP author Tool', 'type': 'mcp', 'config': {
            'mode': 'server', 'exposure': 'all_discovered', 'server': {
                'url': os.environ['WOOBE_TEST_FAKE_MCP_URL'], 'transport': 'streamable_http',
                'headers': [{'key': 'Authorization', 'value': 'Bearer ephemeral-native-environment-token'},
                            {'key': 'X-Tool-Token', 'value': 'ephemeral-native-tool-token', 'sensitive': True}],
            }}, 'input_schema': {'type': 'object', 'properties': {}},
    })
    issued, restricted = await cli.issue('workspace', 'control-key', 'create', body={
        'name': 'Old MCP author', 'expires_at': (datetime.now(UTC) + timedelta(minutes=30)).isoformat(),
        'on_project_create_permissions': [], 'project_grants': [{'project_id': cli.project_id,
            'permissions': ['project:read', 'tool:read', 'tool:write', 'project:environment:read']}],
    })
    # A new Tool-write grant alone does not inherit validation permission.
    await cli.run('request', 'POST', '/tools/mcp/refresh', body={'tool_id': tool['id']}, key=restricted, expected=4)
    engine = create_engine(Settings())
    try:
        async with create_session_factory(engine)() as session, session.begin():
            session.add(ConfigurationLegacyAuthorityModel(project_id=UUID(cli.project_id), subject_type='control_key',
                subject_id=UUID(issued['id']), permission='tool:write', catalog_revision='pre-project_configuration.v1'))
        refreshed = await cli.data('request', 'POST', '/tools/mcp/refresh', body={'tool_id': tool['id']}, key=restricted)
        assert refreshed['initialized'] and refreshed['status'] == 'ready'
        # The provenance applies only to the old Draft operation, not to the
        # new configuration test route or a different Environment.
        await cli.run('request', 'POST', f'/core/projects/{cli.project_id}/configuration/tests/tool/{tool["id"]}',
            body={'environment': 'draft'}, key=restricted, expected=4)
        base = f'/core/projects/{cli.project_id}/configuration'
        key = (await cli.data('request', 'GET', base + '/keys'))['items'][0]
        policy = (await cli.data('request', 'GET', base + '/keys/' + key['id'] + '/use-policies'))['items'][0]
        await cli.data('request', 'DELETE', base + '/use-policies/' + policy['id'],
            '--query', 'expected_revision=' + str(policy['revision']))
        denied = await cli.run('request', 'POST', '/tools/mcp/refresh', body={'tool_id': tool['id']}, key=restricted, expected=4)
        assert 'CONFIG_USAGE_NOT_AUTHORIZED' in str(denied)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize('source', ['inline', 'secret'])
async def test_route_authentication_native_peer_and_anonymous_sibling(cli, unused_tcp_port, source):
    import asyncio
    import httpx
    import uvicorn
    from tests.fakes.mcp_provider import app
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=unused_tcp_port, log_level='warning'))
    serving = asyncio.create_task(server.serve())
    origin = f'http://127.0.0.1:{unused_tcp_port}'
    try:
        async with httpx.AsyncClient(trust_env=False) as peer:
            for _ in range(60):
                try:
                    if (await peer.get(origin + '/health')).status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                await asyncio.sleep(.05)
            else:
                pytest.fail('Ephemeral native route peer did not start')
        project = await cli.data('project', 'create', body={
            'workspace_id': cli.workspace_id, 'name': 'Route-scoped authentication', 'slug': str(uuid4()),
        })
        cli.project_id = project['id']
        values = {'auth': 'Bearer ephemeral-native-environment-token', 'token': 'ephemeral-native-tool-token'}
        cli.secret_values.update(values.values())
        if source == 'secret':
            for name, value in values.items():
                await cli.data('request', 'POST', '/tools/secrets', body={
                    'project_id': cli.project_id, 'name': name, 'type': 'api_key', 'value': value,
                })
        headers = [{'key': 'Authorization', 'value': values['auth'] if source == 'inline' else '{{secret:auth}}'},
            {'key': 'X-Tool-Token', 'value': values['token'] if source == 'inline' else '{{secret:token}}', 'sensitive': True}]
        tool = await cli.data('request', 'POST', '/tools/tools', body={
            'project_id': cli.project_id, 'name': 'Scoped HTTP group', 'type': 'http', 'config': {
                'mode': 'group', 'base_url': origin, 'routes': [
                    {'id': 'protected/route', 'name': 'Protected', 'description': 'Protected read', 'path': '/http-protected',
                     'method': 'GET', 'headers': headers, 'default_permission': 'allow'},
                    {'id': 'anonymous', 'name': 'Anonymous', 'description': 'Anonymous read', 'path': '/http-anonymous',
                     'method': 'GET', 'headers': [], 'default_permission': 'allow'}]},
        })
        first = await cli.data('request', 'POST', '/tools/tools/execute', body={
            'tool_id': tool['id'], 'input_data': {'__mcp_tool_name': 'protected/route'}})
        assert first['success'] and first['output']['body']['authenticated']
        second = await cli.data('request', 'POST', '/tools/tools/execute', body={
            'tool_id': tool['id'], 'input_data': {'__mcp_tool_name': 'anonymous'}})
        assert second['success'] and second['output']['body']['anonymous']
        base = f'/core/projects/{cli.project_id}/configuration'
        readiness = await cli.data('request', 'GET', base + '/readiness/tool/' + tool['id'])
        assert len(readiness['dependencies']) == 2
        assert all('/routes/protected~1route/' in item['field_path'] for item in readiness['dependencies'])
        key = (await cli.data('request', 'GET', base + '/keys'))['items'][0]
        policy = (await cli.data('request', 'GET', base + '/keys/' + key['id'] + '/use-policies'))['items'][0]
        assert policy['destination'].endswith('/http-protected')
        await cli.data('request', 'DELETE', base + '/use-policies/' + policy['id'],
            '--query', 'expected_revision=' + str(policy['revision']))
        denied = await cli.run('request', 'POST', '/tools/tools/execute', body={
            'tool_id': tool['id'], 'input_data': {'__mcp_tool_name': 'protected/route'}}, expected=4)
        assert 'CONFIG_USAGE_NOT_AUTHORIZED' in str(denied)
        # Revoking protected-route use does not attach its material to a sibling.
        second = await cli.data('request', 'POST', '/tools/tools/execute', body={
            'tool_id': tool['id'], 'input_data': {'__mcp_tool_name': 'anonymous'}})
        assert second['success']
    finally:
        server.should_exit = True
        await asyncio.wait_for(serving, 10)


@pytest.mark.asyncio
async def test_tool_author_can_roundtrip_metadata_but_not_rebind_clear_or_write_new_material(cli):
    from copy import deepcopy
    from uuid import UUID
    from modules.core.infra.database.configuration_models import ConfigurationLegacyAuthorityModel
    from shared.infra.config import Settings
    from shared.infra.database.session import create_engine, create_session_factory
    project = await cli.data('project', 'create', body={
        'workspace_id': cli.workspace_id, 'name': 'Tool authority boundary', 'slug': str(uuid4()),
    })
    cli.project_id = project['id']
    for name in ('FIRST_KEY', 'SECOND_KEY'):
        await cli.run('project', 'configuration', 'declare', name)
    tool = await cli.data('request', 'POST', '/tools/tools', body={
        'project_id': cli.project_id, 'name': 'Public reference owner', 'type': 'http', 'config': {
            'url': 'https://approved.example/api', 'method': 'GET', 'authentication': {
                'type': 'bearer', 'fields': {'token': {'source': 'project_environment', 'key': 'FIRST_KEY'}}}},
    })
    issued, restricted = await cli.issue('workspace', 'control-key', 'create', body={
        'name': 'Tool metadata author', 'expires_at': (datetime.now(UTC) + timedelta(minutes=30)).isoformat(),
        'on_project_create_permissions': [], 'project_grants': [{'project_id': cli.project_id,
            'permissions': ['project:read', 'tool:read', 'tool:write', 'project:environment:read']}],
    })
    assert tool['config']['authentication']['fields']['token'] == {'source': 'project_environment', 'key': 'FIRST_KEY'}, tool['config']['authentication']
    edited = await cli.data('request', 'PATCH', '/tools/tools/' + tool['id'], key=restricted,
        body={'name': 'Metadata edit', 'config': tool['config']})
    assert edited['config']['authentication'] == tool['config']['authentication']
    altered = deepcopy(tool['config']); altered['authentication']['fields']['token']['key'] = 'SECOND_KEY'
    await cli.run('request', 'PATCH', '/tools/tools/' + tool['id'], key=restricted, body={'config': altered}, expected=4)
    await cli.run('request', 'PATCH', '/tools/tools/' + tool['id'], key=restricted,
        body={'config': {'url': 'https://approved.example/api', 'method': 'GET'}}, expected=4)
    value = 'fresh-inline-authority-canary'; cli.secret_values.add(value)
    create = {'project_id': cli.project_id, 'name': 'Inline compatibility', 'type': 'http', 'config': {
        'url': 'https://approved.example/api', 'headers': [{'key': 'Authorization', 'value': value}]}}
    await cli.run('request', 'POST', '/tools/tools', key=restricted, body=create, expected=4)
    engine = create_engine(Settings())
    try:
        async with create_session_factory(engine)() as session, session.begin():
            session.add(ConfigurationLegacyAuthorityModel(project_id=UUID(cli.project_id), subject_type='control_key',
                subject_id=UUID(issued['id']), permission='tool:write', catalog_revision='pre-project_configuration.v1'))
        compatibility = await cli.data('request', 'POST', '/tools/tools', key=restricted, body=create)
        assert value not in str(compatibility)
        roundtrip = await cli.data('request', 'PATCH', '/tools/tools/' + compatibility['id'], key=restricted,
            body={'name': 'Private owner metadata', 'config': compatibility['config']})
        assert roundtrip['config']['authentication'] == compatibility['config']['authentication']
        await cli.run('request', 'POST', '/tools/tools', body={**create, 'config': compatibility['config']}, expected=4)
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_cli_binds_exact_route_without_material_and_fences_other_route_edits(cli):
    project = await cli.data('project', 'create', body={
        'workspace_id': cli.workspace_id, 'name': 'Route reference editing', 'slug': str(uuid4()),
    })
    cli.project_id = project['id']
    await cli.run('project', 'configuration', 'declare', 'ORDERS_TOKEN')
    tool = await cli.data('request', 'POST', '/tools/tools', body={
        'project_id': cli.project_id, 'name': 'Two routes', 'type': 'http', 'config': {
            'mode': 'group', 'base_url': 'https://approved.example', 'routes': [
                {'id': 'orders/active', 'name': 'Orders', 'description': 'Read orders', 'path': '/orders'},
                {'id': 'public', 'name': 'Public', 'description': 'Public read', 'path': '/public'},
            ]},
    })
    result = await cli.run('project', 'configuration', 'bind', 'tool', tool['id'],
        '--route', 'orders/active', '--type', 'bearer', '--field', 'token=ORDERS_TOKEN')
    binding = result['data']
    assert binding['route_id'] == 'orders/active'
    assert binding['authentication'] == {'type': 'bearer', 'fields': {
        'token': {'source': 'project_environment', 'key': 'ORDERS_TOKEN'}}}
    readiness = (await cli.run('project', 'configuration', 'check', 'tool', tool['id'], expected=6))['data']
    assert len(readiness['dependencies']) == 1
    assert readiness['dependencies'][0]['field_path'] == '/config/routes/orders~1active/authentication/fields/token'
    await cli.run('project', 'configuration', 'bind', 'tool', tool['id'], '--route', 'public', '--type', 'none')
    stale = await cli.run('request', 'PUT',
        f'/core/projects/{cli.project_id}/configuration/bindings/tool/{tool["id"]}',
        body={'expected_revision': binding['revision'], 'route_id': 'orders/active',
              'authentication': {'type': 'none'}}, expected=6)
    assert stale['error']['domain_code'] == 'CONFIG_REVISION_CONFLICT'
    current = await cli.data('request', 'GET',
        f'/core/projects/{cli.project_id}/configuration/bindings/tool/{tool["id"]}')
    assert current['routes'][0]['authentication'] == binding['authentication']
    assert current['routes'][1]['authentication']['type'] == 'none'


@pytest.mark.asyncio
@pytest.mark.parametrize('flow', ['pkce', 'device'])
async def test_detached_existing_oauth_protocol_and_discovery(cli, unused_tcp_port, flow):
    import asyncio
    import httpx
    import uvicorn
    from tests.fakes.mcp_oauth_provider import app, ACCESS, REFRESH, CLIENT_SECRET, DEVICE
    origin = f'http://127.0.0.1:{unused_tcp_port}'
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=unused_tcp_port, log_level='error'))
    peer = asyncio.create_task(server.serve())
    try:
        async with httpx.AsyncClient(trust_env=False) as client:
            for _ in range(100):
                try:
                    if (await client.get(origin + '/health')).status_code == 200:
                        break
                except httpx.TransportError:
                    pass
                await asyncio.sleep(.025)
            else:
                pytest.fail('Native OAuth peer did not become ready')
        project = await cli.data('project', 'create', body={
            'workspace_id': cli.workspace_id, 'name': 'OAuth owner flow', 'slug': str(uuid4())})
        cli.project_id = project['id']
        cli.secret_values.update({ACCESS, REFRESH, CLIENT_SECRET, DEVICE, 'native-code'})
        tool = await cli.data('request', 'POST', '/tools/tools', body={
            'project_id': cli.project_id, 'name': 'Native OAuth', 'type': 'mcp',
            'config': {'mode': 'server', 'exposure': 'all_discovered', 'server': {'url': origin + '/mcp'}}})
        async with httpx.AsyncClient(base_url=cli.origin, trust_env=False,
            headers={'Authorization': 'Bearer ' + cli.credential}) as http:
            invalid = await http.post('/tools/mcp/oauth/start', json={
                'tool_id': tool['id'], 'client_secret': CLIENT_SECRET})
        assert invalid.status_code == 400 and CLIENT_SECRET not in invalid.text
        async def assert_private_protocol_fields_absent_from_raw_api():
            async with httpx.AsyncClient(base_url=cli.origin, trust_env=False,
                headers={'Authorization': 'Bearer ' + cli.credential}) as http:
                response = await http.get('/tools/tools', params={'project_id': cli.project_id})
            assert response.status_code == 200
            row = next(item for item in response.json()['data'] if item['id'] == tool['id'])
            oauth = row['config'].get('oauth') or {}
            exposed = {name for name in oauth if name.endswith('_encrypted') or name in {'code_verifier', 'device_code', 'client_secret', 'access_token', 'refresh_token', 'state'}}
            assert not exposed, 'Private OAuth source fields returned by raw API: ' + ','.join(sorted(exposed))
            return row['config']
        if flow == 'pkce':
            started = await cli.data('request', 'POST', '/tools/mcp/oauth/start', body={
                'tool_id': tool['id'], 'redirect_uri': origin + '/callback',
                'authorization_endpoint': origin + '/authorize', 'token_endpoint': origin + '/token',
                'registration_endpoint': origin + '/register', 'authorization_server_issuer': origin})
            assert started['status'] == 'pending' and started['state']
            public_config = await assert_private_protocol_fields_absent_from_raw_api()
            await cli.data('request', 'PATCH', '/tools/tools/' + tool['id'], body={
                'name': 'Renamed while OAuth pending', 'config': public_config})
            completed = await cli.data('request', 'POST', '/tools/mcp/oauth/complete', body={
                'tool_id': tool['id'], 'code': 'native-code', 'state': started['state']})
        else:
            started = await cli.data('request', 'POST', '/tools/mcp/oauth/device/start', body={
                'tool_id': tool['id'], 'authorization_server_issuer': origin})
            assert started['status'] == 'device_pending' and started['user_code'] == 'NATIVE-CODE'
            public_config = await assert_private_protocol_fields_absent_from_raw_api()
            await cli.data('request', 'PATCH', '/tools/tools/' + tool['id'], body={
                'name': 'Renamed while device pending', 'config': public_config})
            pending = await cli.data('request', 'POST', '/tools/mcp/oauth/device/poll', body={'tool_id': tool['id']})
            assert pending['status'] == 'authorization_pending' and not pending['connected']
            completed = await cli.data('request', 'POST', '/tools/mcp/oauth/device/poll', body={'tool_id': tool['id']})
        assert completed['connected'] and completed['status'] == 'connected'
        public_config = await assert_private_protocol_fields_absent_from_raw_api()
        await cli.data('request', 'PATCH', '/tools/tools/' + tool['id'], body={
            'name': 'Renamed connected OAuth', 'config': public_config})
        retargeted = json.loads(json.dumps(public_config))
        retargeted['server']['url'] = origin + '/other-mcp'
        denied = await cli.run('request', 'PATCH', '/tools/tools/' + tool['id'], body={'config': retargeted}, expected=6)
        assert denied['error']['domain_code'] == 'CONFIG_DESTINATION_CHANGED'
        listed = await cli.data('request', 'GET', '/tools/tools', '--query', 'project_id=' + cli.project_id)
        owner = next(row for row in listed if row['id'] == tool['id'])
        assert owner['config']['mcp_status'] == 'ready'
        assert owner['config']['oauth']['resource_metadata_url'] == origin + '/resource-metadata'
        assert owner['config']['discovered_tools'][0]['name'] == 'read_status'
        api_log = (cli.directory / 'api.log').read_text()
        if flow == 'pkce':
            assert started['state'] not in api_log
        assert all(value not in api_log for value in (ACCESS, REFRESH, CLIENT_SECRET, DEVICE, 'native-code'))
    finally:
        server.should_exit = True
        await asyncio.wait_for(peer, 10)


@pytest.mark.asyncio
@pytest.mark.parametrize('flow', ['pkce', 'device'])
async def test_environment_limited_operator_cannot_issue_global_oauth_material(cli, unused_tcp_port, flow):
    import asyncio
    import httpx
    import uvicorn
    from tests.fakes import mcp_oauth_provider as fake
    fake.registrations = 0
    origin = f'http://127.0.0.1:{unused_tcp_port}'
    server = uvicorn.Server(uvicorn.Config(fake.app, host='127.0.0.1', port=unused_tcp_port, log_level='error'))
    peer = asyncio.create_task(server.serve())
    try:
        async with httpx.AsyncClient(trust_env=False) as http:
            for _ in range(100):
                try:
                    if (await http.get(origin + '/health')).status_code == 200:
                        break
                except httpx.TransportError:
                    pass
                await asyncio.sleep(.025)
            else:
                pytest.fail('Native OAuth peer did not become ready')
        project = await cli.data('project', 'create', body={
            'workspace_id': cli.workspace_id, 'name': 'Scoped OAuth material', 'slug': str(uuid4())})
        cli.project_id = project['id']
        tool = await cli.data('request', 'POST', '/tools/tools', body={
            'project_id': cli.project_id, 'name': 'Unconnected OAuth', 'type': 'mcp',
            'config': {'mode': 'server', 'server': {'url': origin + '/mcp'}}})
        _, restricted = await cli.issue('workspace', 'control-key', 'create', body={
            'name': 'Draft OAuth operator', 'expires_at': (datetime.now(UTC) + timedelta(minutes=30)).isoformat(),
            'on_project_create_permissions': [], 'project_grants': [{'project_id': cli.project_id,
                'permissions': ['project:read', 'tool:write', 'project:environment:value:write'],
                'conditions': {'environments': ['draft']}}]})
        path = '/tools/mcp/oauth/start' if flow == 'pkce' else '/tools/mcp/oauth/device/start'
        body = {'tool_id': tool['id'], 'authorization_server_issuer': origin}
        if flow == 'pkce': body['redirect_uri'] = origin + '/callback'
        await cli.run('request', 'POST', path, body=body, key=restricted, expected=4)
        assert fake.registrations == 0
        listed = await cli.data('request', 'GET', '/tools/tools', '--query', 'project_id=' + cli.project_id)
        assert not next(item for item in listed if item['id'] == tool['id'])['config'].get('oauth')
    finally:
        server.should_exit = True
        await asyncio.wait_for(peer, 10)


@pytest.mark.asyncio
@pytest.mark.parametrize('kind', ['provider', 'tool'])
async def test_environment_limited_value_writer_cannot_change_global_legacy_material(cli, kind):
    project = await cli.data('project', 'create', body={
        'workspace_id': cli.workspace_id, 'name': 'Global source scope', 'slug': str(uuid4())})
    cli.project_id = project['id']
    permissions = ['project:read', 'project:environment:value:write',
        'provider:write' if kind == 'provider' else 'tool:write']
    _, restricted = await cli.issue('workspace', 'control-key', 'create', body={
        'name': 'Staging values only', 'expires_at': (datetime.now(UTC) + timedelta(minutes=30)).isoformat(),
        'on_project_create_permissions': [], 'project_grants': [{'project_id': cli.project_id,
            'permissions': permissions, 'conditions': {'environments': ['staging']}}]})
    material = 'global-scope-native-canary'; cli.secret_values.add(material)
    if kind == 'provider':
        await cli.run('project', 'provider-credential', 'create', key=restricted,
            body={'project_id': cli.project_id, 'provider': 'openai', 'name': 'Global Provider',
                  'secret': material, 'environment': 'staging'}, expected=4)
    else:
        await cli.run('request', 'POST', '/tools/tools', key=restricted, body={
            'project_id': cli.project_id, 'name': 'Global Tool', 'type': 'http', 'environment': 'staging', 'config': {
                'url': 'https://approved.example/api', 'headers': [{'key': 'Authorization', 'value': material}]}}, expected=4)
