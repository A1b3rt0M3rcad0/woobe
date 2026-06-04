from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.billing.infra.repositories import SQLAlchemyPlanRepository
from modules.billing.service.use_cases import ListActivePlansUseCase
from modules.billing.presentation.controllers.list_plans_controller import ListPlansController
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def list_plans_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    repo = SQLAlchemyPlanRepository(uow)
    use_case = ListActivePlansUseCase(repo)
    controller = ListPlansController(use_case)
    return TransactionalHandler(uow, controller.handle)
