from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.infra.database.repositories import SQLAlchemyAgentPromptRepository
from modules.agent.application.use_cases import ListPromptsUseCase
from modules.agent.presentation.controllers.list_prompt_versions_controller import ListPromptVersionsController
from shared.infra.transactional_handler import TransactionalHandler
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork


def list_prompt_versions_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    repo = SQLAlchemyAgentPromptRepository(uow)
    use_case = ListPromptsUseCase(repo)
    controller = ListPromptVersionsController(use_case)
    return TransactionalHandler(uow, controller.handle)
