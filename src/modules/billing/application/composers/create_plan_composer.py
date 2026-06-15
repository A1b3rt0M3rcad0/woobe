from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.billing.infra.repositories import SQLAlchemyOutboxEventWriter, SQLAlchemyPlanRepository
from modules.billing.application.use_cases import CreatePlanUseCase
from modules.billing.presentation.controllers.create_plan_controller import CreatePlanController
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def create_plan_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    repo = SQLAlchemyPlanRepository(uow)
    outbox = SQLAlchemyOutboxEventWriter(uow)
    use_case = CreatePlanUseCase(repo, outbox)
    controller = CreatePlanController(use_case)
    return TransactionalHandler(uow, controller.handle)
