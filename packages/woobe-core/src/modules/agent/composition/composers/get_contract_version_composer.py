from modules.agent.application.use_cases import GetContractUseCase
from modules.agent.composition.resources import DATABASE_ENGINE
from modules.agent.infra.database.repositories import SQLAlchemyAgentContractRepository
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.get_contract_version_controller import GetContractVersionController
from shared.infra.transactional_handler import TransactionalHandler


def get_contract_version_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    repo = SQLAlchemyAgentContractRepository(uow)
    use_case = GetContractUseCase(repo)
    controller = GetContractVersionController(use_case)
    return TransactionalHandler(uow, controller.handle)
