from modules.agent.application.use_cases import CreatePromptUseCase
from modules.agent.infra.database.database import AgentDatabase
from modules.agent.infra.database.repositories import SQLAlchemyAgentPromptRepository
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.create_prompt_version_controller import CreatePromptVersionController
from shared.infra.transactional_handler import TransactionalHandler


def create_prompt_version_composer(database: AgentDatabase) -> TransactionalHandler:
    uow = AgentUnitOfWork(database)
    repo = SQLAlchemyAgentPromptRepository(uow)
    use_case = CreatePromptUseCase(repo)
    controller = CreatePromptVersionController(use_case)
    return TransactionalHandler(uow, controller.handle)
