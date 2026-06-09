from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.ai.infra.repositories import SQLAlchemyAgentPromptRepository
from modules.ai.service.use_cases import GetPromptUseCase
from modules.ai.presentation.controllers.get_prompt_version_controller import GetPromptVersionController
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def get_prompt_version_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    repo = SQLAlchemyAgentPromptRepository(uow)
    use_case = GetPromptUseCase(repo)
    controller = GetPromptVersionController(use_case)
    return TransactionalHandler(uow, controller.handle)
