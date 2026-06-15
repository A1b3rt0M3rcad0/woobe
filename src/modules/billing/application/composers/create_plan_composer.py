from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.billing.infra.database.repositories import SQLAlchemyOutboxEventWriter, SQLAlchemyPlanRepository
from modules.billing.infra.database.unit_of_work import BillingUnitOfWork
from modules.billing.application.use_cases import CreatePlanUseCase
from modules.billing.presentation.controllers.create_plan_controller import CreatePlanController
from shared.application.transactional_handler import TransactionalHandler


def create_plan_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = BillingUnitOfWork(session_factory)
    repo = SQLAlchemyPlanRepository(uow)
    outbox = SQLAlchemyOutboxEventWriter(uow)
    use_case = CreatePlanUseCase(repo, outbox)
    controller = CreatePlanController(use_case)
    return TransactionalHandler(uow, controller.handle)
