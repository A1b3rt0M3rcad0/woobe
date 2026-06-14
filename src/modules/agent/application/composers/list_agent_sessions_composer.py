from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.infra.database.repositories import (
    SQLAlchemyMessageRepository,
    SQLAlchemySessionRepository,
)
from modules.agent.presentation.controllers.list_agent_sessions_controller import (
    ListAgentSessionsController,
)
from modules.agent.application.use_cases.runtime_use_cases import ListAgentSessionsUseCase
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def list_agent_sessions_composer(
    session_factory: async_sessionmaker[AsyncSession],
) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)

    session_repo = SQLAlchemySessionRepository(uow)
    message_repo = SQLAlchemyMessageRepository(uow)

    use_case = ListAgentSessionsUseCase(
        session_repo=session_repo,
        message_repo=message_repo,
    )

    controller = ListAgentSessionsController(use_case)
    return TransactionalHandler(uow, controller.handle)
