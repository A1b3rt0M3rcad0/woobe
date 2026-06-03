from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from modules.tools.domain.repositories import SecretRepository, ToolRepository
from modules.tools.infra.repositories import (
    SQLAlchemySecretRepository,
    SQLAlchemyToolRepository,
)
from modules.tools.service.use_cases import (
    CreateSecretUseCase,
    CreateToolUseCase,
)


def provide_create_tool_uc(session: AsyncSession) -> CreateToolUseCase:
    repo: ToolRepository = SQLAlchemyToolRepository(session)
    return CreateToolUseCase(session, repo)


async def provide_list_tools_by_agent(session: AsyncSession, agent_id: UUID):
    repo = SQLAlchemyToolRepository(session)
    return await repo.list_by_agent(agent_id)


def provide_create_secret_uc(session: AsyncSession) -> CreateSecretUseCase:
    repo: SecretRepository = SQLAlchemySecretRepository(session)
    return CreateSecretUseCase(session, repo)
