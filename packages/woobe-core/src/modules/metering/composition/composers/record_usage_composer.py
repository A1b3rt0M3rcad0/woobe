from modules.metering.application.use_cases import RecordUsageUseCase
from modules.metering.composition.resources import DATABASE_ENGINE
from modules.metering.infra.database.repositories import (
    SQLAlchemyOutboxEventWriter,
    SQLAlchemyUsageEventRepository,
)
from modules.metering.infra.database.unit_of_work import MeteringUnitOfWork
from modules.metering.presentation.controllers.record_usage_controller import (
    RecordUsageController,
)
from shared.infra.transactional_handler import TransactionalHandler


def record_usage_composer() -> TransactionalHandler:
    uow = MeteringUnitOfWork(DATABASE_ENGINE)
    repo = SQLAlchemyUsageEventRepository(uow)
    outbox = SQLAlchemyOutboxEventWriter(uow)
    use_case = RecordUsageUseCase(repo, outbox)
    controller = RecordUsageController(use_case)
    return TransactionalHandler(uow, controller.handle)
