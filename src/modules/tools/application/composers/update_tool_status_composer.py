from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.tools.infra.repositories import SQLAlchemyOutboxEventWriter, SQLAlchemyToolRepository
from modules.tools.application.use_cases import UpdateToolStatusUseCase
from modules.tools.presentation.controllers.update_tool_status_controller import UpdateToolStatusController
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def update_tool_status_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    repo = SQLAlchemyToolRepository(uow)
    outbox = SQLAlchemyOutboxEventWriter(uow)
    use_case = UpdateToolStatusUseCase(repo, outbox)
    controller = UpdateToolStatusController(use_case)
    return TransactionalHandler(uow, controller.handle)
