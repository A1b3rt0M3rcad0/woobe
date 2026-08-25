from modules.agent.application.use_cases import GetPromptUseCase
from modules.agent.composition.resources import DATABASE_ENGINE
from modules.agent.infra.database.repositories import SQLAlchemyAgentPromptRepository
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.get_prompt_version_controller import GetPromptVersionController
from shared.infra.transactional_handler import TransactionalHandler


def get_prompt_version_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    repo = SQLAlchemyAgentPromptRepository(uow)
    use_case = GetPromptUseCase(repo)
    controller = GetPromptVersionController(use_case)
    return TransactionalHandler(uow, controller.handle)
