"""The paired CLI plans through live authorization, PostgreSQL and owner validation."""

import json
import os
import shutil
import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from tests.integration.cli.test_control_plane_workflow import cli as _live_cli

cli = _live_cli


@pytest.mark.asyncio
@pytest.mark.parametrize("public_apply", [False, True])
@pytest.mark.parametrize(
    "with_skill_and_bindings,entry_kind,lifecycle",
    [
        (False, "Agent", "draft"),
        (True, "Agent", "draft"),
        *[
            (False, kind, stage)
            for kind in ("Agent", "Network")
            for stage in ("staging", "release", "production")
        ],
        (False, "Network", "draft"),
    ],
)
async def test_cli_upload_and_native_plan_against_live_postgres(
    cli,
    tmp_path,
    with_skill_and_bindings,
    entry_kind,
    lifecycle,
    public_apply,
    with_knowledge=False,
    without_saved_draft=False,
    with_mcp=False,
    complete_fixture=False,
):
    project = await cli.data(
        "project",
        "create",
        body={
            "workspace_id": cli.workspace_id,
            "name": "Package planning",
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
            "name": "Package fake provider",
            "secret": "ephemeral-package-test-provider-key",
            "metadata": {"provider_family": "openai", "compatibility": "compatible"},
        },
    )
    cli.secret_values.add("ephemeral-package-test-provider-key")
    source = Path(tmp_path) / "portable"
    source.mkdir()
    files = {
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
            },
        },
    }
    provider_url = os.environ.get("WOOBE_TEST_FAKE_PROVIDER_URL")
    if provider_url:
        files["model.yaml"]["spec"]["base_url"] = provider_url
    if with_mcp:
        mcp_url = os.environ["WOOBE_TEST_FAKE_MCP_URL"]
        files["model.yaml"]["spec"]["model"] = "fake-portable-tool"
        files["woobe.yaml"]["spec"]["resources"].append("mcp.yaml")
        files["mcp.yaml"] = {
            "kind": "Tool",
            "metadata": {"key": "lookup", "name": "Lookup"},
            "spec": {
                "type": "mcp",
                "permission": "allow",
                "risk": "low",
                "config": {
                    "mode": "server",
                    "exposure": "all_discovered",
                    "server": {"url": mcp_url},
                },
                "permissions": [
                    {
                        "remote_name": "lookup",
                        "permission": "allow",
                        "risk": "low",
                        "bindings": {
                            "tenant": {"source": {"kind": "context", "field": "tenant"}}
                        },
                    }
                ],
            },
        }
        files["agent.yaml"]["spec"]["tools"] = [{"ref": "lookup"}]
        files["agent.yaml"]["spec"]["external_context"] = {
            "tenant": {"schema": {"type": "string"}, "default": "portable-tenant"}
        }
    if with_knowledge:
        assert provider_url, (
            "Real Knowledge qualification requires a local fake provider"
        )
        files["woobe.yaml"]["spec"]["resources"] += ["embedding.yaml", "knowledge.yaml"]
        files["embedding.yaml"] = {
            "kind": "Model",
            "metadata": {"key": "embedding", "name": "Embedding"},
            "spec": {
                "provider": "custom",
                "model": "fake-embedding",
                "model_type": "embedding",
                "credential": {"ref": "primary"},
                "base_url": provider_url,
            },
        }
        files["knowledge.yaml"] = {
            "kind": "Knowledge",
            "metadata": {"key": "knowledge", "name": "Support Knowledge"},
            "spec": {
                "mode": "portable",
                "collection": {
                    "name": "Support Knowledge",
                    "description": "Portable grounding",
                },
                "documents": [
                    {
                        "path": "documents/support.txt",
                        "title": "Support policy",
                        "content_type": "text/plain",
                    }
                ],
                "embedding": {"model_ref": "embedding"},
                "vector_snapshot": {},
            },
        }
        files["agent.yaml"]["spec"]["knowledge"] = {"source": {"ref": "knowledge"}}
        (source / "documents").mkdir()
        (source / "documents/support.txt").write_text(
            "Woobe support escalates unresolved issues to an owner. Portable Knowledge survives after local files are deleted."
        )
    binding_arguments = []
    protected = {}
    if with_skill_and_bindings:
        files["woobe.yaml"]["spec"]["resources"].append("skill.yaml")
        requirements = files["woobe.yaml"]["spec"]["requires"]
        requirements["project_environment"] = [
            {"key": "PACKAGE_TEST_TOKEN", "kind": "secret"}
        ]
        requirements["secrets"] = [{"ref": "package-tool-token"}]
        files["agent.yaml"]["spec"]["context"] = {
            "policy": {
                "allowed_sources": ["SYSTEM", "USER_INPUT", "SESSION", "TOOL", "SKILL"],
                "skills": {},
            }
        }
        files["agent.yaml"]["spec"]["skills"] = [
            {"ref": "support-skill", "version": "1.0.0"}
        ]
        files["skill.yaml"] = {
            "kind": "Skill",
            "metadata": {"key": "support-skill", "name": "Support skill"},
            "spec": {
                "version": "1.0.0",
                "package": {
                    "manifest": "SKILL.md",
                    "resources": ["references/checklist.md"],
                },
            },
        }
        (source / "SKILL.md").write_text(
            "---\nname: support-skill\ndescription: Support customers\n---\nFollow the reference"
        )
        (source / "references").mkdir()
        (source / "references/checklist.md").write_text("Escalate unresolved issues")
        binding_file = Path(tmp_path) / "bindings.json"
        binding_file.write_text(
            json.dumps(
                {
                    "format": "woobe-package",
                    "schema_version": "1.0",
                    "kind": "ImportBindings",
                    "metadata": {"name": "Destination"},
                    "spec": {
                        "project_environment": {
                            "PACKAGE_TEST_TOKEN": {"protected_ref": "environment-token"}
                        },
                        "secrets": {
                            "package-tool-token": {"protected_ref": "tool-token"}
                        },
                    },
                }
            )
        )
        binding_arguments = ["--bindings", str(binding_file)]
        protected = {
            "environment-token": "ephemeral-native-environment-token",
            "tool-token": "ephemeral-native-tool-token",
        }
        cli.secret_values.update(protected.values())
        if public_apply:
            for alias, value in protected.items():
                await cli.run(
                    "auth",
                    "credential",
                    "import",
                    "--name",
                    alias,
                    "--stdin",
                    stdin_bytes=value.encode(),
                )
    if entry_kind == "Network":
        files["woobe.yaml"]["spec"]["entrypoint"] = {
            "kind": "Network",
            "ref": "support-network",
        }
        files["woobe.yaml"]["spec"]["resources"].append("network.yaml")
        files["network.yaml"] = {
            "kind": "Network",
            "metadata": {"key": "support-network", "name": "Support Network"},
            "spec": {
                "root": "support-root",
                "nodes": [
                    {"key": "support-root", "agent_ref": "support", "label": "Support"}
                ],
                "edges": [],
            },
        }
    if complete_fixture:
        from copy import deepcopy

        files["woobe.yaml"]["spec"]["resources"] += [
            "fallback.yaml",
            "contract.yaml",
            "prompt.yaml",
        ]
        files["woobe.yaml"]["spec"]["resources"].append("http.yaml")
        files["http.yaml"] = {
            "kind": "Tool",
            "metadata": {"key": "guarded", "name": "guarded_lookup"},
            "spec": {
                "type": "http",
                "description": "Portable authenticated lookup",
                "timeout_ms": 5000,
                "config": {
                    "protocol": "http",
                    "mode": "single",
                    "method": "GET",
                    "url": os.environ["WOOBE_TEST_FAKE_MCP_URL"].removesuffix("/mcp")
                    + "/http-protected",
                    "headers": [
                        {
                            "key": "Authorization",
                            "value": "Bearer {{project_env.PACKAGE_TEST_TOKEN}}",
                            "sensitive": True,
                            "mode": "set",
                        },
                        {
                            "key": "X-Tool-Token",
                            "value": "{{secret:package-tool-token}}",
                            "sensitive": True,
                            "mode": "set",
                        },
                    ],
                    "bindings": {},
                },
                "input_schema": {
                    "type": "object",
                    "properties": {},
                    "additionalProperties": False,
                },
            },
        }
        files["agent.yaml"]["spec"]["tools"].append({"ref": "guarded"})
        files["model.yaml"]["spec"]["model"] = "fake-portable-http"
        files["skill.yaml"]["spec"]["required_tools"] = ["guarded_lookup"]

        files["fallback.yaml"] = deepcopy(files["model.yaml"])
        files["fallback.yaml"]["metadata"] = {"key": "fallback", "name": "Fallback"}
        files["fallback.yaml"]["spec"]["model"] = "fake-success"
        files["contract.yaml"] = {
            "kind": "Contract",
            "metadata": {"key": "answer", "name": "Answer contract"},
            "spec": {
                "version": "1.0.0",
                "validation_mode": "lenient",
                "repair_attempts": 0,
                "input_schema": {},
                "output_schema": {
                    "type": "object",
                    "properties": {"answer": {"type": "string"}},
                    "required": ["answer"],
                },
                "additional_instructions": "Return the portable answer.",
            },
        }
        files["prompt.yaml"] = {
            "kind": "Prompt",
            "metadata": {"key": "instructions", "name": "Instructions"},
            "spec": {
                "version": "1.0.0",
                "content": "Resolve portable customer requests with the installed capabilities.",
            },
        }
        agent_spec = files["agent.yaml"]["spec"]
        agent_spec.pop("legacy_system_prompt", None)
        agent_spec["prompt_ref"] = "instructions"
        agent_spec["model"]["fallback"] = {"ref": "fallback"}
        agent_spec["model"]["parameters"] = {
            "temperature": 0.23,
            "max_output_tokens": 1234,
        }
        agent_spec["execution"] = {"strategy": "standard", "config": {}}
        agent_spec["context"]["manager"] = {"name": "stdcm"}
        agent_spec["context"]["policy"]["allowed_sources"] += ["KNOWLEDGE", "RUNTIME"]
        agent_spec["session"] = {"mode": "stateful"}
        agent_spec["output"] = {"contract_ref": "answer"}
        agent_spec["knowledge"]["rag"] = {
            "top_k": 3,
            "candidate_k": 7,
            "max_context_chunks": 3,
            "max_chunks_per_document": 2,
            "max_context_chars": 11000,
        }
        if entry_kind == "Network":
            files["woobe.yaml"]["spec"]["resources"].append("specialist.yaml")
            files["specialist.yaml"] = deepcopy(files["agent.yaml"])
            files["specialist.yaml"]["metadata"] = {
                "key": "specialist",
                "name": "Portable specialist",
            }
            files["specialist.yaml"]["spec"].pop("prompt_ref")
            files["specialist.yaml"]["spec"]["behavior"] = {
                "schema_version": 1,
                "objective": "Investigate portable requests",
                "responsibilities": ["Inspect evidence"],
                "allowed_behaviors": ["Use installed tools"],
                "disallowed_behaviors": ["Invent facts"],
                "operating_instructions": "Read the Skill checklist",
                "response_guidelines": "Be precise",
                "additional_instructions": "Escalate if needed",
            }
            network = files["network.yaml"]["spec"]
            network["nodes"] = [
                {
                    "key": "support-root",
                    "agent_ref": "support",
                    "label": "Coordinator",
                    "position": {"x": 11, "y": 22},
                    "binding": {"source": "release"},
                },
                {
                    "key": "support-draft",
                    "agent_ref": "support",
                    "label": "Draft view",
                    "position": {"x": 33, "y": 44},
                    "binding": {"source": "draft"},
                },
                {
                    "key": "specialist",
                    "agent_ref": "specialist",
                    "label": "Investigator",
                    "capability_description": "Inspect grounding",
                    "binding": {"source": "staging"},
                },
            ]
            network["edges"] = [
                {"from": "support-root", "to": "specialist"},
                {"from": "support-root", "to": "support-draft"},
            ]
            network["settings"] = {
                "session_mode": "stateful",
                "max_depth": 4,
                "max_invocations": 12,
                "timeout_seconds": 90,
                "tool_result_max_chars": 15000,
            }
    audit_arguments = []
    if lifecycle != "draft":
        audit_arguments = ["--lifecycle", lifecycle]
    if lifecycle in {"release", "production"}:
        audit_arguments += ["--release-notes", "Qualified package release"]
    if lifecycle == "production":
        audit_arguments += ["--reason", "Qualified package activation"]
    for path, document in files.items():
        (source / path).write_text(
            json.dumps({"format": "woobe-package", "schema_version": "1.0", **document})
        )
    receipt = Path(tmp_path) / "approved-plan.json"
    before_agents = await cli.data("project", "agent", "list")
    result = await cli.run(
        "package",
        "plan",
        str(source),
        "--bind",
        f"credential.primary={credential['id']}",
        *binding_arguments,
        *audit_arguments,
        "--save-plan",
        str(receipt),
        "--validate-body",
        "--validate-parameters",
    )
    plan = result["data"]
    assert plan["project_id"] == cli.project_id and plan["api_origin"] == cli.origin
    assert plan["lifecycle"] == lifecycle
    expected = (
        ["create_environment_value", "create_secret"] if with_skill_and_bindings else []
    )
    if with_mcp:
        expected += ["materialize_tool", "verify_mcp_discovery", "verify_mcp_readiness"]
    expected += ["resolve_model"]
    if with_knowledge:
        expected += [
            "create_collection",
            "upload_document",
            "build_vector_snapshot",
            "verify_vector_snapshot",
            "resolve_model",
        ]
    expected += ["materialize_skill_version"] if with_skill_and_bindings else []
    expected += ["prepare_inactive_agent"]
    if with_knowledge:
        expected += ["create_agent_knowledge_version"]
    expected += ["finalize_agent_draft"]
    if entry_kind == "Network":
        expected += ["prepare_network", "save_network_draft"]
    if lifecycle != "draft":
        expected += ["create_staging"]
    if lifecycle in {"release", "production"}:
        expected += ["create_immutable_release"]
    if lifecycle == "production":
        expected += ["activate_production"]
    if entry_kind == "Network":
        expected += ["verify_constituent_agent"]
    expected += ["verify_materialized_package"]
    if complete_fixture:
        expected = [effect["action"] for effect in plan["effects"]]
        assert (
            "create_contract_version" in expected
            and "create_prompt_version" in expected
        )
        assert expected.count("prepare_inactive_agent") == (
            2 if entry_kind == "Network" else 1
        )
        assert expected.count("resolve_model") == 3
    else:
        assert [effect["action"] for effect in plan["effects"]] == expected
    assert len(plan["plan_digest"]) == 64 and receipt.stat().st_mode & 0o777 == 0o600
    assert "ephemeral-package-test-provider-key" not in receipt.read_text()
    assert await cli.data("project", "agent", "list") == before_agents

    if public_apply:
        applied = await cli.run(
            "package",
            "import",
            "--plan-file",
            str(receipt),
            "--checkpoint",
            str(Path(tmp_path) / "checkpoint.json"),
            *([] if with_knowledge else ["--wait"]),
            "--wait-timeout",
            "60s",
            "--validate-body",
            "--validate-parameters",
        )
        if with_knowledge:
            applied = await complete_knowledge_operation(
                cli, Path(tmp_path) / "checkpoint.json"
            )
        final = applied["data"]
        assert applied["meta"]["complete"] is True
        assert final["state"] == "succeeded", final["diagnostics"]
        assert final["phases_completed"] == final["phases_total"] == len(expected)
        assert final["configuration_ready"] is True and final["execution_ready"] is True
        assert len(await cli.data("project", "agent", "list")) == len(before_agents) + (
            2 if complete_fixture and entry_kind == "Network" else 1
        )
        checkpoint = json.loads((Path(tmp_path) / "checkpoint.json").read_text())
        assert checkpoint["operation_id"] == final["operation_id"]
        assert checkpoint["state"] == "terminal"
        replay = await cli.run(
            "package",
            "import",
            "--plan-file",
            str(receipt),
            "--checkpoint",
            str(Path(tmp_path) / "replay-checkpoint.json"),
            "--idempotency-key",
            checkpoint["idempotency_key"],
            "--wait",
        )
        assert replay["data"]["operation_id"] == final["operation_id"]
        assert replay["data"]["state"] == "succeeded"
        assert len(await cli.data("project", "agent", "list")) == len(before_agents) + (
            2 if complete_fixture and entry_kind == "Network" else 1
        )
        target = next(
            item["resource_id"]
            for item in final["inventory"]
            if item["action"]
            == (
                "prepare_network"
                if entry_kind == "Network"
                else "prepare_inactive_agent"
            )
        )
        if without_saved_draft:
            from sqlalchemy import delete
            from modules.agent.infra.database.models import AgentReleaseModel
            from shared.infra.config import Settings
            from shared.infra.database.session import (
                create_engine,
                create_session_factory,
            )

            fixture_engine = create_engine(Settings())
            async with create_session_factory(fixture_engine).begin() as session:
                await session.execute(
                    delete(AgentReleaseModel).where(
                        AgentReleaseModel.agent_id == target,
                        AgentReleaseModel.snapshot_kind == "draft",
                    )
                )
            await fixture_engine.dispose()
        exported = Path(tmp_path) / "exported"
        export_result = await cli.run(
            "package",
            "export",
            entry_kind.lower(),
            target,
            "--source",
            lifecycle,
            "--destination",
            str(exported),
            "--name",
            "Support",
            "--version",
            "1.0.0",
            "--validate-body",
            "--validate-parameters",
        )
        assert (
            export_result["data"]["closure_complete"]
            and export_result["data"]["self_contained"]
        )
        validated = await cli.run("package", "validate", str(exported), "--locked")
        assert (
            validated["data"]["artifact_digest"]
            == export_result["data"]["artifact_digest"]
        )
        assert "ephemeral-package-test-provider-key" not in "".join(
            path.read_text() for path in exported.glob("*.yaml")
        )
        destination_project = await cli.data(
            "project",
            "create",
            body={
                "workspace_id": cli.workspace_id,
                "name": "Package destination",
                "slug": str(uuid4()),
            },
        )
        cli.project_id = destination_project["id"]
        destination_credential = await cli.data(
            "project",
            "provider-credential",
            "create",
            body={
                "project_id": cli.project_id,
                "provider": "custom",
                "name": "Destination fake provider",
                "secret": "ephemeral-package-destination-provider-key",
                "metadata": {
                    "provider_family": "openai",
                    "compatibility": "compatible",
                },
            },
        )
        cli.secret_values.add("ephemeral-package-destination-provider-key")
        destination_binding_arguments = []
        if complete_fixture:
            requirements = json.loads((exported / "woobe.yaml").read_text())["spec"][
                "requires"
            ]
            bindings = {
                "format": "woobe-package",
                "schema_version": "1.0",
                "kind": "ImportBindings",
                "metadata": {"name": "Destination protected references"},
                "spec": {
                    "project_environment": {
                        item["key"]: {"protected_ref": "environment-token"}
                        for item in requirements["project_environment"]
                    },
                    "secrets": {
                        item["ref"]: {"protected_ref": "tool-token"}
                        for item in requirements["secrets"]
                    },
                },
            }
            destination_bindings = Path(tmp_path) / "destination-bindings.json"
            destination_bindings.write_text(json.dumps(bindings))
            destination_binding_arguments = ["--bindings", str(destination_bindings)]
        imported = await cli.run(
            "package",
            "import",
            str(exported),
            "--bind",
            f"credential.credential-1={destination_credential['id']}",
            *destination_binding_arguments,
            *audit_arguments,
            "--checkpoint",
            str(Path(tmp_path) / "reimport-checkpoint.json"),
            *([] if with_knowledge else ["--wait"]),
            "--wait-timeout",
            "60s",
            "--locked",
            "--validate-body",
            "--validate-parameters",
        )
        if with_knowledge:
            imported = await complete_knowledge_operation(
                cli, Path(tmp_path) / "reimport-checkpoint.json"
            )
        assert imported["data"]["state"] == "succeeded", imported["data"]["diagnostics"]
        imported_target = next(
            item["resource_id"]
            for item in imported["data"]["inventory"]
            if item["action"]
            == (
                "prepare_network"
                if entry_kind == "Network"
                else "prepare_inactive_agent"
            )
        )
        reexported = Path(tmp_path) / "reexported"
        await cli.run(
            "package",
            "export",
            entry_kind.lower(),
            imported_target,
            "--source",
            lifecycle,
            "--destination",
            str(reexported),
            "--name",
            "Support",
            "--version",
            "1.0.0",
        )
        left = {
            path.name: json.loads(path.read_text()) for path in exported.glob("*.yaml")
        }
        right = {
            path.name: json.loads(path.read_text())
            for path in reexported.glob("*.yaml")
        }
        for documents in (left, right):
            documents["woobe.yaml"].pop("provenance", None)
        assert left == right

        def support_bytes(root):
            return {
                str(path.relative_to(root)): path.read_bytes()
                for path in root.rglob("*")
                if path.is_file()
                and path.suffix != ".yaml"
                and path.name != "woobe.lock.json"
            }

        assert support_bytes(exported) == support_bytes(reexported)
        if provider_url and lifecycle != "draft":
            shutil.rmtree(source)
            shutil.rmtree(exported)
            shutil.rmtree(reexported)
            runtime_environment = "staging" if lifecycle == "release" else lifecycle
            _, runtime_key = await cli.issue(
                "project",
                "runtime-key",
                "create",
                body={
                    "project_id": cli.project_id,
                    "name": "Portable runtime",
                    "target_type": entry_kind.lower(),
                    "target_id": imported_target,
                    "environment": runtime_environment,
                    "interfaces": ["http", "stream"],
                    "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
                },
            )
            run = await cli.run(
                "runtime",
                "target",
                "run",
                "portable-import",
                "--target-kind",
                entry_kind.lower(),
                body={"input": "Hello"},
                runtime_key=runtime_key,
                expected=0,
            )
            assert run["data"]["success"] is True
            if with_mcp:
                if entry_kind == "Agent":
                    calls = run["data"]["data"]["tool_calls"]
                else:
                    # The Network HTTP result exposes its aggregate output,
                    # while native child Agent runs retain Tool evidence.
                    # Inspect only this destination Project/Network after the
                    # authorized CLI runtime request has completed.
                    from uuid import UUID
                    from sqlalchemy import select
                    from modules.agent.infra.database.run_models import AgentRunModel
                    from modules.network.infra.database.models import (
                        NetworkExecutionModel,
                    )
                    from shared.composition_resources import SESSION_FACTORY

                    async with SESSION_FACTORY() as session:
                        children = (
                            (
                                await session.execute(
                                    select(AgentRunModel)
                                    .join(
                                        NetworkExecutionModel,
                                        AgentRunModel.network_execution_id
                                        == NetworkExecutionModel.id,
                                    )
                                    .where(
                                        AgentRunModel.project_id
                                        == UUID(cli.project_id),
                                        NetworkExecutionModel.project_id
                                        == UUID(cli.project_id),
                                        NetworkExecutionModel.network_id
                                        == UUID(imported_target),
                                    )
                                )
                            )
                            .scalars()
                            .all()
                        )
                    assert children and all(
                        child.status == "completed" for child in children
                    )
                    calls = [
                        call
                        for child in children
                        for call in (child.result or {}).get("tool_calls", [])
                    ]
                assert len(calls) == 1 and calls[0]["success"] is True
                assert "portable-tenant" in json.dumps(calls[0]["output"])
        return

    # Exercise the current owner materializer directly until Apply and worker
    # registration advertise every component/lifecycle in the complete plan.
    from uuid import UUID
    from sqlalchemy import select
    from modules.core.infra.database.control_key_models import WorkspaceControlKeyModel
    from modules.package.entrypoint import build_package_service
    from modules.package.application.execution import ExecutePackageOperation
    from modules.package.infra.native_materializer import NativePackageMaterializer
    from shared.composition_resources import SESSION_FACTORY, SETTINGS
    from shared.security.principal import ControlPlanePrincipal

    async with SESSION_FACTORY() as session:
        root = (
            await session.execute(
                select(WorkspaceControlKeyModel).where(
                    WorkspaceControlKeyModel.workspace_id == UUID(cli.workspace_id)
                )
            )
        ).scalar_one()
        principal = ControlPlanePrincipal(
            api_key_id=root.id,
            credential_id=root.credential_id,
            workspace_id=root.workspace_id,
            key_prefix=root.key_prefix,
            permissions=frozenset(root.permissions),
            on_project_create_permissions=frozenset(root.on_project_create_permissions),
            authenticated_at=datetime.now(UTC),
            expires_at=root.expires_at,
        )
    service = build_package_service()
    approved_private = json.loads(receipt.read_text())["plan"]
    payload = {
        "plan_id": plan["plan_id"],
        "plan_digest": plan["plan_digest"],
        "upload_id": plan["upload_id"],
        "artifact_digest": plan["artifact_digest"],
        "bindings": approved_private["bindings"],
        "protected_bindings": protected,
        "lifecycle": lifecycle,
        "release_notes": approved_private["release_notes"],
        "reason": approved_private["reason"],
    }
    operation, replayed = await service.operations.accept(
        project_id=UUID(cli.project_id),
        principal=principal,
        key="native-owner-" + str(uuid4()),
        payload=payload,
    )
    assert replayed is False

    class ObservedMaterializer(NativePackageMaterializer):
        async def execute_phase(self, work, phase):
            try:
                return await super().execute_phase(work, phase)
            except Exception as exc:
                import traceback

                frames = [
                    (frame.filename, frame.lineno, frame.name)
                    for frame in traceback.extract_tb(exc.__traceback__)
                ]
                pytest.fail(
                    f"Native phase {phase['key']}: {type(exc).__name__}: {frames}"
                )

    worker = ExecutePackageOperation(
        service.operations,
        ObservedMaterializer(
            encryption_key=SETTINGS.encryption_key, artifacts=service.artifacts
        ),
    )
    assert await worker.run_once(project_id=UUID(cli.project_id))
    final = await service.status(
        project_id=UUID(cli.project_id), principal=principal, operation_id=operation.id
    )
    assert final["state"] == "succeeded", final["diagnostics"]
    assert final["phases_completed"] == final["phases_total"] == len(expected)
    assert final["configuration_ready"] is True and final["execution_ready"] is True
    assert len(await cli.data("project", "agent", "list")) == len(before_agents) + (
        2 if complete_fixture and entry_kind == "Network" else 1
    )

    from modules.agent.entrypoint import build_portable_agent_export_reader

    imported_agent = next(
        item["resource_id"]
        for item in final["inventory"]
        if item["action"] == "prepare_inactive_agent"
    )
    captured = await build_portable_agent_export_reader().capture(
        project_id=UUID(cli.project_id),
        principal=principal,
        sources=[{"agent_id": UUID(imported_agent), "source": "draft"}],
    )
    assert captured[0]["definition"]["name"] == "Support"
    assert captured[0]["definition"]["model"] == "fake"
    assert len(captured[0]["skills"]) == int(with_skill_and_bindings)
    assert "ephemeral-package-test-provider-key" not in json.dumps(
        captured, default=str
    )

    if entry_kind == "Network":
        from modules.network.entrypoint import build_portable_network_export_reader

        imported_network = next(
            item["resource_id"]
            for item in final["inventory"]
            if item["action"] == "prepare_network"
        )
        network_capture = await build_portable_network_export_reader().capture(
            project_id=UUID(cli.project_id),
            principal=principal,
            network_id=UUID(imported_network),
            source=lifecycle,
        )
        assert network_capture["spec"]["root"] == "support-root"
        assert network_capture["spec"]["nodes"][0]["agent_ref"] == "agent-1"
        assert network_capture["agents"][0]["definition"]["name"] == "Support"


async def complete_knowledge_operation(cli, checkpoint):
    for _ in range(120):
        response = await cli.run(
            "package", "status", "--checkpoint", str(checkpoint), expected=(0, 7)
        )
        assert "data" in response, response.get("error")
        operation = response["data"]
        if operation["terminal"]:
            assert operation["state"] == "succeeded", (
                operation["phase"],
                operation["diagnostics"],
            )
            return response
        if operation["state"] == "waiting_dependency":
            for dependency in operation["dependencies"]:
                assert dependency["kind"] == "VectorSnapshot"
                snapshot = await cli.data(
                    "project", "knowledge", "snapshot", "get", dependency["id"]
                )
                assert snapshot["status"] != "FAILED", "Native Knowledge build failed"
                if snapshot["status"] != "READY":
                    break
            else:
                resumed = await cli.run(
                    "package",
                    "resume",
                    "--checkpoint",
                    str(checkpoint),
                    "--revision",
                    str(operation["revision"]),
                    expected=(0, 6),
                )
                if "error" in resumed:
                    # The worker may observe readiness first. Never replay resume
                    # with the stale revision; the next loop observes fresh state.
                    assert (
                        resumed["error"]["domain_code"] == "PACKAGE_REVISION_CONFLICT"
                    )
        await asyncio.sleep(max(1.0, operation.get("next_poll_after_ms", 1000) / 1000))
    pytest.fail(
        "Native Knowledge readiness did not complete within the bounded qualification"
    )


@pytest.mark.asyncio
async def test_public_knowledge_export_rebuild_and_runtime_after_local_files_removed(
    cli, tmp_path
):
    await test_cli_upload_and_native_plan_against_live_postgres(
        cli, tmp_path, False, "Agent", "staging", True, with_knowledge=True
    )


@pytest.mark.asyncio
async def test_public_export_captures_a_live_draft_without_creating_a_snapshot(
    cli, tmp_path
):
    await test_cli_upload_and_native_plan_against_live_postgres(
        cli, tmp_path, False, "Agent", "draft", True, without_saved_draft=True
    )


@pytest.mark.asyncio
async def test_public_mcp_fresh_discovery_roundtrip_and_runtime(cli, tmp_path):
    await test_cli_upload_and_native_plan_against_live_postgres(
        cli, tmp_path, False, "Agent", "staging", True, with_mcp=True
    )


@pytest.mark.asyncio
async def test_public_skill_and_protected_bindings_roundtrip_runtime(cli, tmp_path):
    await test_cli_upload_and_native_plan_against_live_postgres(
        cli, tmp_path, True, "Agent", "staging", True
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["Agent", "Network"])
async def test_public_complete_composition_roundtrip_and_runtime(cli, tmp_path, kind):
    await test_cli_upload_and_native_plan_against_live_postgres(
        cli,
        tmp_path,
        True,
        kind,
        "staging",
        True,
        with_knowledge=True,
        with_mcp=True,
        complete_fixture=True,
    )
