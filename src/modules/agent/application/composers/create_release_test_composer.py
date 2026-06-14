from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.infra.database.repositories import SQLAlchemyAgentReleaseTestRepository
from modules.agent.application.use_cases.ai_use_cases import CreateReleaseTestUseCase
from modules.agent.presentation.controllers.create_release_test_controller import CreateReleaseTestController
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def create_release_test_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    repo = SQLAlchemyAgentReleaseTestRepository(uow)
    use_case = CreateReleaseTestUseCase(repo)
    controller = CreateReleaseTestController(use_case)
    return TransactionalHandler(uow, controller.handle)
