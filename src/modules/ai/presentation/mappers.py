from modules.ai.domain.entities import Agent
from modules.ai.presentation.schemas import AgentResponse


def agent_to_response(agent: Agent) -> AgentResponse:
    return AgentResponse(
        id=agent.id,
        project_id=agent.project_id,
        name=agent.name,
        provider=agent.provider.value if hasattr(agent.provider, 'value') else agent.provider,
        model=agent.model,
        provider_credential_id=agent.provider_credential_id,
        fallback_credential_id=agent.fallback_credential_id,
        fallback_provider=agent.fallback_provider.value if (hasattr(agent.fallback_provider, 'value') and agent.fallback_provider) else agent.fallback_provider,
        fallback_model=agent.fallback_model,
        temperature=agent.temperature,
        max_output_tokens=agent.max_output_tokens,
        session_mode=agent.session_mode.value if hasattr(agent.session_mode, 'value') else agent.session_mode,
        system_prompt=agent.system_prompt,
        description=agent.description,
        status=agent.status.value if hasattr(agent.status, 'value') else agent.status,
        settings=agent.settings,
        created_at=agent.created_at,
        updated_at=agent.updated_at,
    )
