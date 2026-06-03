from sqlalchemy.ext.asyncio import AsyncSession

from modules.ai.domain.repositories import AgentRepository, ProviderCredentialRepository
from modules.ai.infra.repositories import (
    SQLAlchemyAgentRepository,
    SQLAlchemyOutboxEventWriter,
    SQLAlchemyProviderCredentialRepository,
)
from modules.ai.service.use_cases import (
    CreateAgentUseCase,
    CreateProviderCredentialUseCase,
    UpdateAgentUseCase,
)
from shared.domain.events import OutboxEventWriter


def get_create_agent_use_case(session: AsyncSession) -> CreateAgentUseCase:
    agent_repo: AgentRepository = SQLAlchemyAgentRepository(session)
    credential_repo: ProviderCredentialRepository = SQLAlchemyProviderCredentialRepository(session)
    outbox: OutboxEventWriter = SQLAlchemyOutboxEventWriter(session)
    return CreateAgentUseCase(agent_repo, credential_repo, outbox)


def get_create_provider_credential_use_case(session: AsyncSession) -> CreateProviderCredentialUseCase:
    credential_repo: ProviderCredentialRepository = SQLAlchemyProviderCredentialRepository(session)
    outbox: OutboxEventWriter = SQLAlchemyOutboxEventWriter(session)
    return CreateProviderCredentialUseCase(credential_repo, outbox)


def get_update_agent_use_case(session: AsyncSession) -> UpdateAgentUseCase:
    agent_repo: AgentRepository = SQLAlchemyAgentRepository(session)
    credential_repo: ProviderCredentialRepository = SQLAlchemyProviderCredentialRepository(session)
    outbox: OutboxEventWriter = SQLAlchemyOutboxEventWriter(session)
    return UpdateAgentUseCase(agent_repo, credential_repo, outbox)


def get_agent_by_id_use_case(session: AsyncSession):
    repo = SQLAlchemyAgentRepository(session)
    return _GetAgentByIdUseCase(repo)


class _GetAgentByIdUseCase:
    def __init__(self, repo: AgentRepository):
        self._repo = repo

    async def execute(self, agent_id):
        from modules.ai.domain.errors import AgentNotFoundError
        agent = await self._repo.get_by_id(agent_id)
        if not agent:
            raise AgentNotFoundError(agent_id)
        return agent
