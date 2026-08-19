from modules.agent.application.use_cases import ListPromptsUseCase
from modules.agent.infra.database.database import AgentDatabase
from modules.agent.infra.database.repositories import SQLAlchemyAgentPromptRepository
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.list_prompt_versions_controller import ListPromptVersionsController
from shared.infra.transactional_handler import TransactionalHandler


def list_prompt_versions_composer(database: AgentDatabase) -> TransactionalHandler:
    uow = AgentUnitOfWork(database)
    repo = SQLAlchemyAgentPromptRepository(uow)
    use_case = ListPromptsUseCase(repo)
    controller = ListPromptVersionsController(use_case)
    return TransactionalHandler(uow, controller.handle)
