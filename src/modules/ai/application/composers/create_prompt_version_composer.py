from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.ai.infra.repositories import SQLAlchemyAgentPromptRepository
from modules.ai.service.use_cases import CreatePromptUseCase
from modules.ai.presentation.controllers.create_prompt_version_controller import CreatePromptVersionController
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def create_prompt_version_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    repo = SQLAlchemyAgentPromptRepository(uow)
    use_case = CreatePromptUseCase(repo)
    controller = CreatePromptVersionController(use_case)
    return TransactionalHandler(uow, controller.handle)
