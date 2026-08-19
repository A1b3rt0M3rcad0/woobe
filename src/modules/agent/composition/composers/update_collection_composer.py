from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.application.use_cases.update_collection_use_case import UpdateCollectionUseCase
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.update_collection_controller import UpdateCollectionController
from shared.infra.transactional_handler import TransactionalHandler


def update_collection_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    use_case = UpdateCollectionUseCase(uow.document_collections)
    controller = UpdateCollectionController(use_case)
    return TransactionalHandler(uow, controller.handle)
