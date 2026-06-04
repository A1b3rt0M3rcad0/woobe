from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.observability.infra.repositories import SQLAlchemyTraceRepository
from modules.observability.service.use_cases import ListTracesUseCase
from modules.observability.presentation.controllers.list_traces_controller import ListTracesController
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def list_traces_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    repo = SQLAlchemyTraceRepository(uow)
    use_case = ListTracesUseCase(repo)
    controller = ListTracesController(use_case)
    return TransactionalHandler(uow, controller.handle)
