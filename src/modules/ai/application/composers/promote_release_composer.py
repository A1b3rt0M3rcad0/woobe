from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.ai.infra.repositories import SQLAlchemyAgentReleaseRepository
from modules.ai.service.use_cases import PromoteReleaseUseCase
from modules.ai.presentation.controllers.promote_release_controller import PromoteReleaseController
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def promote_release_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    repo = SQLAlchemyAgentReleaseRepository(uow)
    use_case = PromoteReleaseUseCase(repo)
    controller = PromoteReleaseController(use_case)
    return TransactionalHandler(uow, controller.handle)
