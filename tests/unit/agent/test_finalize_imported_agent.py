from uuid import uuid4

import pytest

from modules.agent.application.dtos.ai_dtos import CreateReleaseInput
from modules.agent.application.execution_snapshot import (
    apply_agent_execution_snapshot,
    build_agent_execution_snapshot,
)
from modules.agent.application.use_cases.finalize_imported_agent import (
    FinalizeImportedAgentUseCase,
)
from modules.agent.domain.entities import Agent, AgentRelease
from modules.agent.domain.enums import AgentStatus, Provider, SessionMode
from shared.contracts.errors import ConflictError


def scenario(*, mismatch=False):
    agent = Agent(
        project_id=uuid4(),
        name="Support",
        provider=Provider.openai_compatible,
        model="fake",
        status=AgentStatus.inactive,
        session_mode=SessionMode.stateless,
    )
    events = []

    class Agents:
        async def get_by_id(self, identifier):
            return agent if identifier == agent.id else None

    class Draft:
        async def execute(self, definition, *, change_kind):
            assert agent.status == AgentStatus.inactive
            events.append("save_complete_draft")
            release = AgentRelease(
                project_id=agent.project_id,
                agent_id=agent.id,
                version="1.0.0",
                name="Support",
                description="Portable",
                provider="openai_compatible",
                model="fake",
                system_prompt="Help",
                session_mode="stateless",
                agent_status=definition.agent_status,
                prompt_version_id=uuid4(),
                contract_version_id=uuid4(),
                output_schema={"type": "object"},
                runtime_config={"execution": {"strategy": "standard"}},
            )
            apply_agent_execution_snapshot(
                agent, build_agent_execution_snapshot(release)
            )
            return release

    class Update:
        async def execute(self, identifier, definition):
            assert events == ["save_complete_draft"]
            events.append("make_agent_available")
            agent.status = definition.status
            if mismatch:
                agent.system_prompt = "Unexpected difference"

    definition = CreateReleaseInput(
        project_id=agent.project_id, agent_id=agent.id, version="auto"
    )
    return (
        agent,
        events,
        FinalizeImportedAgentUseCase(Draft(), Update(), Agents()),
        definition,
    )


@pytest.mark.asyncio
async def test_import_finalization_activates_only_after_full_draft_and_preserves_lineage():
    agent, events, use_case, definition = scenario()
    release = await use_case.execute(definition)
    assert events == ["save_complete_draft", "make_agent_available"]
    assert agent.status == AgentStatus.active
    assert agent.settings["prompt_version_id"] == str(release.prompt_version_id)
    assert agent.settings["contract_version_id"] == str(release.contract_version_id)


@pytest.mark.asyncio
async def test_projection_disagreement_rejects_finalization_inside_owner_scope():
    _, _, use_case, definition = scenario(mismatch=True)
    with pytest.raises(ConflictError, match="projection"):
        await use_case.execute(definition)


@pytest.mark.asyncio
async def test_finalizer_cannot_mutate_an_already_available_agent():
    agent, events, use_case, definition = scenario()
    agent.status = AgentStatus.active
    with pytest.raises(ConflictError, match="inactive"):
        await use_case.execute(definition)
    assert events == []
