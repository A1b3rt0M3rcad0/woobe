from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.metering.infra.database.repositories import SQLAlchemyOutboxEventWriter, SQLAlchemyUsageEventRepository
from modules.metering.infra.database.unit_of_work import MeteringUnitOfWork
from modules.metering.application.use_cases import RecordUsageUseCase
from modules.metering.presentation.controllers.record_usage_controller import RecordUsageController
from shared.infra.transactional_handler import TransactionalHandler


def record_usage_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = MeteringUnitOfWork(session_factory)
    repo = SQLAlchemyUsageEventRepository(uow)
    outbox = SQLAlchemyOutboxEventWriter(uow)
    use_case = RecordUsageUseCase(repo, outbox)
    controller = RecordUsageController(use_case)
    return TransactionalHandler(uow, controller.handle)
