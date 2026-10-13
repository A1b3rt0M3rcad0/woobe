"""Real new CLI + API + Worker configuration lifecycle, including rotation fences.

Set WOOBE_TEST_CONFIGURATION_CLI=true alongside the exact WOOBE_TEST_CLI_SHA.
The legacy pinned CLI exercises the unchanged compatibility suite.
"""
import pytest
from uuid import uuid4
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
