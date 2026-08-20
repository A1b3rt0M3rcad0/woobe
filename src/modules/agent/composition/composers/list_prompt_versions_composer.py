from modules.agent.application.use_cases import ListPromptsUseCase
from modules.agent.composition.resources import DATABASE_ENGINE
from modules.agent.infra.database.repositories import SQLAlchemyAgentPromptRepository
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.list_prompt_versions_controller import ListPromptVersionsController
from shared.infra.transactional_handler import TransactionalHandler


def list_prompt_versions_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    repo = SQLAlchemyAgentPromptRepository(uow)
    use_case = ListPromptsUseCase(repo)
    controller = ListPromptVersionsController(use_case)
    return TransactionalHandler(uow, controller.handle)
