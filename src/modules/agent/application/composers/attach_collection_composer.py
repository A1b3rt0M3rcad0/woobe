from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.infra.database.repositories import SQLAlchemyAgentCollectionRepository
from modules.agent.presentation.controllers.attach_collection_controller import AttachCollectionController
from modules.agent.application.use_cases.knowledge_use_cases import AttachCollectionUseCase
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def attach_collection_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    repo = SQLAlchemyAgentCollectionRepository(uow)
    use_case = AttachCollectionUseCase(repo)
    controller = AttachCollectionController(use_case)
    return TransactionalHandler(uow, controller.handle)
