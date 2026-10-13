"""Native owners install remote-reference definitions without credential values."""
import asyncio
import io
import json
from uuid import uuid4

import httpx
import pytest

from tests.integration.cli.test_control_plane_workflow import cli as _live_cli
from tests.unit.package.test_configuration_package_v2 import package, bindings
from modules.package.infra.bundles import snapshot_directory

cli = _live_cli


@pytest.mark.asyncio
@pytest.mark.parametrize("with_mcp,with_knowledge", [(False, False), (True, False), (True, True)])
async def test_structural_package_installs_before_remote_values_exist(cli, tmp_path, with_mcp, with_knowledge):
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
        files["embedding.yaml"] = {"format": "woobe-package", "schema_version": "2.0", "kind": "Model",
            "metadata": {"key": "embedding", "name": "Embedding"}, "spec": {"provider": "openai",
                "model": "text-embedding-3-small", "model_type": "embedding", "credential": {"ref": "primary"}}}
        files["knowledge.yaml"] = {"format": "woobe-package", "schema_version": "2.0", "kind": "Knowledge",
            "metadata": {"key": "knowledge", "name": "Support Knowledge"}, "spec": {"mode": "portable",
                "collection": {"name": "Support Knowledge"}, "documents": [{"path": "support.txt", "title": "Policy", "content_type": "text/plain"}],
                "embedding": {"model_ref": "embedding"}, "vector_snapshot": {}}}
        files["woobe.yaml"]["spec"]["resources"] += ["embedding.yaml", "knowledge.yaml"]
        files["agent.yaml"]["spec"]["knowledge"] = {"source": {"ref": "knowledge"}}
        (source / "support.txt").write_text("Investigate reported issues and escalate with evidence.")
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
        assert not {"build_vector_snapshot", "verify_vector_snapshot", "verify_mcp_discovery"} & {item["action"] for item in approved["effects"]}
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

        target = next(item["resource_id"] for item in operation["inventory"] if item["action"] == "prepare_inactive_agent")
        response = await client.post(base + "/export", json={"kind": "Agent", "target_id": target, "source": "draft", "package_schema_version": "2.0", "knowledge": "portable"})
        assert response.is_success, response.text
        exported = response.json()["data"]
        assert exported["package_schema_version"] == "2.0"
        assert exported["closure_complete"] is True
        assert exported["self_contained"] is True
