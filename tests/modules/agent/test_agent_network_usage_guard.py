import pytest

from modules.agent.application.dtos.ai_dtos import UpdateAgentInput
from modules.agent.application.use_cases.ai_agent_cases import UpdateAgentUseCase
from modules.agent.domain.enums import AgentStatus
from shared.infra.errors import ConflictError
from tests.helpers import make_agent


@pytest.mark.asyncio
async def test_deactivating_agent_used_by_network_draft_is_blocked(mocker) -> None:
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
            UpdateAgentInput(status=AgentStatus.inactive),
        )

    agent_repo.update.assert_not_awaited()
    outbox.write.assert_not_awaited()
