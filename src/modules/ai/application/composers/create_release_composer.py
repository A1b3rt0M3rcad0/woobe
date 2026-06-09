from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.ai.infra.repositories import SQLAlchemyAgentReleaseRepository
from modules.ai.service.use_cases import CreateReleaseUseCase
from modules.ai.presentation.controllers.create_release_controller import CreateReleaseController
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def create_release_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    repo = SQLAlchemyAgentReleaseRepository(uow)
    use_case = CreateReleaseUseCase(repo)
    controller = CreateReleaseController(use_case)
    return TransactionalHandler(uow, controller.handle)
