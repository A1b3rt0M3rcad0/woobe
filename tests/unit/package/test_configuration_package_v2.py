from copy import deepcopy
import io
import json
from uuid import uuid4

import pytest

from modules.package.application.validation import validate_document, schemas
from modules.package.application.planning import PlanPackageUseCase
from modules.package.domain.bundle import inventory_digest
from modules.package.domain.errors import PackageError
from modules.package.infra.bundles import snapshot_directory, receive_archive


def package(tmp_path):
    connection = {"provider": "openai", "name": "Primary", "authentication": {
        "type": "api_key", "fields": {"api_key": {"source": "project_environment", "key": "PRIMARY_KEY"}}}}
    files = {
        "woobe.yaml": {"kind": "Package", "metadata": {"name": "Support", "version": "1.0.0"}, "spec": {
            "entrypoint": {"kind": "Agent", "ref": "agent"}, "resources": ["agent.yaml", "model.yaml"],
            "configuration": {"keys": [{"key": "PRIMARY_KEY", "kind": "secret", "value_format": "token"}]},
            "connections": {"primary": connection}}},
        "agent.yaml": {"kind": "Agent", "metadata": {"key": "agent", "name": "Support"},
            "spec": {"legacy_system_prompt": "Help", "model": {"primary": {"ref": "model"}}}},
        "model.yaml": {"kind": "Model", "metadata": {"key": "model", "name": "Model"},
            "spec": {"provider": "openai", "model": "gpt-4o-mini", "credential": {"ref": "primary"}}},
    }
    for name, document in files.items():
        document.update(format="woobe-package", schema_version="2.0")
        (tmp_path / name).write_text(json.dumps(document))
    return files


def bindings():
    return {"format": "woobe-package", "schema_version": "2.0", "kind": "ImportBindings", "metadata": {"name": "Install"},
        "spec": {"credentials": {"primary": {"create": True}}, "project_environment": {"PRIMARY_KEY": {"create": True}}}}


def test_catalogs_are_distinct_and_binding_values_are_forbidden(tmp_path):
    files = package(tmp_path)
    validate_document(files["woobe.yaml"])
    assert schemas()["Package"]["properties"]["schema_version"]["const"] == "1.0"
    assert schemas("2.0")["Package"]["properties"]["schema_version"]["const"] == "2.0"
    for change in ({"protected_ref": "private"}, {"create": True, "existing_key": "PRIMARY_KEY"}, {}, {"value": "canary"}):
        document = bindings()
        document["spec"]["project_environment"]["PRIMARY_KEY"] = change
        with pytest.raises(PackageError):
            validate_document(document)
    for change in ({"value": "canary"}, {"source": "legacy_configuration", "key": "PRIMARY_KEY", "alias_id": str(uuid4())}):
        document = deepcopy(files["woobe.yaml"])
        document["spec"]["connections"]["primary"]["authentication"]["fields"]["api_key"] = change
        with pytest.raises(PackageError) as error:
            validate_document(document)
        assert "canary" not in str(error.value)


def test_v2_archive_lock_and_required_remote_keys(tmp_path):
    files = package(tmp_path)
    with snapshot_directory(tmp_path) as bundle:
        assert bundle.artifact_digest != inventory_digest(bundle.inventory)
        assert bundle.lock()["schema_version"] == "2.0"
        archive = io.BytesIO()
        bundle.archive(archive, include_lock=True)
        with receive_archive(io.BytesIO(archive.getvalue()), locked=True) as received:
            assert received.artifact_digest == bundle.artifact_digest
    files["woobe.yaml"]["spec"]["configuration"]["keys"] = []
    (tmp_path / "woobe.yaml").write_text(json.dumps(files["woobe.yaml"]))
    with pytest.raises(PackageError) as error:
        snapshot_directory(tmp_path)
    assert error.value.code == "PACKAGE_REQUIREMENT_INVALID"


@pytest.mark.asyncio
async def test_structural_plan_declares_before_consumers_and_never_activates(tmp_path):
    package(tmp_path)
    class Inspector:
        async def capabilities(self): return {}
        async def inspect_bindings(self, **kwargs): return kwargs["bindings"]
        async def inspect_component(self, **kwargs): return {}
        async def authorize(self, **kwargs): pass
    with snapshot_directory(tmp_path) as bundle:
        arguments = dict(project_id=uuid4(), principal=object(), graph=bundle.graph, support={},
            artifact_digest=bundle.artifact_digest, upload_id=uuid4(), bindings=bindings(), api_origin="https://example.test")
        with pytest.raises(PackageError) as error:
            await PlanPackageUseCase(Inspector()).execute(**arguments)
        assert error.value.code == "PACKAGE_INSTALLATION_MODE_REQUIRED"
        approved = await PlanPackageUseCase(Inspector()).execute(**arguments, installation_mode="structural")
        actions = [item["action"] for item in approved.document["effects"]]
        assert actions[:2] == ["declare_configuration", "create_reference_credential"]
        assert not set(actions) & {"create_environment_value", "create_credential", "activate_production", "verify_mcp_discovery"}
        assert approved.document["installation_mode"] == "structural"
        with pytest.raises(PackageError):
            await PlanPackageUseCase(Inspector()).execute(**arguments, installation_mode="structural", lifecycle="production")


@pytest.mark.parametrize('route_authentication', [False, True])
def test_export_v2_declares_only_public_intent_and_preserves_v1(tmp_path, route_authentication):
    from modules.package.application.export_projection import ExportProjection
    from modules.package.domain.parsing import decode_document
    credential = str(uuid4())
    alias_id = str(uuid4())
    authentication = {"type": "api_key", "fields": {"api_key": {
        "source": "legacy_configuration", "key": "PRIMARY_KEY", "alias_id": alias_id}}}
    captured = {"source": {"agent_id": str(uuid4()), "kind": "draft"},
        "definition": {"name": "Support", "provider": "openai", "model": "gpt-4o-mini",
            "provider_credential_id": credential, "model_spec_snapshot": {"model_id": "gpt-4o-mini"},
            "runtime_config": {}, "system_prompt": "Help", "session_mode": "stateless"},
        "credentials": {credential: {"provider": "openai", "name": "Main", "metadata": {}, "authentication": authentication}},
        "tools": [], "skills": [], "artifacts": {}, "knowledge": None}
    route = {'id': 'orders', 'name': 'Orders', 'description': 'Read orders', 'path': '/orders'}
    if route_authentication:
        route['authentication'] = {'type': 'bearer', 'fields': {'token': {
            'source': 'project_environment', 'key': 'PRIMARY_KEY'}}}
    captured['tools'] = [{'id': str(uuid4()), 'name': 'Routes', 'type': 'http', 'description': '',
        'timeout_ms': 10000, 'input_schema': {}, 'output_schema': {}, 'permission': 'allow', 'risk': 'safe',
        'permissions': [], 'config': {'mode': 'group', 'base_url': 'https://approved.example',
            'auth': {'type': 'none', 'credentials': []}, 'routes': [route]}}]
    original_tools = deepcopy(captured['tools'])
    declaration = {"key": "PRIMARY_KEY", "kind": "secret", "value_format": "token"}
    projection = ExportProjection(knowledge_mode="binding", environment_kinds={'PRIMARY_KEY': 'secret'}, schema_version="2.0", declarations={"PRIMARY_KEY": declaration})
    projection.finish(kind="Agent", captured=captured, name="Support", version="1.0.0")
    for path, content in projection.files.items():
        (tmp_path / path).write_bytes(content)
    with snapshot_directory(tmp_path) as bundle:
        assert bundle.graph.manifest["spec"]["configuration"]["keys"] == [declaration]
        assert alias_id not in repr(bundle.graph.manifest)
        assert "legacy_configuration" not in repr(bundle.graph.manifest)
    assert captured["credentials"][credential]["authentication"] == authentication
    assert captured['tools'] == original_tools
    if route_authentication:
        with pytest.raises(PackageError) as error:
            ExportProjection(knowledge_mode='binding', environment_kinds={}).finish(
                kind='Agent', captured=captured, name='Support', version='1.0.0')
        assert error.value.code == 'PACKAGE_SCHEMA_UNSUPPORTED'
        return
    legacy = ExportProjection(knowledge_mode="binding", environment_kinds={}).finish(kind="Agent", captured=captured, name="Support", version="1.0.0")
    manifest = decode_document(legacy.files["woobe.yaml"], "woobe.yaml")
    validate_document(manifest)
    assert manifest["spec"]["requires"]["credentials"] == [{"ref": "credential-1", "provider": "openai", "metadata": {}}]


def network_package(files, source):
    files["network.yaml"] = {"format": "woobe-package", "schema_version": "2.0", "kind": "Network",
        "metadata": {"key": "network", "name": "Support Network"}, "spec": {"root": "support", "nodes": [
            {"key": "support", "agent_ref": "agent", "binding": {"source": source}}], "edges": []}}
    files["woobe.yaml"]["spec"]["entrypoint"] = {"kind": "Network", "ref": "network"}
    files["woobe.yaml"]["spec"]["resources"].append("network.yaml")
    return files


@pytest.mark.asyncio
@pytest.mark.parametrize("source", ["staging", "release"])
async def test_structural_network_uses_imported_drafts_without_promoting_constituents(tmp_path, source):
    files = network_package(package(tmp_path), source)
    for name, document in files.items():
        (tmp_path / name).write_text(json.dumps(document))
    class Inspector:
        async def capabilities(self): return {}
        async def inspect_bindings(self, **kwargs): return kwargs["bindings"]
        async def inspect_component(self, **kwargs): return {}
        async def authorize(self, **kwargs): pass
    with snapshot_directory(tmp_path) as bundle:
        approved = await PlanPackageUseCase(Inspector()).execute(project_id=uuid4(), principal=object(),
            graph=bundle.graph, support={}, artifact_digest=bundle.artifact_digest, upload_id=uuid4(),
            bindings=bindings(), api_origin="https://example.test", installation_mode="structural")
        assert approved.document["constituent_binding_policy"] == "imported_draft"
        assert not {"create_staging", "create_immutable_release", "activate_production"} & {
            effect["action"] for effect in approved.document["effects"]}
        assert approved.document["source_definition"]["components"]["network"]["spec"]["nodes"][0]["binding"]["source"] == source


def test_reference_collection_accepts_schema_properties_named_source_and_authentication():
    from modules.package.application.export_projection import reference_requirements
    payload = {"properties": {"source": {"type": "object"}, "auth": {"credentials": [{"type": "string"}]},
        "env_secret_refs": {"properties": {"token": {"type": "string"}}}},
        "authentication": {"type": "api_key", "fields": {"api_key": {"source": "project_environment", "key": "API_KEY"}}},
        "legacy": {"auth": {"credentials": ["legacy-token"]}, "env_secret_refs": {"TOKEN": "env-token"}}}
    assert reference_requirements(payload) == ({"API_KEY"}, {"legacy-token", "env-token"})
