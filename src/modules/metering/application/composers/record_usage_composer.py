from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.metering.infra.repositories import SQLAlchemyOutboxEventWriter, SQLAlchemyUsageEventRepository
from modules.metering.service.use_cases import RecordUsageUseCase
from modules.metering.presentation.controllers.record_usage_controller import RecordUsageController
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def record_usage_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    repo = SQLAlchemyUsageEventRepository(uow)
    outbox = SQLAlchemyOutboxEventWriter(uow)
    use_case = RecordUsageUseCase(repo, outbox)
    controller = RecordUsageController(use_case)
    return TransactionalHandler(uow, controller.handle)
