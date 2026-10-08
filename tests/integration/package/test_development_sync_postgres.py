"""Local authoring round trip over the real CLI, HTTP, durable worker and SQL."""

import json
from pathlib import Path
from uuid import uuid4

import pytest
import yaml
from tests.integration.cli.test_control_plane_workflow import cli as _live_cli

cli = _live_cli


@pytest.mark.asyncio
@pytest.mark.parametrize("kind,with_knowledge,with_mcp", [("agent", False, False), ("network", False, False), ("agent", True, False), ("agent", False, True), ("network", False, True)])
async def test_managed_agent_pull_edit_push_keeps_native_identity_and_rejects_stale_base(
    cli, tmp_path, kind, with_knowledge, with_mcp
):
    project = await cli.data(
        "project",
        "create",
        body={
            "workspace_id": cli.workspace_id,
            "name": "Development",
            "slug": str(uuid4()),
        },
    )
    cli.project_id = project["id"]
    credential = await cli.data(
        "project",
        "provider-credential",
        "create",
        body={
            "project_id": cli.project_id,
            "provider": "custom",
            "name": "Development provider",
            "secret": "ephemeral-development-provider-key",
            "metadata": {"provider_family": "openai", "compatibility": "compatible"},
        },
    )
    cli.secret_values.add("ephemeral-development-provider-key")
    source = tmp_path / "portable"
    source.mkdir()
    import os

    documents = {
        "woobe.yaml": {
            "kind": "Package",
            "metadata": {"name": "Support", "version": "1.0.0"},
            "spec": {
                "entrypoint": {"kind": "Agent", "ref": "support"},
                "resources": ["agent.yaml", "model.yaml"],
                "requires": {"credentials": [{"ref": "primary", "provider": "custom"}]},
            },
        },
        "agent.yaml": {
            "kind": "Agent",
            "metadata": {"key": "support", "name": "Support"},
            "spec": {
                "legacy_system_prompt": "Help customers",
                "model": {"primary": {"ref": "primary"}},
            },
        },
        "model.yaml": {
            "kind": "Model",
            "metadata": {"key": "primary", "name": "Primary"},
            "spec": {
                "provider": "custom",
                "model": "fake",
                "credential": {"ref": "primary"},
                "base_url": os.environ["WOOBE_TEST_FAKE_PROVIDER_URL"],
            },
        },
    }
    documents["tool.yaml"] = {
        "kind": "Tool",
        "metadata": {"key": "lookup", "name": "Lookup"},
        "spec": {
            "type": "http",
            "description": "Public lookup",
            "config": {
                "protocol": "http",
                "mode": "single",
                "method": "GET",
                "url": "https://example.invalid/lookup",
                "headers": [],
                "bindings": {},
            },
            "input_schema": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
    }
    documents["woobe.yaml"]["spec"]["resources"].append("tool.yaml")
    documents["agent.yaml"]["spec"]["tools"] = [{"ref": "lookup"}]
    if with_mcp:
        documents["tool.yaml"]["spec"] = {
            "type": "mcp",
            "config": {"mode": "server", "exposure": "all_discovered", "server": {"url": os.environ["WOOBE_TEST_FAKE_MCP_URL"]}},
            "permissions": [{"remote_name": "lookup", "permission": "review", "risk": "unknown"}],
        }
    if with_knowledge:
        documents["embedding.yaml"] = {
            "kind": "Model", "metadata": {"key": "embedding", "name": "Embedding"},
            "spec": {"provider": "custom", "model": "fake-embedding", "model_type": "embedding", "credential": {"ref": "primary"}, "base_url": os.environ["WOOBE_TEST_FAKE_PROVIDER_URL"]},
        }
        documents["knowledge.yaml"] = {
            "kind": "Knowledge", "metadata": {"key": "knowledge", "name": "Support knowledge"},
            "spec": {"mode": "portable", "collection": {"name": "Support knowledge", "description": "Grounding"}, "documents": [{"path": "documents/policy.txt", "title": "Policy", "content_type": "text/plain"}], "embedding": {"model_ref": "embedding"}, "vector_snapshot": {}},
        }
        documents["woobe.yaml"]["spec"]["resources"] += ["embedding.yaml", "knowledge.yaml"]
        documents["agent.yaml"]["spec"]["knowledge"] = {"source": {"ref": "knowledge"}}
        (source / "documents").mkdir()
        (source / "documents/policy.txt").write_text("Support escalates unresolved problems to the project owner.")
        documents["skill.yaml"] = {
            "kind": "Skill", "metadata": {"key": "procedure", "name": "Procedure"},
            "spec": {"version": "1.0.0", "package": {"manifest": "SKILL.md", "resources": []}},
        }
        documents["woobe.yaml"]["spec"]["resources"].append("skill.yaml")
        documents["agent.yaml"]["spec"]["skills"] = [{"ref": "procedure", "version": "1.0.0"}]
        documents["agent.yaml"]["spec"]["context"] = {"policy": {"allowed_sources": ["SYSTEM", "USER_INPUT", "SESSION", "TOOL", "SKILL"], "skills": {}}}
        (source / "SKILL.md").write_text("---\nname: support-procedure\ndescription: Support customers\n---\nFollow the support procedure.\n")

    if kind == "network":
        documents["network.yaml"] = {
            "kind": "Network",
            "metadata": {"key": "network", "name": "Support network"},
            "spec": {
                "root": "root",
                "nodes": [
                    {
                        "key": "root",
                        "agent_ref": "support",
                        "label": "Release view",
                        "binding": {"source": "release"},
                    },
                    {
                        "key": "draft",
                        "agent_ref": "support",
                        "label": "Draft view",
                        "binding": {"source": "draft"},
                    },
                ],
                "edges": [{"from": "root", "to": "draft"}],
            },
        }
        documents["woobe.yaml"]["spec"]["resources"].append("network.yaml")
        documents["woobe.yaml"]["spec"]["entrypoint"] = {
            "kind": "Network",
            "ref": "network",
        }
    for path, document in documents.items():
        document.update(format="woobe-package", schema_version="1.0")
        (source / path).write_text(yaml.safe_dump(document))
    operation = (
        await cli.run(
            "package",
            "import",
            str(source),
            "--bind",
            f"credential.primary={credential['id']}",
            "--wait",
        )
    )["data"]
    assert operation["state"] == "succeeded"
    agent_id = next(
        item["resource_id"]
        for item in operation["inventory"]
        if item["action"] == "prepare_inactive_agent"
    )
    local = tmp_path / "development"
    local.mkdir()
    await cli.run("init", cwd=local)
    provider_author = local / "provider-author.yaml"
    provider_author.write_text(yaml.safe_dump({
        "format": "woobe-package", "schema_version": "1.0", "kind": "Provider",
        "metadata": {"key": "destination-provider", "name": "Development provider"},
        "spec": {"provider": "custom", "compatibility": "compatible", "provider_family": "openai"},
    }))
    await cli.run("resources", "create", "provider", "destination-provider", "--file", str(provider_author), cwd=local)
    await cli.run("resources", "bind", "provider", "@destination-provider", credential["id"], cwd=local)
    target_id = (
        agent_id
        if kind == "agent"
        else next(
            item["resource_id"]
            for item in operation["inventory"]
            if item["action"] == "prepare_network"
        )
    )
    pulled = (await cli.run(kind, target_id, "pull", "--alias", "support", cwd=local))[
        "data"
    ]
    assert pulled["pulled"] is True
    provider_registry = yaml.safe_load((local / ".woobe-config").read_text())
    if with_mcp:
        tool_resource = next(item for item in provider_registry["resources"] if item["kind"] == "Tool")
        tool_descriptor = yaml.safe_load((local / ".woobe" / tool_resource["path"] / "tool.yaml").read_text())
        permission = tool_descriptor["spec"]["permissions"][0]
        assert {key: permission[key] for key in ("remote_name", "permission", "risk")} == {"remote_name": "lookup", "permission": "review", "risk": "unknown"}
    provider_alias = next(item["alias"] for item in provider_registry["resources"] if item["kind"] == "Provider")
    assert sum(item["kind"] == "Provider" for item in provider_registry["resources"]) == 1
    verified = (await cli.run("resources", "bind", "provider", f"@{provider_alias}", credential["id"], cwd=local))["data"]
    assert verified["executed"] is True
    tools_before = await cli.data("project", "tool", "list")
    assert len(tools_before) == 1
    if with_knowledge:
        await _assert_knowledge_reuses_collection_and_documents(cli, local)
        return
    if kind == "network":
        provider_models = await cli.data("project", "provider-model", "list")
        model_usage = await cli.data(
            "project", "provider-model", "usage", provider_models[0]["id"]
        )
        assert any(
            item["type"] == "network" and item["id"] == target_id
            for item in model_usage["blocking"]
        )
        credential_usage = await cli.data(
            "project", "provider-credential", "usage", credential["id"]
        )
        assert any(
            item["type"] == "network" and item["id"] == target_id
            for item in credential_usage["blocking"]
        )
        config = yaml.safe_load((local / ".woobe-config").read_text())
        assert sum(item["kind"] == "Agent" for item in config["resources"]) == 2
        assert sum(item.get("frozen", False) for item in config["resources"]) == 1
        descriptor = Path(pulled["path"]) / "network.yaml"
        original = yaml.safe_load(descriptor.read_text())
        original["metadata"]["description"] = "Edited local network"
        descriptor.write_text(yaml.safe_dump(original))
        pushed = (await cli.run("network", "@support", "push", cwd=local))["data"]
        assert pushed["pushed"] is True
        assert await cli.data("project", "tool", "list") == tools_before
        agents = await cli.data("agent", "list")
        assert [item["id"] for item in agents] == [agent_id]
        await cli.run("network", "@support", "pull", cwd=local)
        after = yaml.safe_load((local / ".woobe-config").read_text())
        assert len(after["resources"]) == len(config["resources"])
        await _assert_explicit_clone_creation(cli, local, kind, tools_before)
        staged_network = await cli.data("network", "@support", "stage", "--yes", cwd=local)
        assert staged_network["kind"] == "staging"
        published_network = await cli.data("network", "@support", "publish", "--yes", cwd=local)
        assert published_network["kind"] == "release"
        await cli.run("network", "@support", "activate", "--version", published_network["version"], "--notes", "Already active composition", "--yes", cwd=local, expected=6)
        updated = yaml.safe_load(descriptor.read_text())
        updated["spec"]["nodes"][0]["label"] = "Revised entry label"
        descriptor.write_text(yaml.safe_dump(updated))
        await cli.run("network", "@support", "push", cwd=local)
        await cli.data("network", "@support", "stage", "--yes", cwd=local)
        newer = await cli.data("network", "@support", "publish", "--yes", cwd=local)
        assert newer["id"] != published_network["id"]
        rolled_back = await cli.data("network", "@support", "rollback", "--version", published_network["version"], "--notes", "Restore stable composition", "--yes", cwd=local)
        assert rolled_back["version"]["id"] == published_network["id"]
        assert rolled_back["activation"]["activation_kind"] == "rollback"
        activated_network = await cli.data("network", "@support", "activate", "--version", newer["version"], "--notes", "Activate reviewed composition", "--yes", cwd=local)
        assert activated_network["version"]["id"] == newer["id"]
        releases = await cli.data("agent", "release", "list", agent_id)
        assert all(item["status"] != "production" for item in releases)
        await _assert_surface_authoring(cli, local, "network")
        rejected_archive = await cli.run("agent", agent_id, "archive", "--yes", expected=6)
        assert not rejected_archive["success"]
        return
    descriptor = Path(pulled["path"]) / "agent.yaml"
    document = yaml.safe_load(descriptor.read_text())
    document["spec"]["legacy_system_prompt"] = "Help customers with local YAML"
    descriptor.write_text(yaml.safe_dump(document))
    diff = (await cli.run("agent", "@support", "diff", cwd=local))["data"]
    assert diff["changed"] is True
    pushed = (await cli.run("agent", "@support", "push", cwd=local))["data"]
    assert pushed["pushed"] is True
    native = await cli.data("agent", "get", agent_id)
    assert native["system_prompt"] == "Help customers with local YAML"
    assert native["revision"] > 1
    assert await cli.data("project", "tool", "list") == tools_before
    agents = await cli.data("agent", "list", "--query", f"project_id={cli.project_id}")
    assert [item["id"] for item in agents] == [agent_id]
    await cli.data(
        "agent", "update", agent_id, body={"description": "Changed in another client"}
    )
    document["spec"]["legacy_system_prompt"] = "Second local edit"
    descriptor.write_text(yaml.safe_dump(document))
    failure = await cli.run("agent", "@support", "push", cwd=local, expected=6)
    assert not failure["success"]
    latest = await cli.data("agent", "get", agent_id)
    assert latest["description"] == "Changed in another client"
    assert latest["system_prompt"] == "Help customers with local YAML"
    await cli.run("agent", "@support", "pull", cwd=local)
    merged = yaml.safe_load(descriptor.read_text())
    assert merged["spec"]["legacy_system_prompt"] == "Second local edit"
    assert merged["metadata"]["description"] == "Changed in another client"
    await _assert_explicit_clone_creation(cli, local, kind, tools_before)
    await cli.run("agent", "@support", "push", cwd=local)
    prompt_native = await cli.data(
        "agent",
        "prompt",
        "create",
        agent_id,
        body={
            "project_id": cli.project_id,
            "agent_id": agent_id,
            "version": "1.0.0",
            "name": "Instructions",
            "content": "Help customers",
        },
    )
    await cli.data(
        "agent",
        "release",
        "create",
        agent_id,
        body={
            "project_id": cli.project_id,
            "agent_id": agent_id,
            "version": "1.0.0",
            "prompt_version_id": prompt_native["id"],
        },
    )
    await cli.run("agent", "@support", "pull", cwd=local)
    registry_before = yaml.safe_load((local / ".woobe-config").read_text())
    prompt_resource = next(
        item
        for item in registry_before["resources"]
        if item["kind"] == "Prompt" and not item["alias"].startswith("support-copy-")
    )
    prompt_descriptor = local / ".woobe" / prompt_resource["path"] / "prompt.yaml"
    prompt = yaml.safe_load(prompt_descriptor.read_text())
    prompt["spec"]["content"] = "Changed instructions without manually changing version"
    prompt_descriptor.write_text(yaml.safe_dump(prompt))
    await cli.run("agent", "@support", "push", cwd=local)
    prompts = await cli.data("agent", "prompt", "list", agent_id)
    assert len(prompts) == 2
    prompt_versions = [
        await cli.data("agent", "prompt", "get", agent_id, item["id"])
        for item in prompts
    ]
    assert {item["content"] for item in prompt_versions} == {
        "Help customers",
        prompt["spec"]["content"],
    }
    await cli.run("agent", "@support", "pull", cwd=local)
    registry_after = yaml.safe_load((local / ".woobe-config").read_text())
    assert len(registry_after["resources"]) == len(registry_before["resources"])
    assert any(
        item["uid"] == prompt_resource["uid"] for item in registry_after["resources"]
    )
    staged = await cli.data("agent", "@support", "stage", "--yes", cwd=local)
    assert staged["status"] == "staging"
    testcase = local / "testcase.yaml"
    testcase.write_text(yaml.safe_dump({"message": "Answer a simple support question"}))
    executed = (await cli.run("agent", "@support", "test", "--file", str(testcase), cwd=local))["data"]
    assert executed["status"] == "passed", executed
    assert executed["actual_output"]["run_id"]
    assert executed["actual_output"]["answer"]
    recorded = await cli.data("agent", "release", "tests", agent_id, staged["id"])
    assert any(item["id"] == executed["id"] for item in recorded)
    testcase.write_text(yaml.safe_dump({"message": "Answer a simple support question", "expected_output": {"answer": "deliberately impossible assertion"}}))
    failed = await cli.run("agent", "@support", "test", "--file", str(testcase), cwd=local, expected=6)
    assert failed["data"]["status"] == "failed"
    assert failed["data"]["actual_output"]["run_id"]
    assert {item["code"] for item in failed["data"]["validation_errors"]} == {"EXPECTED_OUTPUT_MISMATCH"}
    published = await cli.data("agent", "@support", "publish", "--notes", "Reviewed local development", "--yes", cwd=local)
    assert published["status"] == "released"
    activated = await cli.data("agent", "@support", "activate", "--version", published["version"], "--notes", "Deploy tested release", "--yes", cwd=local)
    assert activated["status"] == "production"
    releases = await cli.data("agent", "@support", "release", "list", cwd=local)
    assert any(item["id"] == activated["id"] for item in releases)
    archived = await cli.data("agent", "@support-next", "delete", "--yes", cwd=local)
    assert archived["status"] == "archived"
    await _assert_surface_authoring(cli, local, "agent")


async def _assert_knowledge_reuses_collection_and_documents(cli, local):
    collections = await cli.data("knowledge", "collection", "list")
    assert len(collections) == 1
    collection_id = collections[0]["id"]
    original_documents = await cli.data("knowledge", "document", "list")
    original_snapshots = await cli.data("knowledge", "snapshot", "list", collection_id)
    registry = yaml.safe_load((local / ".woobe-config").read_text())
    artifact = next(item for item in registry["resources"] if item["kind"] == "Knowledge")
    descriptor = local / ".woobe" / artifact["path"] / "knowledge.yaml"
    assert await cli.data("knowledge", "snapshot", "list", "@" + artifact["alias"], cwd=local) == original_snapshots
    skill = next(item for item in registry["resources"] if item["kind"] == "Skill")
    skill_descriptor = local / ".woobe" / skill["path"] / "skill.yaml"
    skill_document = yaml.safe_load(skill_descriptor.read_text())
    manifest = skill_descriptor.parent / skill_document["spec"]["package"]["manifest"]
    original_manifest = manifest.read_text()
    manifest.write_text(original_manifest + "\nEscalate urgent issues immediately.\n")
    original_versions = await cli.data("skill", "version", "list", "@" + skill["alias"], cwd=local)

    knowledge = yaml.safe_load(descriptor.read_text())
    knowledge["spec"]["vector_snapshot"]["chunking"]["chunk_size"] = 1000
    descriptor.write_text(yaml.safe_dump(knowledge))
    result = (await cli.run("agent", "@support", "push", cwd=local))["data"]
    assert result["pushed"] is True
    versions = await cli.data("skill", "version", "list", "@" + skill["alias"], cwd=local)
    assert len(versions) == len(original_versions) + 1
    assert {item["skill_id"] for item in versions} == {item["skill_id"] for item in original_versions}
    assert await cli.data("knowledge", "collection", "list") == collections
    stored_documents = await cli.data("knowledge", "document", "list")
    stable = lambda documents: [{key: value for key, value in item.items() if key not in {"updated_at", "indexed_at", "chunk_count"}} for item in documents]
    assert stable(stored_documents) == stable(original_documents)
    snapshots = await cli.data("knowledge", "snapshot", "list", collection_id)
    assert len(snapshots) == len(original_snapshots) + 1
    assert all(item["collection_id"] == collection_id for item in snapshots)
    await cli.run("agent", "@support", "pull", cwd=local)
    after = yaml.safe_load((local / ".woobe-config").read_text())
    assert len(after["resources"]) == len(registry["resources"])
    assert next(item for item in after["resources"] if item["kind"] == "Knowledge")["uid"] == artifact["uid"]
    await cli.run("agent", "@support", "push", cwd=local)
    assert len(await cli.data("knowledge", "snapshot", "list", collection_id)) == len(snapshots)


async def _assert_explicit_clone_creation(cli, local, kind, tools_before):
    cloned = (
        await cli.run(
            "resources", "clone", kind, "@support", "--alias", "support-copy", cwd=local
        )
    )["data"]
    assert cloned["resource"]["uid"]
    preview = (await cli.run(kind, "@support-copy", "create", "--dry-run", cwd=local))[
        "data"
    ]
    assert preview["executed"] is False
    assert preview["semantic_validation"] == "server_validated"
    assert preview["effects"]
    reply = await cli.run(kind, "@support-copy", "create", cwd=local, expected=(0, 7))
    assert reply["success"], [
        (item.get("code"), item.get("message"))
        for item in reply.get("data", {}).get("diagnostics", [])
    ]
    created = reply["data"]
    assert created["pushed"] is True
    assert await cli.data("project", "tool", "list") == tools_before
    roots = await cli.data(kind, "list")
    assert len(roots) == 2
    assert len({item["id"] for item in roots}) == 2
    await cli.run(kind, "@support-copy", "create", cwd=local, expected=2)
    assert len(await cli.data(kind, "list")) == 2
    await cli.run(
        "resources",
        "move",
        kind,
        "@support-copy",
        "--path",
        f"{kind}s/relocated",
        cwd=local,
    )
    await cli.run(
        "resources",
        "alias",
        kind,
        "@support-copy",
        "--alias",
        "support-next",
        cwd=local,
    )
    await cli.run(kind, "@support-next", "push", cwd=local)
    assert len(await cli.data(kind, "list")) == 2


async def _assert_surface_authoring(cli, local, target_kind):
    registry = yaml.safe_load((local / ".woobe-config").read_text())
    target_key = next(item["key"] for item in registry["resources"] if item["alias"] == "support" and item["kind"].lower() == target_kind)
    source = local / "surface-author.yaml"
    source.write_text(yaml.safe_dump({
        "format": "woobe-package", "schema_version": "1.0", "kind": "Surface",
        "metadata": {"key": "chat", "name": "Managed chat", "description": "Original"},
        "spec": {"target_ref": target_key, "allowed_origins": ["https://example.test"],
                 "requests_per_minute": 60, "max_concurrent_runs": 2, "session_token_ttl_seconds": 300},
    }))
    await cli.run("resources", "create", "surface", "chat", "--file", str(source), cwd=local)
    created = (await cli.run("surface", "@chat", "create", cwd=local))["data"]
    surface_id = created["resource_id"]
    native = await cli.data("surface", "get", surface_id)
    assert native["target_type"] == target_kind
    assert native["status"] == "draft"
    descriptor = local / ".woobe/surfaces/chat/surface.yaml"
    document = yaml.safe_load(descriptor.read_text())
    document["metadata"]["description"] = "Edited in YAML"
    descriptor.write_text(yaml.safe_dump(document))
    await cli.run("surface", "@chat", "push", cwd=local)
    changed = await cli.data("surface", "get", surface_id)
    assert changed["description"] == "Edited in YAML"
    assert changed["target_release_id"] == native["target_release_id"]
    await cli.data("surface", "update", surface_id, body={"name": "Changed in UI"})
    await cli.run("surface", "@chat", "push", cwd=local, expected=6)
    document["metadata"]["description"] = "Independent local change"
    descriptor.write_text(yaml.safe_dump(document))
    await cli.run("surface", "@chat", "pull", cwd=local)
    merged = yaml.safe_load(descriptor.read_text())
    assert merged["metadata"]["name"] == "Changed in UI"
    assert merged["metadata"]["description"] == "Independent local change"
    await cli.run("surface", "@chat", "push", cwd=local)
    preview = (await cli.run("resources", "push", "--kind", "surface", "--dry-run", cwd=local))["data"]
    assert preview["roots"] == 1 and preview["executed"] is False
    await cli.data("surface", "activate", surface_id, body={})
    await cli.data("surface", "disable", surface_id)
    await cli.data("surface", "archive", surface_id)
    assert (await cli.data("surface", "get", surface_id))["status"] == "archived"
