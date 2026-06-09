from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.runtime.infra.repositories import SQLAlchemyAskJobRepository
from modules.runtime.presentation.controllers.create_ask_job_controller import (
    CreateAskJobController,
)
from modules.runtime.service.use_cases import CreateAskJobUseCase
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def create_ask_job_composer(
    session_factory: async_sessionmaker[AsyncSession],
) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    repo = SQLAlchemyAskJobRepository(uow)
    use_case = CreateAskJobUseCase(repo)
    controller = CreateAskJobController(use_case)
    return TransactionalHandler(uow, controller.handle)
