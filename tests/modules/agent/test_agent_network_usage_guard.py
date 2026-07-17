import pytest

from modules.agent.application.dtos.ai_dtos import UpdateAgentInput
from modules.agent.application.use_cases.ai_agent_cases import UpdateAgentUseCase
from modules.agent.domain.enums import AgentStatus
from shared.infra.errors import ConflictError
from tests.helpers import make_agent


@pytest.mark.asyncio
@pytest.mark.parametrize("target_status", [AgentStatus.inactive, AgentStatus.archived])
async def test_disabling_active_agent_used_by_network_draft_is_blocked(
    mocker,
    target_status: AgentStatus,
) -> None:
    agent = make_agent()
    agent.status = AgentStatus.active
    agent_repo = mocker.AsyncMock()
    agent_repo.get_by_id.return_value = agent
    credential_repo = mocker.AsyncMock()
    outbox = mocker.AsyncMock()
    usage_reader = mocker.AsyncMock()
    usage_reader.list_draft_references.return_value = [
        {"id": "network-a", "name": "Customer Support"}
    ]
    use_case = UpdateAgentUseCase(
        agent_repo,
        credential_repo,
        outbox,
        network_usage_reader=usage_reader,
    )

    with pytest.raises(ConflictError, match="Customer Support"):
        await use_case.execute(
            agent.id,
            UpdateAgentInput(status=target_status),
        )

    usage_reader.list_draft_references.assert_awaited_once_with(
        project_id=agent.project_id,
        agent_id=agent.id,
    )
    agent_repo.update.assert_not_awaited()
    outbox.write.assert_not_awaited()


@pytest.mark.asyncio
async def test_regular_agent_update_does_not_query_network_usage(mocker) -> None:
    agent = make_agent()
    agent.status = AgentStatus.active
    agent_repo = mocker.AsyncMock()
    agent_repo.get_by_id.return_value = agent
    agent_repo.update.return_value = agent
    credential_repo = mocker.AsyncMock()
    outbox = mocker.AsyncMock()
    usage_reader = mocker.AsyncMock()
    use_case = UpdateAgentUseCase(
        agent_repo,
        credential_repo,
        outbox,
        network_usage_reader=usage_reader,
    )

    await use_case.execute(agent.id, UpdateAgentInput(description="Updated"))

    usage_reader.list_draft_references.assert_not_awaited()
