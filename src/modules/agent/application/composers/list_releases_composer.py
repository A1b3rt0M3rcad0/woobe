from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.ai.infra.repositories import SQLAlchemyAgentReleaseRepository
from modules.agent.application.use_cases.ai_use_cases import ListReleasesUseCase
from modules.ai.presentation.controllers.list_releases_controller import ListReleasesController
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def list_releases_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    repo = SQLAlchemyAgentReleaseRepository(uow)
    use_case = ListReleasesUseCase(repo)
    controller = ListReleasesController(use_case)
    return TransactionalHandler(uow, controller.handle)
