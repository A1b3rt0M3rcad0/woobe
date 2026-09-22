from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from modules.agent.infra.context_management.managers.resolver import build_context_assembler
from modules.agent.application.context_assembly import (
    ContextBudgetExceeded,
    assemble_context,
    estimate_input_units,
)
from modules.agent.application.interfaces.context_assembler import ContextAssemblyRequest
from modules.agent.application.interfaces.context_policy import (
    ContextPolicyV1,
    SkillContextPolicy,
    resolve_context_policy,
)
from modules.agent.application.interfaces.execution_context import (
    current_execution,
    new_execution_context,
)
from modules.agent.application.skill_bindings import (
    freeze_skill_bindings,
    frozen_enabled_skills,
)
from modules.agent.application.skill_packages import (
    ImportSkillInput,
    parse_skill_package,
)
from modules.agent.application.skill_runtime import (
    SkillRuntime,
    skill_contribution_content,
)
from modules.agent.application.use_cases.skill_cases import SkillCatalog
from modules.agent.domain.skills import SkillVersion, skill_package_hash
from modules.agent.infra.execution.instrumented_execution_runner import (
    configure_skill_runtime,
    run_instrumented_execution,
)
from shared.contracts.errors import NotFoundError, ValidationError


@pytest.fixture
def version():
    package = parse_skill_package(
        ImportSkillInput(
            version="1.0.0",
            skill_md="---\nname: invoice-review\ndescription: Review invoices before approval.\n---\nCheck invoice totals and use references/checklist.md.",
            resources={
                "references/checklist.md": "Compare tax and subtotal before approving."
            },
        )
    )
    return SkillVersion(
        skill_id=uuid4(),
        project_id=uuid4(),
        version="1.0.0",
        package=package,
        package_hash=skill_package_hash(package),
    )


def runtime_config(version):
    return {
        "context_assembler": {"name": "standard"},
        "context": {
            "allowed_sources": ["SYSTEM", "USER_INPUT", "SESSION", "TOOL", "SKILL"],
            "skills": {},
        },
        "skills": {
            "bindings": [
                {
                    "skill_id": str(version.skill_id),
                    "skill_version_id": str(version.id),
                    "enabled": True,
                }
            ],
            "snapshots": [version.snapshot()],
        },
    }


def request(runtime, policy=None):
    context = new_execution_context()
    context.skill_context = runtime.contributions()
    return ContextAssemblyRequest(
        messages=[
            SystemMessage(content="Agent rules"),
            HumanMessage(content="Review this invoice"),
        ],
        model_invocation_id=uuid4(),
        agent_run_id=uuid4(),
        project_id=uuid4(),
        provider="openai",
        model="test",
        runtime_context=context,
        policy=policy
        or ContextPolicyV1(
            allowed_sources=["SYSTEM", "USER_INPUT", "SESSION", "SKILL", "TOOL"],
            skills=SkillContextPolicy(),
        ),
    )


@pytest.mark.parametrize(
    "path",
    [
        "../secret.txt",
        "/etc/passwd",
        "references/../secret.md",
        "references//x.md",
        "scripts/run.py",
        "assets/run.sh",
        "references\\x.md",
    ],
)
def test_import_rejects_unsupported_resource_paths(path):
    with pytest.raises(ValidationError):
        parse_skill_package(
            ImportSkillInput(
                version="1.0.0",
                skill_md="---\nname: example\ndescription: Test\n---\nProcedure",
                resources={path: "text"},
            )
        )


@pytest.mark.parametrize(
    "manifest",
    [
        "no frontmatter",
        "---\nname: Bad Name\ndescription: Test\n---\nProcedure",
        "---\nname: example\ndescription: &a test\nlicense: *a\n---\nProcedure",
        "---\nname: example\ndescription: test\n---\n",
        "---\nname: example\ndescription: test\n---\nhello\x00",
    ],
)
def test_import_rejects_invalid_packages(manifest):
    with pytest.raises(ValidationError):
        parse_skill_package(ImportSkillInput(version="1.0.0", skill_md=manifest))


async def test_server_resolves_pins_and_replaces_forged_snapshot_bytes(version):
    config = runtime_config(version)
    config["skills"]["snapshots"] = [{"package": {"instructions": "forged"}}]
    repo = SimpleNamespace(get_version=AsyncMock(return_value=version))
    frozen = await freeze_skill_bindings(
        repo, project_id=version.project_id, runtime_config=config
    )
    assert frozen_enabled_skills(frozen, version.project_id) == [version.snapshot()]
    repo.get_version.assert_awaited_once_with(version.project_id, version.id)
    assert config["skills"]["snapshots"][0]["package"]["instructions"] == "forged"


async def test_cross_project_version_is_rejected(version):
    repo = SimpleNamespace(get_version=AsyncMock(return_value=None))
    with pytest.raises(ValidationError, match="Project"):
        await freeze_skill_bindings(
            repo, project_id=uuid4(), runtime_config=runtime_config(version)
        )
    with pytest.raises(ValidationError, match="frozen"):
        frozen_enabled_skills(runtime_config(version), uuid4())


async def test_one_fixed_version_per_skill_and_integrity(version):
    config = runtime_config(version)
    config["skills"]["bindings"] *= 2
    repo = SimpleNamespace(get_version=AsyncMock(return_value=version))
    with pytest.raises(ValidationError, match="one version"):
        await freeze_skill_bindings(
            repo, project_id=version.project_id, runtime_config=config
        )
    corrupt = replace(version, package_hash="wrong")
    with pytest.raises(ValidationError, match="integrity"):
        await freeze_skill_bindings(
            SimpleNamespace(get_version=AsyncMock(return_value=corrupt)),
            project_id=version.project_id,
            runtime_config=runtime_config(version),
        )


async def test_enabled_skills_require_compatible_context_manager(version):
    config = runtime_config(version)
    config["context_assembler"] = {"name": "adaptive"}
    with pytest.raises(ValidationError, match="Standard Context Manager"):
        await freeze_skill_bindings(
            None, project_id=version.project_id, runtime_config=config
        )
    config["skills"]["bindings"] = []
    assert (
        await freeze_skill_bindings(
            None, project_id=version.project_id, runtime_config=config
        )
    )["skills"]["snapshots"] == []


async def test_catalog_versions_are_project_scoped_and_keep_name(version):
    repo = SimpleNamespace(
        get_skill=AsyncMock(return_value=None),
        get_version=AsyncMock(return_value=None),
        create_version=AsyncMock(),
    )
    catalog = SkillCatalog(repo)
    with pytest.raises(NotFoundError):
        await catalog.get_version(uuid4(), version.id)
    with pytest.raises(NotFoundError):
        await catalog.add_version(
            uuid4(),
            version.skill_id,
            ImportSkillInput(version="2.0.0", skill_md=version.package["skill_md"]),
        )
    repo.get_skill.return_value = SimpleNamespace(
        name="another-skill", id=version.skill_id
    )
    with pytest.raises(ValidationError, match="preserve its name"):
        await catalog.add_version(
            version.project_id,
            version.skill_id,
            ImportSkillInput(version="2.0.0", skill_md=version.package["skill_md"]),
        )
    repo.create_version.assert_not_called()


def test_progressive_loading_deduplication_provenance_and_run_isolation(version):
    runtime = SkillRuntime([version.snapshot()], SkillContextPolicy(), set())
    assert version.package["instructions"] not in str(runtime.contributions())
    assert not runtime.execute(
        "skills_search", {"query": "invoice"}, tool_call_id="search"
    )["success"]
    activation = runtime.execute(
        "skills_activate",
        {"skill_version_id": str(version.id)},
        tool_call_id="activate",
    )
    assert activation["success"]
    assert version.package["instructions"] not in str(activation)
    assert runtime.execute(
        "skills_activate", {"skill_version_id": str(version.id)}, tool_call_id="again"
    )["output"]["already_active"]
    assert runtime.execute(
        "skills_read_resource",
        {"skill_version_id": str(version.id), "path": "references/checklist.md"},
        tool_call_id="read",
    )["success"]
    assembled = build_context_assembler("standard").assemble(
        request(runtime)
    )
    assert (
        sum(
            version.package["instructions"] in str(message.content)
            for message in assembled.messages
        )
        == 1
    )
    assert assembled.messages[-1].content == "Review this invoice"
    contributions = [
        item for item in assembled.snapshot.contributions if item.source_type == "SKILL"
    ]
    assert len(contributions) == 3
    assert assembled.snapshot.manifest["skills"]["active_versions"] == [str(version.id)]
    assert not any("content" in item.metadata for item in contributions)
    fresh = SkillRuntime([version.snapshot()], SkillContextPolicy(), set())
    assert len(fresh.contributions()) == 1
    assert not fresh.execute(
        "skills_read_resource",
        {"skill_version_id": str(version.id), "path": "references/checklist.md"},
        tool_call_id="read",
    )["success"]


def test_activation_enforces_tools_and_installed_versions(version):
    changed = deepcopy(version.snapshot())
    changed["package"]["required_tools"] = ["approve_invoice"]
    runtime = SkillRuntime([changed], SkillContextPolicy(), set())
    assert not runtime.execute(
        "skills_activate", {"skill_version_id": str(version.id)}, tool_call_id="call"
    )["success"]
    assert not runtime.execute(
        "skills_activate", {"skill_version_id": str(uuid4())}, tool_call_id="call"
    )["success"]
    assert len(runtime.contributions()) == 1


def test_budget_declines_new_content_without_truncating_active_instructions(version):
    snapshot = deepcopy(version.snapshot())
    snapshot["package"]["instructions"] += " Full procedure." * 40
    runtime = SkillRuntime([snapshot], SkillContextPolicy(max_units=8000), set())
    runtime.execute(
        "skills_activate", {"skill_version_id": str(version.id)}, tool_call_id="a"
    )
    exact_units = sum(
        estimate_input_units(skill_contribution_content(item))
        for item in runtime.contributions()
    )
    runtime = SkillRuntime([snapshot], SkillContextPolicy(max_units=exact_units), set())
    assert runtime.execute(
        "skills_activate", {"skill_version_id": str(version.id)}, tool_call_id="a"
    )["success"]
    assert not runtime.execute(
        "skills_read_resource",
        {"skill_version_id": str(version.id), "path": "references/checklist.md"},
        tool_call_id="r",
    )["success"]
    assembled = build_context_assembler("standard").assemble(
        request(
            runtime,
            ContextPolicyV1(
                allowed_sources=["SYSTEM", "USER_INPUT", "TOOL", "SKILL"],
                skills=SkillContextPolicy(max_units=exact_units),
            ),
        )
    )
    assert any(
        version.package["instructions"] in str(message.content)
        for message in assembled.messages
    )
    policy = ContextPolicyV1(
        allowed_sources=["SYSTEM", "USER_INPUT", "SKILL"],
        skills=SkillContextPolicy(),
        budget={"max_input_units": 256},
    )
    oversized = request(runtime, policy)
    oversized = replace(
        oversized,
        messages=[SystemMessage(content="x" * 2000), HumanMessage(content="Input")],
    )
    with pytest.raises(ContextBudgetExceeded):
        build_context_assembler("standard").assemble(oversized)


def test_standard_context_is_stable_without_active_skills(version):
    policy = ContextPolicyV1()
    assert "skills" not in policy.model_dump(mode="json")
    context_request = request(
        SkillRuntime([version.snapshot()], SkillContextPolicy(), set()), policy
    )
    context_request.runtime_context.skill_context = None
    original = assemble_context(
        messages=context_request.messages,
        model_invocation_id=context_request.model_invocation_id,
        agent_run_id=context_request.agent_run_id,
        project_id=context_request.project_id,
        provider=context_request.provider,
        model=context_request.model,
        runtime_context=context_request.runtime_context,
        policy=context_request.policy,
    )
    updated = build_context_assembler("standard").assemble(context_request)
    assert original.messages == updated.messages
    assert {
        key: value
        for key, value in original.snapshot.manifest.items()
        if key != "snapshot_id"
    } == {
        key: value
        for key, value in updated.snapshot.manifest.items()
        if key != "snapshot_id"
    }


async def test_real_model_loop_activates_visible_skill_only_when_requested(version):
    context = new_execution_context()
    context.project_id = version.project_id
    context.agent_id = uuid4()
    context.run_id = uuid4()
    config = runtime_config(version)
    context.context_policy = resolve_context_policy(config).model_dump(mode="json")
    observed = []
    normal_skill_tools = {
        "skills_activate",
        "skills_read_resource",
    }

    class BoundModel:
        def __init__(self, owner, tool_names):
            self.owner = owner
            self.tool_names = tool_names

        async def ainvoke(self, messages, **kwargs):
            return await self.owner.invoke_bound(self.tool_names, messages)

    class Model:
        def bind_tools(self, tools, **kwargs):
            names = {item["function"]["name"] for item in tools}
            assert kwargs.get("tool_choice") == "auto"
            assert names == normal_skill_tools
            return BoundModel(self, names)

        async def invoke_bound(self, tool_names, messages):
            observed.append((tool_names, messages))
            materialized = version.package["instructions"] in str(messages)
            if not materialized:
                return AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "skills_activate",
                            "args": {"skill_version_id": str(version.id)},
                            "id": "activate",
                            "type": "tool_call",
                        }
                    ],
                )
            return AIMessage(content="Invoice reviewed.")

    model = Model()
    factory = SimpleNamespace(create_chat_model=lambda **kwargs: model)
    agent = SimpleNamespace(
        id=context.agent_id,
        project_id=version.project_id,
        provider="openai",
        model="test",
        temperature=0.2,
        max_output_tokens=1000,
        settings={"runtime_config": config},
    )
    external_tool = AsyncMock()
    configure_skill_runtime(frozen_enabled_skills, SkillRuntime)
    token = current_execution.set(context)
    try:
        result = await run_instrumented_execution(
            llm_factory=factory,
            execute_single_tool=external_tool,
            clean_json_answer=lambda answer: answer,
            agent=agent,
            api_key="test",
            base_url=None,
            response_format={},
            json_enabled=False,
            has_tools=False,
            agent_tools=[],
            tool_name_to_id={},
            messages=[
                SystemMessage(content="Review invoices"),
                HumanMessage(content="Please review"),
            ],
            context_assembler=build_context_assembler("standard"),
        )
        assert [tool_names for tool_names, _messages in observed] == [
            normal_skill_tools,
            normal_skill_tools,
        ]
        assert [call.tool_name for call in result.tool_calls] == ["skills_activate"]
        assert result.result.content == "Invoice reviewed."
        external_tool.assert_not_called()
    finally:
        current_execution.reset(token)


async def test_agent_update_freezes_version_before_persistence(version):
    from modules.agent.application.dtos.ai_dtos import UpdateAgentInput
    from modules.agent.application.use_cases.ai_agent_cases import UpdateAgentUseCase
    from modules.agent.domain.entities import Agent

    agent = Agent(project_id=version.project_id, name="Reviewer", model="test")
    agent_repo = SimpleNamespace(
        get_by_id=AsyncMock(return_value=agent),
        update=AsyncMock(side_effect=lambda value: value),
    )
    catalog = SimpleNamespace(get_version=AsyncMock(return_value=version))
    incoming = runtime_config(version)
    incoming["skills"]["snapshots"] = []
    use_case = UpdateAgentUseCase(
        agent_repo, AsyncMock(), AsyncMock(), skill_repo=catalog
    )
    result = await use_case.execute(
        agent.id, UpdateAgentInput(settings={"runtime_config": incoming})
    )
    assert frozen_enabled_skills(
        result.settings["runtime_config"], agent.project_id
    ) == [version.snapshot()]
    assert agent_repo.update.call_args.args[0].settings["runtime_config"]["skills"][
        "snapshots"
    ] == [version.snapshot()]


def test_release_identity_changes_with_skill_version_and_restores_exact_snapshot(
    version,
):
    from modules.agent.domain.entities import AgentRelease
    from modules.agent.domain.release_snapshot import release_snapshot_hash
    from modules.agent.infra.execution.frozen_snapshot_runtime import (
        FrozenSnapshotStructuredOutputRuntime,
    )
    from modules.agent.domain.entities import Agent

    release = AgentRelease(
        project_id=version.project_id, runtime_config=runtime_config(version)
    )
    original_hash = release_snapshot_hash(release)
    changed = deepcopy(release)
    changed.runtime_config["skills"]["bindings"][0]["enabled"] = False
    assert release_snapshot_hash(changed) != original_hash
    runtime = FrozenSnapshotStructuredOutputRuntime.__new__(
        FrozenSnapshotStructuredOutputRuntime
    )
    agent = Agent(
        project_id=version.project_id,
        settings={"runtime_config": changed.runtime_config},
    )
    restored = runtime._apply_snapshot_override(
        agent, {"runtime_config": release.runtime_config}
    )
    assert frozen_enabled_skills(
        restored.settings["runtime_config"], version.project_id
    ) == [version.snapshot()]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "operation", ["skills_search", "skills_activate", "skills_read_resource"]
)
async def test_skill_instrumentation_labels_activity_without_changing_transport(
    operation, monkeypatch
):
    from modules.agent.infra.execution import (
        execution_instrumentation as instrumentation,
    )

    activity = AsyncMock()
    event = AsyncMock()
    monkeypatch.setattr(instrumentation, "emit_agent_activity", activity)
    monkeypatch.setattr(instrumentation, "emit_runtime_event", event)
    info, message, payload = await instrumentation.execute_tool_call(
        execute=AsyncMock(
            return_value={
                "success": True,
                "output": {"name": "invoice-review", "version": "1.0.0"},
            }
        ),
        tool_call={"id": "skill-call", "name": operation, "args": {}},
        resolved_tool_id="internal-skill-operation",
    )
    assert len(activity.call_args_list) == 2
    for call in activity.call_args_list:
        assert "Skill" in call.kwargs["message"]
        assert "tool" not in call.kwargs["message"].lower()
    assert [call.args[0] for call in event.call_args_list] == [
        "tool_call_started",
        "tool_call_completed",
    ]
    assert info.tool_name == operation
    assert message.tool_call_id == "skill-call"
    assert payload["success"] is True
    assert payload["skill_name"] == "invoice-review"
    assert payload["skill_version"] == "1.0.0"
