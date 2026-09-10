from copy import deepcopy
import importlib.util
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
from pydantic import ValidationError as SchemaError
import pytest

from modules.agent.application.dtos.ai_dtos import CreateAgentInput, CreateReleaseInput, UpdateAgentInput
from modules.agent.application.dtos.behavior_dtos import canonicalize_behavior_spec
from modules.agent.application.execution_snapshot import apply_agent_execution_snapshot, build_agent_execution_snapshot
from modules.agent.application.system_instruction_assembler import assemble_system_instructions
from modules.agent.application.use_cases.ai_agent_cases import CreateAgentUseCase, UpdateAgentUseCase
from modules.agent.application.use_cases.auto_compatible_release_lifecycle import AutoCompatibleReleaseLifecycleUseCase
from modules.agent.application.use_cases.release_lifecycle_use_cases_v2 import AutoCreateReleaseUseCase
from modules.agent.application.use_cases.rerun_agent_run import _draft_snapshot_override
from modules.agent.application.use_cases.session_mode_compatible_release import SessionModeCompatibleCreateReleaseUseCase
from modules.agent.domain.entities import Agent, AgentRelease
from modules.agent.domain.enums import ReleaseStatus
from modules.agent.domain.release_snapshot import canonical_release_snapshot, release_snapshot_hash
from modules.agent.infra.database.mappers import agent_entity_to_model, agent_model_to_entity, agent_release_entity_to_model, agent_release_model_to_entity
from modules.agent.infra.execution.frozen_snapshot_runtime import FrozenSnapshotStructuredOutputRuntime
from modules.agent.infra.execution.runtime_preparation import build_execution_snapshot
from modules.agent.presentation.mappers import agent_to_response, release_to_response
from modules.network.domain.release_contracts import agent_snapshot_payload
from modules.network.infra.services.session_mode_binding_service import NetworkApplicationService
from shared.contracts.errors import ConflictError


def behavior(**overrides):
    return canonicalize_behavior_spec({"objective": "Resolve the request", **overrides})


def agent_repository(agent):
    return SimpleNamespace(
        get_by_id=AsyncMock(return_value=agent),
        save=AsyncMock(side_effect=lambda item: item),
        update=AsyncMock(side_effect=lambda item: item),
    )


class Releases:
    def __init__(self):
        self.items = {}

    async def save(self, item):
        self.items[item.id] = item
        return item

    async def get_by_id(self, item_id):
        return self.items.get(item_id)

    async def list_by_status(self, agent_id, status):
        return [item for item in self.items.values() if item.agent_id == agent_id and item.status == status]

    async def list_by_agent(self, agent_id):
        return [item for item in self.items.values() if item.agent_id == agent_id]


def test_assembler_has_deterministic_identity_section_order_and_list_order():
    spec = behavior(responsibilities=[" Second ", "", "First"], allowed_behaviors=["Ask"], disallowed_behaviors=["Invent"], operating_instructions="Inspect evidence", response_guidelines="Be concise", additional_instructions="  Keep this exact.\n")
    result = assemble_system_instructions("Reviewer", "Review invoices", spec)
    assert result == (
        "[AGENT IDENTITY]\n\nName: Reviewer\nDescription: Review invoices\n\n"
        "[OBJECTIVE]\n\nResolve the request\n\n"
        "[RESPONSIBILITIES]\n\n- Second\n- First\n\n"
        "[ALLOWED BEHAVIORS]\n\n- Ask\n\n"
        "[DISALLOWED BEHAVIORS]\n\n- Invent\n\n"
        "[OPERATING INSTRUCTIONS]\n\nInspect evidence\n\n"
        "[RESPONSE GUIDELINES]\n\nBe concise\n\n"
        "[ADDITIONAL INSTRUCTIONS]\n\n  Keep this exact.\n"
    )
    assert assemble_system_instructions("Reviewer", "Review invoices", deepcopy(spec)) == result


def test_empty_sections_are_omitted_and_canonicalization_does_not_mutate_input():
    raw = {"responsibilities": [" a ", " ", "b", "a"]}
    assert canonicalize_behavior_spec(raw)["responsibilities"] == ["a", "b", "a"]
    assert raw["responsibilities"] == [" a ", " ", "b", "a"]
    assert assemble_system_instructions(None, None, {}) == ""
    assert assemble_system_instructions("Agent", "", {"objective": " "}) == "[AGENT IDENTITY]\n\nName: Agent"


@pytest.mark.parametrize("value", [
    {"schema_version": 2}, {"schema_version": True}, {"schema_version": "1"},
    {"objective": 1}, {"responsibilities": "one"}, {"responsibilities": [1]},
    {"allowed_behaviors": None}, {"identity": "duplicate"},
])
def test_invalid_behavior_is_rejected_at_the_input_boundary(value):
    with pytest.raises(SchemaError):
        CreateAgentInput(project_id=uuid4(), name="A", model="test", behavior_spec=value)
    with pytest.raises(SchemaError):
        CreateReleaseInput(project_id=uuid4(), agent_id=uuid4(), version="draft", behavior_spec=value)


@pytest.mark.asyncio
async def test_create_and_identity_update_compile_on_the_backend():
    repo = agent_repository(None)
    credentials = SimpleNamespace(get_by_id=AsyncMock())
    outbox = SimpleNamespace(write=AsyncMock())
    created = await CreateAgentUseCase(repo, credentials, outbox).execute(CreateAgentInput(
        project_id=uuid4(), name="Reviewer", description="Invoice specialist", model="test",
        behavior_spec=behavior(), system_prompt="Untrusted client compilation",
    ))
    assert "Name: Reviewer" in created.system_prompt
    assert "Description: Invoice specialist" in created.system_prompt
    assert "Untrusted" not in created.system_prompt
    repo.get_by_id.return_value = created
    updated = await UpdateAgentUseCase(repo, credentials, outbox).execute(created.id, UpdateAgentInput(name="Auditor"))
    assert "Name: Auditor" in updated.system_prompt
    assert updated.behavior_spec == created.behavior_spec
    assert agent_to_response(created).behavior_spec == created.behavior_spec
    with pytest.raises(ConflictError, match="behavior_spec"):
        await UpdateAgentUseCase(repo, credentials, outbox).execute(created.id, UpdateAgentInput(system_prompt="overwrite"))


@pytest.mark.asyncio
async def test_save_draft_compiles_and_synchronizes_the_agent_projection():
    agent = Agent(name="Legacy", description="Role", model="test", system_prompt="  legacy\n")
    releases = Releases()
    repo = agent_repository(agent)
    save = SessionModeCompatibleCreateReleaseUseCase(AutoCreateReleaseUseCase(releases), repo)
    draft = await save.execute(CreateReleaseInput(
        project_id=agent.project_id, agent_id=agent.id, version="draft",
        behavior_spec=behavior(additional_instructions=agent.system_prompt),
    ))
    assert draft.behavior_spec == agent.behavior_spec
    assert draft.system_prompt == agent.system_prompt
    assert draft.behavior_spec["additional_instructions"] == "  legacy\n"
    assert draft.system_prompt.endswith("  legacy\n")
    draft = await save.execute(CreateReleaseInput(project_id=agent.project_id, agent_id=agent.id, version="draft", name="Renamed"))
    assert "Name: Renamed" in draft.system_prompt
    assert draft.behavior_spec["objective"] == "Resolve the request"


@pytest.mark.asyncio
async def test_legacy_draft_save_does_not_reinterpret_prompt():
    agent = Agent(name="Legacy", model="test", system_prompt="  historical instructions\n")
    save = SessionModeCompatibleCreateReleaseUseCase(AutoCreateReleaseUseCase(Releases()), agent_repository(agent))
    draft = await save.execute(CreateReleaseInput(project_id=agent.project_id, agent_id=agent.id, version="draft"))
    assert draft.behavior_spec is None
    assert draft.system_prompt == "  historical instructions\n"


@pytest.mark.asyncio
@pytest.mark.parametrize("legacy", [False, True])
async def test_promotion_and_reactivation_freeze_both_representations_without_recompiling(legacy, monkeypatch):
    releases = Releases()
    draft = AgentRelease(name="Saved", project_id=uuid4(), agent_id=uuid4(), version="draft", provider="openai", model="test", session_mode="stateful", behavior_spec=None if legacy else behavior(), system_prompt="exact materialized instructions")
    draft.snapshot_kind = "draft"
    await releases.save(draft)
    lifecycle = AutoCompatibleReleaseLifecycleUseCase(releases)
    def must_not_compile(*args):
        raise AssertionError("Historical instructions must not be recompiled")
    monkeypatch.setattr("modules.agent.application.use_cases.release_lifecycle_use_cases_v2.assemble_system_instructions", must_not_compile)
    staging = await lifecycle.execute(draft.agent_id, draft.id, target_status="staging")
    first = await lifecycle.execute(draft.agent_id, staging.id, target_status="production")
    expected = deepcopy(first.behavior_spec)
    if draft.behavior_spec:
        draft.behavior_spec["objective"] = "Changed later"
    draft.system_prompt = "new instructions"
    staging2 = await lifecycle.execute(draft.agent_id, draft.id, target_status="staging")
    await lifecycle.execute(draft.agent_id, staging2.id, target_status="production")
    restored = await lifecycle.execute(draft.agent_id, first.id, target_status="production")
    assert restored.id == first.id
    assert restored.behavior_spec == expected
    assert restored.system_prompt == "exact materialized instructions"
    assert release_to_response(await releases.get_by_id(restored.id)).behavior_spec == expected


def test_database_roundtrip_preserves_behavior_and_null_legacy():
    for spec in [None, behavior(responsibilities=["a", "b"])]:
        agent = Agent(name="A", model="test", behavior_spec=spec, system_prompt="exact")
        assert agent_model_to_entity(agent_entity_to_model(agent)).behavior_spec == spec
        release = AgentRelease(version="draft", session_mode="stateful", behavior_spec=spec, system_prompt="exact")
        restored = agent_release_model_to_entity(agent_release_entity_to_model(release))
        assert restored.behavior_spec == spec
        assert restored.system_prompt == "exact"


def test_legacy_hashes_remain_compatible_and_behavior_affects_snapshot_hash():
    release = AgentRelease()
    assert "behavior_spec" not in canonical_release_snapshot(release)
    assert "behavior_spec" not in agent_snapshot_payload(release)
    legacy_hash = release_snapshot_hash(release)
    release.behavior_spec = behavior()
    first_hash = release_snapshot_hash(release)
    assert first_hash != legacy_hash
    release.behavior_spec["responsibilities"] = ["Second", "First"]
    assert release_snapshot_hash(release) != first_hash


def test_unsaved_behavior_compiles_but_rerun_keeps_original_materialization():
    runtime = object.__new__(FrozenSnapshotStructuredOutputRuntime)
    agent = Agent(name="Old", description="Old role", model="test", behavior_spec=behavior(), system_prompt="old")
    runtime._apply_snapshot_override(agent, {"name": "Unsaved", "description": "New role", "behavior_spec": behavior(objective="Unsaved goal")})
    assert "Name: Unsaved" in agent.system_prompt
    assert "Unsaved goal" in agent.system_prompt
    run_snapshot = build_execution_snapshot(agent=agent, tools=[], rag_binding=None, release_id=None, release_version=None, tool_to_snapshot=lambda tool: {})
    historical_prompt = run_snapshot["agent"]["system_prompt"]
    agent.behavior_spec["objective"] = "Mutated after run"
    assert run_snapshot["agent"]["behavior_spec"]["objective"] == "Unsaved goal"
    override = _draft_snapshot_override(run_snapshot)
    override["system_prompt"] = "historical compiler output"
    runtime._apply_snapshot_override(agent, override)
    assert agent.system_prompt == "historical compiler output"
    assert agent.behavior_spec["objective"] == "Unsaved goal"
    assert historical_prompt != agent.system_prompt
    runtime._apply_snapshot_override(agent, {"temperature": 0.3})
    assert agent.behavior_spec["objective"] == "Unsaved goal"
    assert agent.system_prompt == "historical compiler output"
    assert agent.temperature == 0.3
    runtime._apply_snapshot_override(agent, {"system_prompt": "legacy"})
    assert agent.behavior_spec is None
    assert agent.system_prompt == "legacy"


@pytest.mark.asyncio
@pytest.mark.parametrize("environment", ["staging", "production"])
async def test_network_freezes_the_pinned_release_behavior_instead_of_current_agent(environment):
    agent = Agent(name="Current", model="test", behavior_spec=behavior(objective="current"), system_prompt="current")
    release = AgentRelease(project_id=agent.project_id, agent_id=agent.id, name="Pinned", provider="openai", model="test", session_mode="stateful", version="1.0.0", status=ReleaseStatus.released, behavior_spec=behavior(objective="pinned"), system_prompt="pinned compiler output")
    release.snapshot_kind = "release"
    def rows(items):
        return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: items))
    session = SimpleNamespace(execute=AsyncMock(side_effect=[rows([release]), rows([agent])]))
    bindings = {"node": {"agent_id": str(agent.id), "release_id": str(release.id)}}
    await NetworkApplicationService._freeze_bindings(session, project_id=agent.project_id, bindings=bindings, environment=environment)
    snapshot = bindings["node"]["snapshot_override"]
    assert snapshot["behavior_spec"]["objective"] == "pinned"
    assert snapshot["system_prompt"] == "pinned compiler output"
    apply_agent_execution_snapshot(agent, snapshot)
    assert agent.name == "Pinned"
    assert agent.behavior_spec == release.behavior_spec
    release.behavior_spec = None
    release.system_prompt = "legacy release"
    apply_agent_execution_snapshot(agent, build_agent_execution_snapshot(release))
    assert agent.behavior_spec is None
    assert agent.system_prompt == "legacy release"


def test_behavior_migration_adds_nullable_columns_without_data_rewrites():
    path = Path(__file__).resolve().parents[3] / "packages/woobe-core/migrations/versions/0065_agent_behavior_spec.py"
    spec = importlib.util.spec_from_file_location("behavior_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    output = StringIO()
    context = MigrationContext.configure(dialect_name="postgresql", opts={"as_sql": True, "output_buffer": output})
    with Operations.context(context):
        module.upgrade()
    statements = output.getvalue()
    assert "ALTER TABLE agent.agents ADD COLUMN behavior_spec JSONB" in statements
    assert "ALTER TABLE agent.agent_releases ADD COLUMN behavior_spec JSONB" in statements
    assert "NOT NULL" not in statements
    assert "UPDATE" not in statements
    assert "system_prompt" not in statements
