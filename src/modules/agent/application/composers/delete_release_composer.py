from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.infra.database.repositories import SQLAlchemyAgentReleaseRepository
from modules.agent.application.use_cases import DeleteReleaseUseCase
from modules.agent.presentation.controllers.delete_release_controller import DeleteReleaseController
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def delete_release_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    repo = SQLAlchemyAgentReleaseRepository(uow)
    use_case = DeleteReleaseUseCase(repo)
    controller = DeleteReleaseController(use_case)
    return TransactionalHandler(uow, controller.handle)
