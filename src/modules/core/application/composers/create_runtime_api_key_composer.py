from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.infra.database.repositories import SQLAlchemyAgentRepository
from modules.core.application.use_cases.create_runtime_api_key_use_case import (
    CreateRuntimeApiKeyUseCase,
)
from modules.core.infra.database.unit_of_work import CoreUnitOfWork
from modules.core.presentation.controllers.create_runtime_api_key_controller import (
    CreateRuntimeApiKeyController,
)
from shared.infra.transactional_handler import TransactionalHandler


def create_runtime_api_key_composer(
    session_factory: async_sessionmaker[AsyncSession],
) -> TransactionalHandler:
    uow = CoreUnitOfWork(session_factory)
    use_case = CreateRuntimeApiKeyUseCase(
        uow.projects,
        SQLAlchemyAgentRepository(uow),
        uow.api_keys,
        uow.outbox,
    )
    controller = CreateRuntimeApiKeyController(use_case)
    return TransactionalHandler(uow, controller.handle)
