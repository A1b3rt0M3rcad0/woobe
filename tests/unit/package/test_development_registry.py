from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from modules.package.application.semantic_definition import semantic_digests
from modules.package.domain.bundle import PackageGraph
from modules.package.domain.errors import PackageError
from modules.package.infra.development_registry import DevelopmentRegistry
from modules.package.infra.models import PackageResourceBindingModel
from shared.infra.database.base import Base


@pytest.mark.asyncio
async def test_registered_roots_retain_identity_dependencies_copy_on_write_and_stale_base_rejected():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        execution_options={"schema_translate_map": {"package": None}},
    )
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(
            lambda sync: Base.metadata.create_all(
                sync, tables=[PackageResourceBindingModel.__table__]
            )
        )
    project, registry_id, agent_id, tool_id = uuid4(), uuid4(), uuid4(), uuid4()
    agent_uid, tool_uid = uuid4(), uuid4()
    reader = SimpleNamespace(
        inspect=AsyncMock(
            side_effect=lambda _session, **kw: {
                "resource_id": str(kw["resource_id"]),
                "revision": 7,
                "draft_id": str(uuid4()),
            }
        )
    )
    registry = DevelopmentRegistry(sessions, reader, reader)
    components = {
        "tool": {
            "kind": "Tool",
            "metadata": {"key": "tool", "name": "Lookup"},
            "spec": {"type": "http", "description": "Updated"},
        },
        "agent": {
            "kind": "Agent",
            "metadata": {"key": "agent", "name": "Support"},
            "spec": {
                "model": {},
                "tools": [{"ref": "tool"}],
                "legacy_system_prompt": "Help",
            },
        },
    }
    graph = PackageGraph(
        {}, components, {"tool": "tool.yaml", "agent": "agent.yaml"}, ("tool", "agent")
    )
    targets = {
        "tool": {
            "resource_uid": str(tool_uid),
            "resource_id": str(tool_id),
            "expected_revision": 7,
        },
        "agent": {
            "resource_uid": str(agent_uid),
            "resource_id": str(agent_id),
            "expected_revision": 7,
        },
    }
    effects = [
        {"component": "tool", "action": "materialize_tool", "permission": "tool:write"},
        {
            "component": "agent",
            "action": "prepare_inactive_agent",
            "permission": "agent:write",
        },
        {
            "component": "agent",
            "action": "finalize_agent_draft",
            "permission": "agent:version",
        },
    ]
    async with sessions.begin() as session:
        session.add_all(
            [
                PackageResourceBindingModel(
                    project_id=project,
                    registry_id=registry_id,
                    resource_uid=tool_uid,
                    kind="Tool",
                    resource_id=tool_id,
                ),
                PackageResourceBindingModel(
                    project_id=project,
                    registry_id=registry_id,
                    resource_uid=agent_uid,
                    kind="Agent",
                    resource_id=agent_id,
                ),
            ]
        )
    document = {"bindings": {}, "binding_resolutions": {}, "effects": deepcopy(effects)}
    async with sessions.begin() as session:
        await registry.prepare(
            session,
            project_id=project,
            principal="principal",
            registry_id=str(registry_id),
            targets=targets,
            graph=graph,
            inventory=[],
            document=document,
        )
    assert document["effects"][0]["identity_policy"] == "copy_on_write"
    assert document["effects"][1]["action"] == "prepare_existing_agent"
    assert document["resource_bindings"]["agent"]["resource_id"] == str(agent_id)
    assert reader.inspect.await_args.kwargs["principal"] == "principal"
    targets["agent"]["expected_revision"] = 6
    with pytest.raises(PackageError, match="changed after the local base"):
        async with sessions.begin() as session:
            await registry.prepare(
                session,
                project_id=project,
                principal="principal",
                registry_id=str(registry_id),
                targets=targets,
                graph=graph,
                inventory=[],
                document={
                    "bindings": {},
                    "binding_resolutions": {},
                    "effects": effects,
                },
            )
    await engine.dispose()


def test_semantic_definition_is_independent_of_keys_paths_and_credential_aliases():
    original = {
        "m": {
            "kind": "Model",
            "metadata": {"key": "m", "name": "Chat"},
            "spec": {"credential": {"ref": "one"}, "model": "chat"},
        },
        "a": {
            "kind": "Agent",
            "metadata": {"key": "a", "name": "Agent"},
            "spec": {"model": {"primary": {"ref": "m"}}},
        },
    }
    renamed = deepcopy(original)
    renamed["model-local"] = renamed.pop("m")
    renamed["agent-local"] = renamed.pop("a")
    renamed["model-local"]["metadata"]["key"] = "model-local"
    renamed["model-local"]["spec"]["credential"]["ref"] = "two"
    renamed["agent-local"]["metadata"]["key"] = "agent-local"
    renamed["agent-local"]["spec"]["model"]["primary"]["ref"] = "model-local"
    first = semantic_digests(original, ("m", "a"), {}, [], {"one": "native"})
    second = semantic_digests(
        renamed, ("model-local", "agent-local"), {}, [], {"two": "native"}
    )
    assert first["a"] == second["agent-local"]
    renamed["model-local"]["spec"]["model"] = "different"
    changed = semantic_digests(
        renamed, ("model-local", "agent-local"), {}, [], {"two": "native"}
    )
    assert first["a"] != changed["agent-local"]
