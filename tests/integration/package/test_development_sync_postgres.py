"""Local authoring round trip over the real CLI, HTTP, durable worker and SQL."""

import json
from pathlib import Path
from uuid import uuid4

import pytest
import yaml
from tests.integration.cli.test_control_plane_workflow import cli as _live_cli

cli = _live_cli


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["agent", "network"])
async def test_managed_agent_pull_edit_push_keeps_native_identity_and_rejects_stale_base(
    cli, tmp_path, kind
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
    tools_before = await cli.data("project", "tool", "list")
    assert len(tools_before) == 1
    if kind == "network":
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
