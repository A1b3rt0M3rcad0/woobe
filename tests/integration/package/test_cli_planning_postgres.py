"""The paired CLI plans through live authorization, PostgreSQL and owner validation."""

import json
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
    cli, tmp_path, with_skill_and_bindings, entry_kind, lifecycle, public_apply
):
    if public_apply and with_skill_and_bindings:
        pytest.skip(
            "Protected-store public apply is qualified in the dedicated fixture"
        )
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
    expected += ["resolve_model"]
    expected += ["materialize_skill_version"] if with_skill_and_bindings else []
    expected += ["prepare_inactive_agent", "finalize_agent_draft"]
    if entry_kind == "Network":
        expected += ["prepare_network", "save_network_draft"]
    if lifecycle != "draft":
        expected += ["create_staging"]
    if lifecycle in {"release", "production"}:
        expected += ["create_immutable_release"]
    if lifecycle == "production":
        expected += ["activate_production"]
    expected += ["verify_materialized_package"]
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
            "--wait",
            "--wait-timeout",
            "60s",
            "--validate-body",
            "--validate-parameters",
        )
        final = applied["data"]
        assert applied["meta"]["complete"] is True
        assert final["state"] == "succeeded", final["diagnostics"]
        assert final["phases_completed"] == final["phases_total"] == len(expected)
        assert final["configuration_ready"] is True and final["execution_ready"] is True
        assert len(await cli.data("project", "agent", "list")) == len(before_agents) + 1
        checkpoint = json.loads((Path(tmp_path) / "checkpoint.json").read_text())
        assert checkpoint["operation_id"] == final["operation_id"]
        assert checkpoint["state"] == "terminal"
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
        imported = await cli.run(
            "package",
            "import",
            str(exported),
            "--bind",
            f"credential.credential-1={destination_credential['id']}",
            *audit_arguments,
            "--checkpoint",
            str(Path(tmp_path) / "reimport-checkpoint.json"),
            "--wait",
            "--wait-timeout",
            "60s",
            "--locked",
            "--validate-body",
            "--validate-parameters",
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
        return

    # Exercise the current owner materializer directly until Apply and worker
    # registration advertise every component/lifecycle in the complete plan.
    from datetime import UTC, datetime
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
    assert len(await cli.data("project", "agent", "list")) == len(before_agents) + 1

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
