from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from modules.ai.domain.errors import AgentNotFoundError
from modules.ai.domain.repositories import (
    AgentRepository,
    ProviderCredentialRepository,
)
from modules.ai.infra.repositories import (
    SQLAlchemyAgentRepository,
    SQLAlchemyOutboxEventWriter,
    SQLAlchemyProviderCredentialRepository,
)
from modules.ai.service.dtos import CreateAgentOutput
from modules.ai.service.use_cases import (
    CreateAgentUseCase,
    CreateProviderCredentialUseCase,
)


def get_create_provider_credential_use_case(
    session: AsyncSession,
) -> CreateProviderCredentialUseCase:
    return CreateProviderCredentialUseCase(
        credential_repo=SQLAlchemyProviderCredentialRepository(session),
        outbox=SQLAlchemyOutboxEventWriter(session),
    )


def get_create_agent_use_case(session: AsyncSession) -> CreateAgentUseCase:
    return CreateAgentUseCase(
        agent_repo=SQLAlchemyAgentRepository(session),
        credential_repo=SQLAlchemyProviderCredentialRepository(session),
        outbox=SQLAlchemyOutboxEventWriter(session),
    )


class GetAgentByIdUseCase:
    def __init__(self, agent_repo: AgentRepository) -> None:
        self._agent_repo = agent_repo

    async def execute(self, agent_id: UUID) -> CreateAgentOutput:
        agent = await self._agent_repo.get_by_id(agent_id)
        if not agent:
            raise AgentNotFoundError(agent_id)
        return CreateAgentOutput(
            id=agent.id,
            project_id=agent.project_id,
            name=agent.name,
            type=agent.type,
            provider=agent.provider,
            model=agent.model,
            status=agent.status,
            created_at=agent.created_at,
        )


def get_agent_by_id_use_case(session: AsyncSession) -> GetAgentByIdUseCase:
    return GetAgentByIdUseCase(
        agent_repo=SQLAlchemyAgentRepository(session),
    )
