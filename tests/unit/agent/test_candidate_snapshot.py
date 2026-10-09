from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.agent.application.dtos.ai_dtos import CreateReleaseInput
from modules.agent.application.use_cases.create_candidate_snapshot import CreateCandidateSnapshot
from modules.agent.application.use_cases.knowledge_safe_release_lifecycle import KnowledgeSafeCreateReleaseUseCase
from modules.agent.domain.entities import Agent
from modules.agent.domain.enums import AgentStatus, Provider
from shared.contracts.errors import ConflictError


@pytest.mark.asyncio
async def test_candidate_freezes_exact_input_without_reading_or_changing_singleton_draft():
    agent = Agent(project_id=uuid4(), name="Current Root", provider=Provider.custom,
        model="current-model", system_prompt="Unrelated pending work", status=AgentStatus.active)
    before = deepcopy(agent)
    rows = {}

    async def save(snapshot):
        rows[snapshot.id] = snapshot
        return snapshot

    releases = SimpleNamespace(get_by_id=AsyncMock(side_effect=lambda identifier: rows.get(identifier)),
        save=AsyncMock(side_effect=save), list_by_status=AsyncMock(side_effect=AssertionError("Candidate read mutable Draft")))
    knowledge = SimpleNamespace(validate=AsyncMock())
    preparation = KnowledgeSafeCreateReleaseUseCase(releases, knowledge, SimpleNamespace())
    use_case = CreateCandidateSnapshot(agents=SimpleNamespace(get_by_id=AsyncMock(return_value=agent)), releases=releases, preparation=preparation)
    incoming = CreateReleaseInput(project_id=agent.project_id, agent_id=agent.id, version="auto",
        name="Historical Hotfix", system_prompt="Exact sealed instructions", provider="custom",
        model="sealed-model", session_mode="stateless", agent_status="active", runtime_config={"execution_strategy": "standard"})
    original = incoming.model_dump()
    identifier = uuid4()
    candidate = await use_case.execute(incoming, snapshot_id=identifier)
    assert candidate.id == identifier and candidate.snapshot_kind == "candidate"
    assert candidate.status.value == "archived"
    assert candidate.system_prompt == "Exact sealed instructions" and candidate.model == "sealed-model"
    assert agent == before and incoming.model_dump() == original
    assert releases.list_by_status.await_count == 0 and releases.save.await_count == 1
    assert await use_case.execute(incoming, snapshot_id=identifier) is candidate
    assert releases.save.await_count == 1
    changed = incoming.model_copy(update={"system_prompt": "Different content"})
    with pytest.raises(ConflictError, match="SNAPSHOT_CONFLICT"):
        await use_case.execute(changed, snapshot_id=identifier)
    assert rows[identifier].system_prompt == "Exact sealed instructions"
    assert releases.save.await_count == 1 and agent == before
