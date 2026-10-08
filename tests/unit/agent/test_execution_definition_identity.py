from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import AsyncMock

import pytest

from modules.agent.domain.execution_definition import (
    AGENT_EXECUTION_FIELDS,
    AgentExecutionSnapshot,
    hash_agent_execution_snapshot,
)
from modules.agent.domain.release_snapshot import (
    release_snapshot_hash,
    release_snapshots_equal,
)


@pytest.mark.parametrize(
    "field",
    [
        "external_context_contract",
        "model_spec_snapshot",
        "model_spec_hash",
        "fallback_model_spec_snapshot",
        "fallback_model_spec_hash",
    ],
)
def test_v2_identity_covers_previously_omitted_executable_fields(field):
    source = SimpleNamespace(name="support", runtime_config={})
    changed = deepcopy(source)
    setattr(
        changed,
        field,
        {"different": True}
        if field.endswith("snapshot") or field.endswith("contract")
        else "different",
    )
    # Legacy receipt material stays stable; new equivalence must not collapse it.
    assert release_snapshot_hash(source) == release_snapshot_hash(changed)
    assert hash_agent_execution_snapshot(source) != hash_agent_execution_snapshot(
        changed
    )
    assert not release_snapshots_equal(source, changed)


def test_snapshot_is_versioned_and_preserves_every_execution_field():
    source = {field: f"value-{field}" for field in AGENT_EXECUTION_FIELDS}
    source["collection_ids"] = ["b", "a"]
    source["runtime_config"] = {"execution_strategy": "standard"}
    snapshot = AgentExecutionSnapshot.from_source(source)
    assert snapshot.schema_version == "2"
    assert set(snapshot.definition.fields) == set(AGENT_EXECUTION_FIELDS)
    assert snapshot.definition.fields["collection_ids"] == ["a", "b"]
    assert source["collection_ids"] == ["b", "a"]


def test_dictionary_order_and_collection_order_do_not_change_identity():
    left = {"collection_ids": ["a", "b"], "runtime_config": {"x": 1, "y": 2}}
    right = {"runtime_config": {"y": 2, "x": 1}, "collection_ids": ["b", "a"]}
    assert hash_agent_execution_snapshot(left) == hash_agent_execution_snapshot(right)


def test_nonfinite_executable_numbers_are_not_hashable():
    with pytest.raises(ValueError):
        hash_agent_execution_snapshot({"temperature": float("nan")})


def test_runtime_projection_preserves_model_specs_lineage_and_risk():
    from modules.agent.application.execution_snapshot import (
        build_agent_execution_snapshot,
        apply_agent_execution_snapshot,
    )
    from modules.agent.domain.entities import Agent, AgentRelease
    from modules.agent.domain.enums import Provider

    project, agent_id = uuid4(), uuid4()
    release = AgentRelease(
        project_id=project,
        agent_id=agent_id,
        version="draft",
        provider="openai",
        model="fake",
        session_mode="stateless",
    )
    release.model_spec_snapshot = {"frozen": "primary"}
    release.model_spec_hash = "primary-hash"
    release.fallback_model_spec_snapshot = {"frozen": "fallback"}
    release.fallback_model_spec_hash = "fallback-hash"
    release.prompt_version_id, release.contract_version_id = uuid4(), uuid4()
    release.model_config_version_id = uuid4()
    release.risk_score = 3
    snapshot = build_agent_execution_snapshot(release)
    assert set(AGENT_EXECUTION_FIELDS) <= set(snapshot)
    target = Agent(
        project_id=project, name="target", provider=Provider.openai, model="fake"
    )
    apply_agent_execution_snapshot(target, snapshot)
    projected = build_agent_execution_snapshot(target)
    for field in (
        "model_spec_snapshot",
        "model_spec_hash",
        "fallback_model_spec_snapshot",
        "fallback_model_spec_hash",
        "prompt_version_id",
        "contract_version_id",
        "model_config_version_id",
        "risk_score",
    ):
        assert projected[field] == snapshot[field]


@pytest.mark.asyncio
async def test_preparatory_agent_can_be_created_inactive_and_cannot_run():
    from modules.agent.application.dtos.ai_dtos import CreateAgentInput
    from modules.agent.application.execution_snapshot import (
        AgentExecutionSnapshotResolver,
    )
    from modules.agent.application.use_cases.ai_agent_cases import CreateAgentUseCase
    from modules.agent.domain.enums import AgentStatus
    from shared.contracts.errors import ValidationError

    async def save(agent):
        return agent

    repository = SimpleNamespace(save=save)
    credentials = SimpleNamespace(get_by_id=AsyncMock())
    outbox = SimpleNamespace(write=AsyncMock())
    agent = await CreateAgentUseCase(repository, credentials, outbox).execute(
        CreateAgentInput(
            project_id=uuid4(),
            name="preparing",
            model="fake",
            status=AgentStatus.inactive,
        )
    )
    assert agent.status == AgentStatus.inactive
    with pytest.raises(ValidationError):
        AgentExecutionSnapshotResolver().resolve_loaded(
            project_id=agent.project_id,
            agent=agent,
            environment="draft",
            release=None,
            allow_legacy_draft=True,
        )
