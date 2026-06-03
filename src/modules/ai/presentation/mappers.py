from modules.ai.domain.entities import Agent
from modules.ai.presentation.schemas import AgentResponse


def agent_to_response(agent: Agent) -> AgentResponse:
    return AgentResponse(
        id=agent.id,
        project_id=agent.project_id,
        name=agent.name,
        provider=agent.provider.value if hasattr(agent.provider, 'value') else agent.provider,
        model=agent.model,
        status=agent.status.value if hasattr(agent.status, 'value') else agent.status,
        created_at=agent.created_at,
    )
