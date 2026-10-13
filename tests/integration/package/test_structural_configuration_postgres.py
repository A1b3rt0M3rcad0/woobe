"""Native owners install remote-reference definitions without credential values."""
import asyncio
import io
import json
import os
from uuid import uuid4

import httpx
import pytest

from tests.integration.cli.test_control_plane_workflow import cli as _live_cli
from tests.unit.package.test_configuration_package_v2 import package, bindings, network_package
from modules.package.infra.bundles import snapshot_directory

cli = _live_cli


@pytest.mark.asyncio
@pytest.mark.parametrize("with_mcp,with_knowledge,network_source", [(False, False, None), (True, False, None), (True, True, None), (True, True, "release"), (False, False, "staging")])
async def test_structural_package_installs_before_remote_values_exist(cli, tmp_path, with_mcp, with_knowledge, network_source):
    project = await cli.data("project", "create", body={"workspace_id": cli.workspace_id,
        "name": "Structural configuration", "slug": str(uuid4())})
    cli.project_id = project["id"]
    source = tmp_path / "structure"
    source.mkdir()
    files = package(source)
    if with_mcp:
        # The port is intentionally unavailable: installation must not discover.
        files["mcp.yaml"] = {"format": "woobe-package", "schema_version": "2.0", "kind": "Tool",
            "metadata": {"key": "lookup", "name": "Unprepared MCP"}, "spec": {"type": "mcp", "config": {
                "mode": "server", "exposure": "all_discovered", "server": {"url": "http://127.0.0.1:9/mcp"},
                "authentication": {"type": "none"}}}}
        files["agent.yaml"]["spec"]["tools"] = [{"ref": "lookup"}]
        files["woobe.yaml"]["spec"]["resources"].append("mcp.yaml")
        for name, document in files.items():
            (source / name).write_text(json.dumps(document))
    if with_knowledge:
        provider_url = os.environ["WOOBE_TEST_FAKE_PROVIDER_URL"]
        files["woobe.yaml"]["spec"]["connections"]["primary"].update(provider="custom", metadata={"provider_family": "openai", "compatibility": "compatible", "base_url": provider_url})
        files["model.yaml"]["spec"].update(provider="custom", model="fake", base_url=provider_url)
        files["embedding.yaml"] = {"format": "woobe-package", "schema_version": "2.0", "kind": "Model",
            "metadata": {"key": "embedding", "name": "Embedding"}, "spec": {"provider": "custom", "base_url": provider_url,
                "model": "fake-embedding", "model_type": "embedding", "credential": {"ref": "primary"}}}
        files["knowledge.yaml"] = {"format": "woobe-package", "schema_version": "2.0", "kind": "Knowledge",
            "metadata": {"key": "knowledge", "name": "Support Knowledge"}, "spec": {"mode": "portable",
                "collection": {"name": "Support Knowledge"}, "documents": [{"path": "support.txt", "title": "Policy", "content_type": "text/plain"}],
                "embedding": {"model_ref": "embedding"}, "vector_snapshot": {}}}
        files["woobe.yaml"]["spec"]["resources"] += ["embedding.yaml", "knowledge.yaml"]
        files["agent.yaml"]["spec"]["knowledge"] = {"source": {"ref": "knowledge"}}
        (source / "support.txt").write_text("Investigate reported issues and escalate with evidence.")
        for name, document in files.items():
            (source / name).write_text(json.dumps(document))
    if network_source:
        network_package(files, network_source)
        for name, document in files.items():
            (source / name).write_text(json.dumps(document))
    with snapshot_directory(source) as captured:
        archive = io.BytesIO()
        captured.archive(archive, include_lock=True)
        digest = captured.artifact_digest
    async with httpx.AsyncClient(base_url=cli.origin, headers={"Authorization": "Bearer " + cli.credential}, trust_env=False, timeout=30) as client:
        base = f"/projects/{cli.project_id}/packages"
        response = await client.post(base + "/uploads", files={"file": ("package.tar.gz", archive.getvalue(), "application/gzip")})
        assert response.is_success, response.text
        upload = response.json()["data"]
        assert upload["package_schema_version"] == "2.0"
        request = {"upload_id": upload["upload_id"], "artifact_digest": digest, "bindings": bindings(),
            "installation_mode": "structural", "lifecycle": "draft"}
        response = await client.post(base + "/plan", json=request)
        assert response.is_success, response.text
        approved = response.json()["data"]
        assert approved["installation_mode"] == "structural"
        assert not {"build_vector_snapshot", "verify_vector_snapshot", "verify_mcp_discovery", "create_staging", "create_immutable_release", "activate_production"} & {item["action"] for item in approved["effects"]}
        apply = {**request, "plan_id": approved["plan_id"], "plan_digest": approved["plan_digest"], "protected_bindings": {}}
        response = await client.post(base + "/apply", json=apply, headers={"Idempotency-Key": "structural-" + str(uuid4())})
        assert response.is_success, response.text
        operation = response.json()["data"]
        for _ in range(120):
            if operation["terminal"]:
                break
            await asyncio.sleep(.25)
            response = await client.get(base + "/operations/" + operation["operation_id"])
            assert response.is_success, response.text
            operation = response.json()["data"]
        assert operation["state"] == "succeeded", operation
        assert operation["installation_status"] == "installed"
        assert operation["execution_ready"] is False
        assert operation["runtime_preparation_status"] == "pending"
        assert operation["deployment_status"] == "not_activated"
        keys = await client.get(f"/core/projects/{cli.project_id}/configuration/keys")
        assert keys.status_code == 200, keys.text
        key = next(item for item in keys.json()["data"]["items"] if item["key"] == "PRIMARY_KEY")
        assert key["values"]["draft"]["material"] == "missing"

        if network_source:
            assert approved["constituent_binding_policy"] == "imported_draft"
        target = next(item["resource_id"] for item in operation["inventory"] if item["action"] == ("prepare_network" if network_source else "prepare_inactive_agent"))
        response = await client.post(base + "/export", json={"kind": "Network" if network_source else "Agent", "target_id": target, "source": "draft", "package_schema_version": "2.0", "knowledge": "portable"})
        assert response.is_success, response.text
        exported = response.json()["data"]
        assert exported["package_schema_version"] == "2.0"
        assert exported["closure_complete"] is True
        assert exported["self_contained"] is True

        if with_knowledge:
            vector_id = next(item["resource_id"] for item in operation["inventory"] if item["action"] == "declare_vector_snapshot")
            route = f"/agent/knowledge/vector-snapshots/{vector_id}"
            response = await client.get(route, params={"project_id": cli.project_id})
            assert response.is_success, response.text
            snapshot = response.json()["data"]
            assert snapshot["status"] == "PENDING_PREPARATION"
            original_build_config = snapshot["build_config"]
            preparation = {"project_id": cli.project_id, "expected_build_config_hash": snapshot["build_config_hash"], "environment": "draft"}
            response = await client.post(route + "/prepare", json=preparation)
            assert not response.is_success, "Missing values/use grants must block preparation"
            response = await client.get(route, params={"project_id": cli.project_id})
            assert response.json()["data"]["status"] == "PENDING_PREPARATION"
            configuration = f"/core/projects/{cli.project_id}/configuration"
            canary = "structural-vector-private-canary"
            response = await client.put(configuration + f"/keys/{key['id']}/values/draft", json={"expected_revision": 0, "value": canary})
            assert response.is_success, response.text
            credential_id = next(item["resource_id"] for item in operation["inventory"] if item["action"] == "create_reference_credential")
            response = await client.post(configuration + "/use-policies", json={"key_id": key["id"], "consumer_kind": "provider_credential", "consumer_scope": credential_id,
                "destination": provider_url, "environments": ["draft"], "field_paths": ["/authentication/fields/api_key"], "expected_revision": 0})
            assert response.is_success, response.text
            for _ in range(2):
                response = await client.post(route + "/prepare", json=preparation)
                assert response.is_success, response.text
                assert canary not in response.text
            for _ in range(120):
                response = await client.get(route, params={"project_id": cli.project_id})
                assert response.is_success, response.text
                snapshot = response.json()["data"]
                assert snapshot["status"] != "FAILED", snapshot.get("error_message")
                if snapshot["status"] == "READY":
                    break
                await asyncio.sleep(.25)
            assert snapshot["status"] == "READY"
            assert snapshot["vector_count"] > 0 and snapshot["snapshot_hash"]
            assert snapshot["build_config"] == original_build_config
