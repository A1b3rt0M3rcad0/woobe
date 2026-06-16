from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.infra.database.repositories import SQLAlchemyAgentPromptRepository
from modules.agent.application.use_cases import CreatePromptUseCase
from modules.agent.presentation.controllers.create_prompt_version_controller import CreatePromptVersionController
from shared.infra.transactional_handler import TransactionalHandler
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork


def create_prompt_version_composer(session_factory: async_sessionmaker[AsyncSession]) -> TransactionalHandler:
    uow = AgentUnitOfWork(session_factory)
    repo = SQLAlchemyAgentPromptRepository(uow)
    use_case = CreatePromptUseCase(repo)
    controller = CreatePromptVersionController(use_case)
    return TransactionalHandler(uow, controller.handle)
