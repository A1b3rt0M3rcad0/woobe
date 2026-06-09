from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.ai.infra.repositories import SQLAlchemyAgentPromptRepository
from modules.ai.service.use_cases import ListPromptsUseCase
from modules.ai.presentation.controllers.list_prompt_versions_controller import ListPromptVersionsController
from shared.application.transactional_handler import TransactionalHandler
from shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork


def list_prompt_versions_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = PostgresUnitOfWork(session_factory)
    repo = SQLAlchemyAgentPromptRepository(uow)
    use_case = ListPromptsUseCase(repo)
    controller = ListPromptVersionsController(use_case)
    return TransactionalHandler(uow, controller.handle)
