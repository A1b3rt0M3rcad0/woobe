from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.billing.infra.database.repositories import SQLAlchemyPlanRepository
from modules.billing.infra.database.unit_of_work import BillingUnitOfWork
from modules.billing.application.use_cases import ListActivePlansUseCase
from modules.billing.presentation.controllers.list_plans_controller import ListPlansController
from shared.infra.transactional_handler import TransactionalHandler


def list_plans_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = BillingUnitOfWork(session_factory)
    repo = SQLAlchemyPlanRepository(uow)
    use_case = ListActivePlansUseCase(repo)
    controller = ListPlansController(use_case)
    return TransactionalHandler(uow, controller.handle)
