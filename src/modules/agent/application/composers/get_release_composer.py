from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.infra.database.repositories import SQLAlchemyAgentReleaseRepository
from modules.agent.application.use_cases.ai_use_cases import GetReleaseUseCase
from modules.agent.presentation.controllers.get_release_controller import GetReleaseController
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def get_release_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    repo = SQLAlchemyAgentReleaseRepository(uow)
    use_case = GetReleaseUseCase(repo)
    controller = GetReleaseController(use_case)
    return TransactionalHandler(uow, controller.handle)
